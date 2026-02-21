"""
FastAPI РїСЂРёР»РѕР¶РµРЅРёРµ вЂ” Р±СЌРєРµРЅРґ RAG С‡Р°С‚-Р±РѕС‚Р°.
Р­РЅРґРїРѕРёРЅС‚С‹: /chat (СЃС‚СЂРёРјРёРЅРі), /upload, /documents, /documents/{filename} (DELETE).
"""

import json
import logging
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.config import DOCUMENTS_DIR, logger
from backend.ingestion import (
    ingest_file,
    ingest_directory,
    get_vectorstore,
    get_embeddings,
    get_indexed_documents,
    delete_document_from_db,
    get_relative_source,
)
from backend.chain import get_answer, get_answer_stream
from backend.retriever import reset_vectorstore_cache


# === Lifespan вЂ” Р·Р°РїСѓСЃРє/РѕСЃС‚Р°РЅРѕРІРєР° watchdog РїСЂРё СЃС‚Р°СЂС‚Рµ/РѕСЃС‚Р°РЅРѕРІРєРµ СЃРµСЂРІРµСЂР° ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Р·Р°РїСѓСЃРєР°РµРј РјРѕРЅРёС‚РѕСЂРёРЅРі РїР°РїРєРё documents/
    logger.info("Watcher is temporarily disabled. Use POST /reindex manually.")
    yield
    # Shutdown: РѕСЃС‚Р°РЅР°РІР»РёРІР°РµРј РјРѕРЅРёС‚РѕСЂРёРЅРі


# === FastAPI РїСЂРёР»РѕР¶РµРЅРёРµ ===
app = FastAPI(
    title="RAG Chatbot API",
    description="РљРѕСЂРїРѕСЂР°С‚РёРІРЅС‹Р№ С‡Р°С‚-Р±РѕС‚ СЃ RAG РЅР° Р±Р°Р·Рµ LangChain + Groq + ChromaDB",
    version="1.0.0",
    lifespan=lifespan,
)

# === CORS вЂ” СЂР°Р·СЂРµС€Р°РµРј С„СЂРѕРЅС‚РµРЅРґ РЅР° Vite ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Pydantic РјРѕРґРµР»Рё Р·Р°РїСЂРѕСЃРѕРІ/РѕС‚РІРµС‚РѕРІ ===

class ChatRequest(BaseModel):
    """Р—Р°РїСЂРѕСЃ РЅР° С‡Р°С‚."""
    question: str
    chat_history: list[dict] = []


class ChatResponse(BaseModel):
    """РћС‚РІРµС‚ С‡Р°С‚Р° (РґР»СЏ РЅРµ-СЃС‚СЂРёРјРёРЅРі СЂРµР¶РёРјР°)."""
    answer: str
    sources: list[dict] = []


class DocumentInfo(BaseModel):
    """РРЅС„РѕСЂРјР°С†РёСЏ Рѕ Р·Р°РіСЂСѓР¶РµРЅРЅРѕРј РґРѕРєСѓРјРµРЅС‚Рµ."""
    filename: str
    chunks_count: int
    pages: list
    upload_date: str = ""


# === Р­РЅРґРїРѕРёРЅС‚С‹ ===

@app.get("/", tags=["РћР±С‰РµРµ"])
async def root():
    """РљРѕСЂРЅРµРІРѕР№ СЌРЅРґРїРѕРёРЅС‚ вЂ” РїСЂРѕРІРµСЂРєР° СЂР°Р±РѕС‚РѕСЃРїРѕСЃРѕР±РЅРѕСЃС‚Рё."""
    return {"status": "ok", "message": "RAG Chatbot API СЂР°Р±РѕС‚Р°РµС‚"}


