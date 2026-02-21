"""
Watchdog-мониторинг папки documents/.
При добавлении, изменении или удалении файлов автоматически
обновляет индекс в ChromaDB.

Поддерживаемые события:
  - Создание файла → индексация
  - Изменение файла → переиндексация (дедупликация встроена)
  - Удаление файла → удаление чанков из ChromaDB
  - Перемещение файла → удаление старого + индексация нового
"""

import logging
import threading
import time
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from backend.config import DOCUMENTS_DIR
from backend.ingestion import (
    ingest_file,
    delete_document_from_db,
    get_vectorstore,
    get_embeddings,
    get_relative_source,
)
from backend.retriever import reset_vectorstore_cache

logger = logging.getLogger("rag-chatbot")

# Поддерживаемые расширения
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}

# Задержка перед индексацией (секунды) — даём файлу полностью записаться
DEBOUNCE_DELAY = 3.0

# Глобальный lock — предотвращаем одновременные операции с ChromaDB и embeddings
_processing_lock = threading.Lock()


def _is_supported(path: Path) -> bool:
    """Проверяет что файл поддерживаемый и не временный."""
    # Игнорируем временные файлы Word (~$filename.doc) и скрытые файлы
    if path.name.startswith("~$") or path.name.startswith("."):
        return False
    return path.suffix.lower() in ALLOWED_EXTENSIONS


class DocumentEventHandler(FileSystemEventHandler):
    """
    Обработчик событий файловой системы для папки documents/.
    Использует debounce — откладывает индексацию на DEBOUNCE_DELAY секунд,
    чтобы файл успел полностью записаться на диск.
    """

    def __init__(self):
        super().__init__()
        # Таймеры для debounce — {путь_файла: Timer}
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def _debounce(self, key: str, callback, *args):
        """Откладывает вызов callback на DEBOUNCE_DELAY секунд. Повторный вызов сбрасывает таймер."""
        with self._lock:
            if key in self._timers:
                self._timers[key].cancel()
            timer = threading.Timer(DEBOUNCE_DELAY, callback, args=args)
            self._timers[key] = timer
            timer.start()

    def _index_file(self, file_path: Path):
        """Индексация одного файла в ChromaDB (thread-safe)."""
        with _processing_lock:
            try:
                # Проверяем что файл всё ещё существует (мог быть удалён за время debounce)
                if not file_path.exists():
                    return
                source_name = get_relative_source(file_path)
                logger.info(f"[Watcher] Индексация файла: {source_name}")
                embeddings = get_embeddings()
                vectorstore = get_vectorstore(embeddings)
                chunks_count = ingest_file(file_path, vectorstore)
                reset_vectorstore_cache()
                logger.info(f"[Watcher] ✅ {source_name}: {chunks_count} чанков добавлено")
            except Exception as e:
                logger.error(f"[Watcher] Ошибка индексации {file_path.name}: {e}")

    def _delete_file(self, file_path: Path):
        """Удаление чанков файла из ChromaDB (thread-safe)."""
        with _processing_lock:
            try:
                source_name = get_relative_source(file_path)
                logger.info(f"[Watcher] Удаление из индекса: {source_name}")
                deleted = delete_document_from_db(source_name)
                reset_vectorstore_cache()
                logger.info(f"[Watcher] 🗑️ {source_name}: удалено {deleted} чанков")
            except Exception as e:
                logger.error(f"[Watcher] Ошибка удаления {file_path.name}: {e}")

    def on_created(self, event: FileSystemEvent):
        """Файл создан — индексируем с задержкой."""
        if event.is_directory:
            return
        path = Path(event.src_path)
        if _is_supported(path):
            self._debounce(str(path), self._index_file, path)

    def on_modified(self, event: FileSystemEvent):
        """Файл изменён — переиндексируем с задержкой (дедупликация встроена)."""
        if event.is_directory:
            return
        path = Path(event.src_path)
        if _is_supported(path):
            self._debounce(str(path), self._index_file, path)

    def on_deleted(self, event: FileSystemEvent):
        """Файл удалён — удаляем чанки из ChromaDB."""
        if event.is_directory:
            return
        path = Path(event.src_path)
        if _is_supported(path):
            self._debounce(str(path), self._delete_file, path)

    def on_moved(self, event: FileSystemEvent):
        """Файл перемещён/переименован — удаляем старый, индексируем новый."""
        if event.is_directory:
            return
        old_path = Path(event.src_path)
        new_path = Path(event.dest_path)

        if _is_supported(old_path):
            self._debounce(str(old_path), self._delete_file, old_path)
        if _is_supported(new_path):
            self._debounce(str(new_path), self._index_file, new_path)


# === Глобальный observer ===
_observer: Observer | None = None


def start_watcher():
    """Запуск watchdog-мониторинга папки documents/."""
    global _observer

    if _observer is not None:
        logger.warning("[Watcher] Уже запущен")
        return

    # Создаём папку если не существует
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)

    handler = DocumentEventHandler()
    _observer = Observer()
    # recursive=True — мониторим вложенные папки тоже
    _observer.schedule(handler, str(DOCUMENTS_DIR), recursive=True)
    _observer.daemon = True  # Завершается вместе с основным процессом
    _observer.start()

    logger.info(f"[Watcher] 👁️ Мониторинг папки: {DOCUMENTS_DIR} (рекурсивно)")


def stop_watcher():
    """Остановка watchdog-мониторинга."""
    global _observer

    if _observer is None:
        return

    _observer.stop()
    _observer.join(timeout=5)
    _observer = None
    logger.info("[Watcher] Мониторинг остановлен")
