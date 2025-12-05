import os
import uvicorn
import asyncio
import traceback
import mimetypes
from typing import List, Optional

from fastapi import FastAPI, Request, UploadFile, File, Form, Header, HTTPException, APIRouter
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from google.genai import types

from src.logic_graph import get_compiled_graph
from src.utils.logging_utils import log_structured
from src.tools.claims_tools import analyze_claim_image_async, save_batch_claim_data

app = FastAPI(title="DirIA Core", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

claims_router = APIRouter(prefix="/api/v1/claims", tags=["claims"])

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_PATH = os.path.join(BASE_DIR, "src", "static")
INDEX_FILE = os.path.join(STATIC_PATH, "index.html")
CONSOLE_FILE = os.path.join(STATIC_PATH, "console.html")

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")

@app.get("/", tags=["UI"])
async def serve_ui():
    if os.path.exists(INDEX_FILE):
        return FileResponse(INDEX_FILE)
    return JSONResponse(status_code=404, content={"error": "UI no encontrada"})

@app.get("/console.html", tags=["UI"])
async def serve_console():
    if os.path.exists(CONSOLE_FILE):
        return FileResponse(CONSOLE_FILE)
    return JSONResponse(status_code=404, content={"error": "Consola no encontrada"})

@app.get("/health")
async def health():
    return {"status": "ok", "mode": "hybrid_dwh_enabled"}

# --- CHATBOT (LangGraph) ---
@app.post("/", tags=["Chat"])
async def handle_chat(request: Request):
    try:
        event = await request.json()
        
        request_source = event.get('source', 'chat') 
        
        if event.get('type') != 'MESSAGE': return {}

        user_email = event.get('user', {}).get('email', 'web_guest@diria.io')
        message_text = event.get('message', {}).get('text', '')
        thread_id = event.get('message', {}).get('thread', {}).get('name', f"thread_{user_email}")

        log_structured("MessageReceived", user=user_email, text=message_text, source=request_source)

        # Cerebro
        graph = get_compiled_graph()
        if not graph: raise ImportError("Grafo no cargado.")

        config = {"configurable": {"thread_id": thread_id}}
        
        inputs = {
            "messages": [types.Content(role="user", parts=[types.Part.from_text(text=message_text)])],
            "user_email": user_email,
            "origin": request_source 
        }
        
        state = await graph.ainvoke(inputs, config=config)
        
        last_msg = state["messages"][-1]
        response_text = last_msg.parts[0].text if last_msg.parts else "..."
        
        return {"text": response_text}

    except Exception as e:
        tb = traceback.format_exc()
        print(f"Chat Error: {e}")
        return {"text": f"Error en el cerebro KAI: {str(e)}"}

@claims_router.post("/upload")
async def upload_claims(
    service_number: str = Form(...),
    files: List[UploadFile] = File(...)
):
    try:
        count = len(files)
        log_structured("BatchUploadStart", service=service_number, count=count)
        
        tasks = []
        
        for file in files:
            content = await file.read()
            mime_type, _ = mimetypes.guess_type(file.filename)
            if not mime_type: mime_type = file.content_type or "application/octet-stream"
            
            tasks.append(
                analyze_claim_image_async(service_number, content, file.filename, mime_type)
            )
        
        raw_results = await asyncio.gather(*tasks)
        final_data = save_batch_claim_data(service_number, raw_results)
        
        log_structured("BatchUploadSuccess", service=service_number, processed=len(raw_results))

        return {
            "status": "success",
            "service": service_number,
            "processed_count": count,
            "data": final_data
        }

    except Exception as e:
        tb = traceback.format_exc()
        print(f"Upload Error: {tb}")
        return JSONResponse(status_code=500, content={"error": str(e), "detail": "Fallo en procesamiento IA."})

app.include_router(claims_router)

from src.api.user_router import router as user_router
app.include_router(user_router)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)