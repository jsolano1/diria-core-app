from src.services import knowledge_service
from google import genai
from src.config import settings
from src.utils.prompt_loader import load_prompt
from src.utils.logging_utils import log_structured

def search_knowledge_base_tool(user_query: str, solicitante_email: str = "unknown") -> str:
    """Busca en la base de conocimiento usando RAG con Postgres."""
    log_structured("KBSearchStart", query=user_query, user=solicitante_email)
    
    try:
        results = knowledge_service.search_knowledge_base(user_query, solicitante_email)
    except Exception as e:
        log_structured("KBSearchError", error=str(e))
        return "Hubo un error consultando la base de conocimiento."

    if not results:
        return "No encontré información relevante en tus documentos."

    # Filter by threshold if needed, currently just taking top results
    relevant_chunks = [r for r in results if r['similarity'] > 0.6]
    
    if not relevant_chunks:
        return "No encontré información suficientemente relevante en el KB."

    contexto_para_llm = "\n\n--- CONTEXTO ADICIONAL ---\n\n".join([
        f"Fuente: {c['metadata'].get('filename', 'unknown')} (Similitud: {c['similarity']:.2f})\nContenido: {c['content']}" 
        for c in relevant_chunks
    ])
    
    try:
        client = genai.Client(vertexai=True, project=settings.GCP_PROJECT_ID, location=settings.LOCATION)
        prompt_template_final = load_prompt("rag_final_answer.md") 
        
        if prompt_template_final:
            prompt_respuesta_final = prompt_template_final.replace("{document_content}", contexto_para_llm).replace("{user_query}", user_query)
        else:
            prompt_respuesta_final = f"Contexto:\n{contexto_para_llm}\n\nPregunta: {user_query}\n\nResponde usando el contexto."

        response = client.models.generate_content(
            model=settings.GEMINI_MODEL_ID,
            contents=prompt_respuesta_final
        )
        
        return response.candidates[0].content.parts[0].text
        
    except Exception as e:
        return f"Error durante el proceso final de RAG: {str(e)}"

def upload_document_tool(filename: str, content: str, solicitante_email: str = "unknown") -> str:
    """Sube un documento de texto a la base de conocimiento."""
    # This tool assumes content is passed as string. In a real console upload, 
    # the file would be handled by an API endpoint calling the service directly.
    # This tool might be used if the user pastes text to the agent.
    try:
        return knowledge_service.upload_document(content.encode('utf-8'), filename, solicitante_email)
    except Exception as e:
        return f"Error subiendo documento: {str(e)}"