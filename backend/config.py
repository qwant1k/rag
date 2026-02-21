"""Application configuration for RAG chatbot."""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def _configure_utf8_console() -> None:
    """Force UTF-8 for console streams (especially on Windows)."""
    if os.name == "nt":
        # Best-effort switch code page to UTF-8 for current console session.
        os.system("chcp 65001 > nul")

    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


_configure_utf8_console()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)
logger = logging.getLogger("rag-chatbot")

# Project root directory (one level above backend/)
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env
env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(env_path)
    logger.info(f"Загружен .env файл: {env_path}")
else:
    logger.warning(f".env файл не найден по пути: {env_path}")

# API keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    logger.warning("GROQ_API_KEY не задан! Установите его в .env файле.")

# Paths
DOCUMENTS_DIR = BASE_DIR / "documents"
CHROMA_DB_DIR = BASE_DIR / "chroma_db"

DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)

# Embeddings
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")

# Chunking
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))

# RAG
TOP_K_RETRIEVE = int(os.getenv("TOP_K_RETRIEVE", "5"))
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "12"))

# LLM
LLM_MODEL = os.getenv("LLM_MODEL", "qwen-qwq-32b")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.55"))

# OCR
TESSERACT_CMD = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")

# Chroma collection
CHROMA_COLLECTION_NAME = "rag_documents"

logger.info(f"Директория документов: {DOCUMENTS_DIR}")
logger.info(f"Директория ChromaDB: {CHROMA_DB_DIR}")
logger.info(f"Модель эмбеддингов: {EMBEDDING_MODEL}")
logger.info(f"Размер чанка: {CHUNK_SIZE}, перекрытие: {CHUNK_OVERLAP}")
logger.info(f"Top-K результатов: {TOP_K_RETRIEVE}")
logger.info(f"LLM модель: {LLM_MODEL}")