@app.post("/chat", tags=["Р§Р°С‚"])
async def chat(request: ChatRequest):
    """
    РЎС‚СЂРёРјРёРЅРі РѕС‚РІРµС‚Р° РЅР° РІРѕРїСЂРѕСЃ.
    РћС‚РїСЂР°РІР»СЏРµС‚ Server-Sent Events (SSE) вЂ” СЃРЅР°С‡Р°Р»Р° С‚РѕРєРµРЅС‹ РѕС‚РІРµС‚Р°, Р·Р°С‚РµРј РёСЃС‚РѕС‡РЅРёРєРё.
    Р¤РѕСЂРјР°С‚ СЃРѕР±С‹С‚РёР№:
      data: {"type": "token", "content": "..."}
      data: {"type": "sources", "content": [...]}
      data: {"type": "done"}
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Р’РѕРїСЂРѕСЃ РЅРµ РјРѕР¶РµС‚ Р±С‹С‚СЊ РїСѓСЃС‚С‹Рј")

    logger.info(f"POST /chat вЂ” РІРѕРїСЂРѕСЃ: '{request.question[:80]}...'")

    # РџРѕР»СѓС‡Р°РµРј async СЃС‚СЂРёРј Рё РёСЃС‚РѕС‡РЅРёРєРё
    token_stream, sources = await get_answer_stream(
        question=request.question,
        chat_history=request.chat_history,
    )

    async def event_generator():
        """Р“РµРЅРµСЂР°С‚РѕСЂ SSE СЃРѕР±С‹С‚РёР№."""
        try:
            # РЎС‚СЂРёРјРёРј С‚РѕРєРµРЅС‹ РѕС‚РІРµС‚Р°
            async for token in token_stream:
                data = json.dumps({"type": "token", "content": token}, ensure_ascii=False)
                yield f"data: {data}\n\n"

            # РћС‚РїСЂР°РІР»СЏРµРј РёСЃС‚РѕС‡РЅРёРєРё РїРѕСЃР»Рµ Р·Р°РІРµСЂС€РµРЅРёСЏ РѕС‚РІРµС‚Р°
            sources_data = json.dumps({"type": "sources", "content": sources}, ensure_ascii=False)
            yield f"data: {sources_data}\n\n"

            # РЎРёРіРЅР°Р» Р·Р°РІРµСЂС€РµРЅРёСЏ
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.error(f"РћС€РёР±РєР° РІ SSE СЃС‚СЂРёРјРµ: {e}")
            error_data = json.dumps({"type": "error", "content": str(e)}, ensure_ascii=False)
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/chat/sync", tags=["Р§Р°С‚"])
async def chat_sync(request: ChatRequest):
    """
    РЎРёРЅС…СЂРѕРЅРЅС‹Р№ РѕС‚РІРµС‚ РЅР° РІРѕРїСЂРѕСЃ (Р±РµР· СЃС‚СЂРёРјРёРЅРіР°).
    РџРѕР»РµР·РЅРѕ РґР»СЏ С‚РµСЃС‚РёСЂРѕРІР°РЅРёСЏ С‡РµСЂРµР· Swagger UI.
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Р’РѕРїСЂРѕСЃ РЅРµ РјРѕР¶РµС‚ Р±С‹С‚СЊ РїСѓСЃС‚С‹Рј")

    logger.info(f"POST /chat/sync вЂ” РІРѕРїСЂРѕСЃ: '{request.question[:80]}...'")
    result = get_answer(request.question, request.chat_history)
    return ChatResponse(**result)


