import json
import sqlalchemy
from sqlalchemy import text
from google.cloud.sql.connector import Connector, IPTypes
from google import genai
from google.cloud import storage
from src.config import settings
from src.utils.logging_utils import log_structured
import numpy as np

# Initialize Cloud SQL Connector
connector = Connector()

def get_conn():
    conn = connector.connect(
        settings.DB_CONNECTION_NAME,
        "pg8000",
        user=settings.DB_USER,
        password=settings.DB_PASS,
        db=settings.DB_NAME,
        ip_type=IPTypes.PUBLIC,  # Adjust if using private IP
    )
    return conn

pool = sqlalchemy.create_engine(
    "postgresql+pg8000://",
    creator=get_conn,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
)

def init_db():
    """Initializes the database with the vector extension and table."""
    with pool.connect() as db_conn:
        db_conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        db_conn.execute(text("""
            CREATE TABLE IF NOT EXISTS knowledge_embeddings (
                id SERIAL PRIMARY KEY,
                content TEXT,
                embedding VECTOR(768),
                metadata JSONB
            );
        """))
        db_conn.commit()

# Initialize DB on module load (or call explicitly)
try:
    init_db()
except Exception as e:
    log_structured("DBInitError", error=str(e))

def get_embedding(text: str) -> list:
    client = genai.Client(vertexai=True, project=settings.GCP_PROJECT_ID, location=settings.LOCATION)
    response = client.models.embed_content(
        model=settings.EMBEDDING_MODEL_NAME,
        contents=text
    )
    return response.embeddings[0].values

def upload_document(file_content: bytes, filename: str, user_email: str, content_type: str = "text/plain") -> str:
    """
    Uploads a document, chunks it, embeds it, and stores it in Postgres.
    """
    # 1. Upload to GCS (User specific bucket/folder)
    storage_client = storage.Client(project=settings.GCP_PROJECT_ID)
    bucket_name = settings.KNOWLEDGE_BASE_BUCKET
    bucket = storage_client.bucket(bucket_name)
    
    # Dynamic path: user_email/filename
    blob_path = f"{user_email}/{filename}"
    blob = bucket.blob(blob_path)
    blob.upload_from_string(file_content, content_type=content_type)
    
    gcs_uri = f"gs://{bucket_name}/{blob_path}"
    
    # 2. Parse and Chunk (Simple splitting for now)
    # Assuming text content. For PDFs/Docs, we'd need a parser (e.g., PyPDF2, DocAI).
    # For now, treating as text.
    try:
        text_content = file_content.decode("utf-8")
    except UnicodeDecodeError:
        return "Error: Only text files are supported for now."

    chunk_size = 1000
    chunks = [text_content[i:i+chunk_size] for i in range(0, len(text_content), chunk_size)]
    
    # 3. Embed and Store
    with pool.connect() as db_conn:
        for chunk in chunks:
            embedding = get_embedding(chunk)
            stmt = text("""
                INSERT INTO knowledge_embeddings (content, embedding, metadata)
                VALUES (:content, :embedding, :metadata)
            """)
            metadata = json.dumps({"source": gcs_uri, "filename": filename, "user": user_email})
            db_conn.execute(stmt, parameters={"content": chunk, "embedding": str(embedding), "metadata": metadata})
        db_conn.commit()
        
    return f"Documento '{filename}' procesado y agregado a la base de conocimiento."

def search_knowledge_base(query: str, user_email: str, limit: int = 5) -> list:
    """
    Searches the knowledge base using vector similarity.
    """
    query_embedding = get_embedding(query)
    
    with pool.connect() as db_conn:
        # Cosine distance (<=>) or Inner Product (<#>) or L2 (<->)
        # Usually cosine distance is good for embeddings.
        # Note: pgvector's <=> operator is cosine distance. 
        # We want similarity, so we order by distance ASC.
        stmt = text("""
            SELECT content, metadata, 1 - (embedding <=> :embedding) as similarity
            FROM knowledge_embeddings
            WHERE metadata->>'user' = :user_email
            ORDER BY embedding <=> :embedding
            LIMIT :limit
        """)
        
        results = db_conn.execute(stmt, parameters={
            "embedding": str(query_embedding), 
            "user_email": user_email,
            "limit": limit
        }).fetchall()
        
    return [{"content": row[0], "metadata": row[1], "similarity": row[2]} for row in results]
