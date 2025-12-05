import json
from sqlalchemy import text
from google import genai
from src.config import settings
from src.utils.database_client import get_db_connection
from src.utils.logging_utils import log_structured

def init_memory_table():
    """Initializes the user_long_term_memory table with vector extension."""
    engine = get_db_connection()
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS user_long_term_memory (
                    id SERIAL PRIMARY KEY,
                    user_email VARCHAR(255),
                    content TEXT,
                    embedding VECTOR(768),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSONB
                );
            """))
            conn.commit()
            log_structured("MemoryTableInit", status="Success")
    except Exception as e:
        log_structured("MemoryTableInitError", error=str(e))

# Initialize on load
init_memory_table()

def get_embedding(text_content: str) -> list:
    """Generates embedding for text using Vertex AI."""
    try:
        client = genai.Client(vertexai=True, project=settings.GCP_PROJECT_ID, location=settings.LOCATION)
        response = client.models.embed_content(
            model=settings.EMBEDDING_MODEL_NAME,
            contents=text_content
        )
        return response.embeddings[0].values
    except Exception as e:
        log_structured("EmbeddingError", error=str(e))
        return []

def save_user_preference(user_email: str, preference_text: str):
    """Saves a user preference to long-term memory."""
    embedding = get_embedding(preference_text)
    if not embedding:
        return False

    engine = get_db_connection()
    try:
        with engine.connect() as conn:
            stmt = text("""
                INSERT INTO user_long_term_memory (user_email, content, embedding, metadata)
                VALUES (:user_email, :content, :embedding, :metadata)
            """)
            # Metadata could store 'type': 'preference' or 'fact'
            metadata = json.dumps({"type": "preference"})
            conn.execute(stmt, {
                "user_email": user_email, 
                "content": preference_text, 
                "embedding": str(embedding),
                "metadata": metadata
            })
            conn.commit()
        return True
    except Exception as e:
        log_structured("SaveMemoryError", error=str(e), user=user_email)
        return False

def get_relevant_preferences(user_email: str, query: str, limit: int = 3) -> list:
    """Retrieves relevant preferences based on the current query."""
    embedding = get_embedding(query)
    if not embedding:
        return []

    engine = get_db_connection()
    try:
        with engine.connect() as conn:
            # Search for memories for this user, ordered by similarity
            stmt = text("""
                SELECT content, 1 - (embedding <=> :embedding) as similarity
                FROM user_long_term_memory
                WHERE lower(user_email) = lower(:user_email)
                ORDER BY embedding <=> :embedding
                LIMIT :limit
            """)
            results = conn.execute(stmt, {
                "embedding": str(embedding),
                "user_email": user_email,
                "limit": limit
            }).fetchall()
            
            # Filter by some threshold if needed, e.g., > 0.5
            return [row[0] for row in results if row[1] > 0.5]
    except Exception as e:
        log_structured("GetMemoryError", error=str(e), user=user_email)
        return []