@app.post("/upload", tags=["Р”РѕРєСѓРјРµРЅС‚С‹"])
async def upload_file(file: UploadFile = File(...)):
    """
    Р—Р°РіСЂСѓР·РєР° С„Р°Р№Р»Р° Рё РёРЅРґРµРєСЃР°С†РёСЏ РІ ChromaDB.
    РџРѕРґРґРµСЂР¶РёРІР°РµРјС‹Рµ С„РѕСЂРјР°С‚С‹: PDF, DOCX, TXT.
    Р•СЃР»Рё С„Р°Р№Р» СѓР¶Рµ СЃСѓС‰РµСЃС‚РІСѓРµС‚ вЂ” РїРµСЂРµР·Р°РїРёСЃС‹РІР°РµС‚СЃСЏ (РґРµРґСѓРїР»РёРєР°С†РёСЏ).
    """
    # РџСЂРѕРІРµСЂСЏРµРј СЂР°СЃС€РёСЂРµРЅРёРµ С„Р°Р№Р»Р°
    allowed_extensions = {".pdf", ".docx", ".doc", ".txt"}
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"РќРµРїРѕРґРґРµСЂР¶РёРІР°РµРјС‹Р№ С„РѕСЂРјР°С‚ С„Р°Р№Р»Р°: {file_ext}. Р”РѕРїСѓСЃС‚РёРјС‹Рµ: {', '.join(allowed_extensions)}",
        )

    # РЎРѕС…СЂР°РЅСЏРµРј С„Р°Р№Р» РЅР° РґРёСЃРє
    file_path = DOCUMENTS_DIR / file.filename
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"POST /upload вЂ” С„Р°Р№Р» СЃРѕС…СЂР°РЅС‘РЅ: {file.filename}")
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° СЃРѕС…СЂР°РЅРµРЅРёСЏ С„Р°Р№Р»Р°: {e}")
        raise HTTPException(status_code=500, detail=f"РћС€РёР±РєР° СЃРѕС…СЂР°РЅРµРЅРёСЏ С„Р°Р№Р»Р°: {str(e)}")

    # РРЅРґРµРєСЃРёСЂСѓРµРј С„Р°Р№Р»
    try:
        embeddings = get_embeddings()
        vectorstore = get_vectorstore(embeddings)
        chunks_count = ingest_file(file_path, vectorstore)

        # РЎР±СЂР°СЃС‹РІР°РµРј РєСЌС€ retriever С‡С‚РѕР±С‹ РЅРѕРІС‹Рµ РґР°РЅРЅС‹Рµ Р±С‹Р»Рё РґРѕСЃС‚СѓРїРЅС‹
        reset_vectorstore_cache()

        # РћС‚РЅРѕСЃРёС‚РµР»СЊРЅС‹Р№ РїСѓС‚СЊ РґР»СЏ РєРѕРЅСЃРёСЃС‚РµРЅС‚РЅРѕСЃС‚Рё СЃ metadata source
        source_name = get_relative_source(file_path)
        logger.info(f"POST /upload вЂ” РёРЅРґРµРєСЃР°С†РёСЏ Р·Р°РІРµСЂС€РµРЅР°: {chunks_count} С‡Р°РЅРєРѕРІ")
        return {
            "status": "ok",
            "filename": source_name,
            "chunks_count": chunks_count,
            "message": f"Р¤Р°Р№Р» '{source_name}' Р·Р°РіСЂСѓР¶РµРЅ Рё РїСЂРѕРёРЅРґРµРєСЃРёСЂРѕРІР°РЅ ({chunks_count} С‡Р°РЅРєРѕРІ)",
        }
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РёРЅРґРµРєСЃР°С†РёРё С„Р°Р№Р»Р°: {e}")
        raise HTTPException(status_code=500, detail=f"РћС€РёР±РєР° РёРЅРґРµРєСЃР°С†РёРё: {str(e)}")


