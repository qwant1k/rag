"""
Retriever — поиск релевантных чанков в ChromaDB.
Возвращает топ-K документов по семантической близости к запросу.
"""

import logging
from langchain_chroma import Chroma
from langchain_core.documents import Document

from backend.config import TOP_K_RETRIEVE
from backend.ingestion import get_vectorstore, get_embeddings

logger = logging.getLogger("rag-chatbot")

# Кэшируем embeddings и vectorstore для переиспользования
_embeddings = None
_vectorstore = None


def _get_cached_vectorstore() -> Chroma:
    """Получение кэшированного vectorstore (создаётся один раз)."""
    global _embeddings, _vectorstore
    if _vectorstore is None:
        _embeddings = get_embeddings()
        _vectorstore = get_vectorstore(_embeddings)
        logger.info("Vectorstore инициализирован и закэширован")
    return _vectorstore


def reset_vectorstore_cache():
    """Сброс кэша vectorstore (нужен после загрузки новых документов)."""
    global _embeddings, _vectorstore
    _embeddings = None
    _vectorstore = None
    logger.info("Кэш vectorstore сброшен")


def get_retriever(top_k: int = TOP_K_RETRIEVE):
    """
    Создание retriever для поиска по ChromaDB.
    Возвращает LangChain-совместимый retriever с поиском по similarity.
    """
    vectorstore = _get_cached_vectorstore()
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": top_k},
    )
    logger.info(f"Retriever создан (top_k={top_k})")
    return retriever


def search_documents(query: str, top_k: int = TOP_K_RETRIEVE) -> list[Document]:
    """
    Прямой поиск документов по запросу.
    Возвращает список Document с метаданными (source, page).
    """
    vectorstore = _get_cached_vectorstore()
    try:
        results = vectorstore.similarity_search(query, k=top_k)
        logger.info(f"Поиск '{query[:50]}...': найдено {len(results)} результатов")
        return results
    except Exception as e:
        logger.error(f"Ошибка при поиске: {e}")
        return []


def search_with_scores(query: str, top_k: int = TOP_K_RETRIEVE) -> list[tuple[Document, float]]:
    """
    Поиск документов с оценкой релевантности.
    Возвращает список кортежей (Document, score).
    """
    vectorstore = _get_cached_vectorstore()
    try:
        results = vectorstore.similarity_search_with_score(query, k=top_k)
        logger.info(f"Поиск с оценками '{query[:50]}...': найдено {len(results)} результатов")
        return results
    except Exception as e:
        logger.error(f"Ошибка при поиске с оценками: {e}")
        return []


def format_sources(documents: list[Document]) -> list[dict]:
    """
    Форматирование источников из найденных документов.
    Возвращает уникальный список {filename, page} для отображения в UI.
    """
    seen = set()
    sources = []
    for doc in documents:
        source = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page", "?")
        key = f"{source}_p{page}"
        if key not in seen:
            seen.add(key)
            sources.append({
                "filename": source,
                "page": page,
                "snippet": doc.page_content[:150] + "..." if len(doc.page_content) > 150 else doc.page_content,
            })
    return sources