@app.get("/documents", tags=["Р”РѕРєСѓРјРµРЅС‚С‹"])
async def list_documents():
    """РџРѕР»СѓС‡РµРЅРёРµ СЃРїРёСЃРєР° РІСЃРµС… Р·Р°РіСЂСѓР¶РµРЅРЅС‹С… Рё РїСЂРѕРёРЅРґРµРєСЃРёСЂРѕРІР°РЅРЅС‹С… РґРѕРєСѓРјРµРЅС‚РѕРІ."""
    try:
        documents = get_indexed_documents()
        logger.info(f"GET /documents вЂ” РЅР°Р№РґРµРЅРѕ {len(documents)} РґРѕРєСѓРјРµРЅС‚РѕРІ")
        return {"status": "ok", "documents": documents}
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїРѕР»СѓС‡РµРЅРёСЏ СЃРїРёСЃРєР° РґРѕРєСѓРјРµРЅС‚РѕРІ: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/documents/{filename:path}", tags=["Р”РѕРєСѓРјРµРЅС‚С‹"])
async def delete_document(filename: str):
    """
    РЈРґР°Р»РµРЅРёРµ РґРѕРєСѓРјРµРЅС‚Р° РёР· ChromaDB Рё СЃ РґРёСЃРєР°.
    """
    try:
        # РЈРґР°Р»СЏРµРј РёР· ChromaDB
        deleted_count = delete_document_from_db(filename)

        # РЈРґР°Р»СЏРµРј С„Р°Р№Р» СЃ РґРёСЃРєР°
        file_path = DOCUMENTS_DIR / filename
        if file_path.exists():
            file_path.unlink()
            logger.info(f"DELETE /documents/{filename} вЂ” С„Р°Р№Р» СѓРґР°Р»С‘РЅ СЃ РґРёСЃРєР°")

        # РЎР±СЂР°СЃС‹РІР°РµРј РєСЌС€ retriever
        reset_vectorstore_cache()

        if deleted_count > 0:
            return {
                "status": "ok",
                "message": f"Р”РѕРєСѓРјРµРЅС‚ '{filename}' СѓРґР°Р»С‘РЅ ({deleted_count} С‡Р°РЅРєРѕРІ)",
                "deleted_chunks": deleted_count,
            }
        else:
            return {
                "status": "ok",
                "message": f"Р”РѕРєСѓРјРµРЅС‚ '{filename}' РЅРµ РЅР°Р№РґРµРЅ РІ Р±Р°Р·Рµ, РЅРѕ С„Р°Р№Р» СѓРґР°Р»С‘РЅ СЃ РґРёСЃРєР°",
                "deleted_chunks": 0,
            }
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° СѓРґР°Р»РµРЅРёСЏ РґРѕРєСѓРјРµРЅС‚Р° '{filename}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reindex", tags=["Р”РѕРєСѓРјРµРЅС‚С‹"])
async def reindex():
    """
    Р СѓС‡РЅР°СЏ РїРµСЂРµРёРЅРґРµРєСЃР°С†РёСЏ РІСЃРµС… С„Р°Р№Р»РѕРІ РёР· РїР°РїРєРё documents/ (СЂРµРєСѓСЂСЃРёРІРЅРѕ).
    РџРµСЂРµСЃС‡РёС‚С‹РІР°РµС‚ РІСЃРµ РґРѕРєСѓРјРµРЅС‚С‹ Рё РѕР±РЅРѕРІР»СЏРµС‚ С‡Р°РЅРєРё РІ ChromaDB.
    """
    try:
        logger.info("POST /reindex вЂ” Р·Р°РїСѓСЃРє РїРѕР»РЅРѕР№ РїРµСЂРµРёРЅРґРµРєСЃР°С†РёРё")
        results = ingest_directory()
        reset_vectorstore_cache()

        total_chunks = sum(results.values())
        logger.info(f"POST /reindex вЂ” Р·Р°РІРµСЂС€РµРЅРѕ: {len(results)} С„Р°Р№Р»РѕРІ, {total_chunks} С‡Р°РЅРєРѕРІ")
        return {
            "status": "ok",
            "message": f"РџРµСЂРµРёРЅРґРµРєСЃР°С†РёСЏ Р·Р°РІРµСЂС€РµРЅР°: {len(results)} С„Р°Р№Р»РѕРІ, {total_chunks} С‡Р°РЅРєРѕРІ",
            "files": results,
            "total_chunks": total_chunks,
        }
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїРµСЂРµРёРЅРґРµРєСЃР°С†РёРё: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# === Р—Р°РїСѓСЃРє С‡РµСЂРµР· uvicorn ===
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
