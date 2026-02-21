import { useEffect, useMemo, useState } from "react";
import {
  Database,
  FileText,
  Menu,
  MessageSquare,
  Plus,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react";
import Chat from "./components/Chat";
import FileUpload from "./components/FileUpload";
import { deleteDocument, getDocuments, reindexDocuments } from "./api/client";
import type { ChatMessage, DocumentInfo } from "./api/client";

interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: string;
  updatedAt: string;
}

const CHAT_STORAGE_KEY = "rag_chat_sessions_v1";
const ACTIVE_CHAT_STORAGE_KEY = "rag_active_chat_v1";
const DEFAULT_CHAT_TITLE = "Новый чат";

function createChatSession(): ChatSession {
  const now = new Date().toISOString();
  const id =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

  return {
    id,
    title: DEFAULT_CHAT_TITLE,
    messages: [],
    createdAt: now,
    updatedAt: now,
  };
}

function deriveChatTitle(messages: ChatMessage[]): string {
  const firstUser = messages.find((m) => m.role === "user" && m.content.trim());
  if (!firstUser) return DEFAULT_CHAT_TITLE;

  const oneLine = firstUser.content.replace(/\s+/g, " ").trim();
  if (oneLine.length <= 42) return oneLine;
  return `${oneLine.slice(0, 42)}...`;
}

export default function App() {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [deletingFile, setDeletingFile] = useState<string | null>(null);
  const [reindexing, setReindexing] = useState(false);

  const [chats, setChats] = useState<ChatSession[]>(() => {
    try {
      const raw = localStorage.getItem(CHAT_STORAGE_KEY);
      if (!raw) return [createChatSession()];
      const parsed = JSON.parse(raw) as ChatSession[];
      return parsed.length > 0 ? parsed : [createChatSession()];
    } catch {
      return [createChatSession()];
    }
  });

  const [activeChatId, setActiveChatId] = useState<string>(() => {
    const saved = localStorage.getItem(ACTIVE_CHAT_STORAGE_KEY);
    return saved || "";
  });

  useEffect(() => {
    if (!activeChatId && chats.length > 0) {
      setActiveChatId(chats[0].id);
      return;
    }

    const exists = chats.some((c) => c.id === activeChatId);
    if (!exists && chats.length > 0) {
      setActiveChatId(chats[0].id);
    }
  }, [activeChatId, chats]);

  useEffect(() => {
    localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(chats));
  }, [chats]);

  useEffect(() => {
    if (activeChatId) {
      localStorage.setItem(ACTIVE_CHAT_STORAGE_KEY, activeChatId);
    }
  }, [activeChatId]);

  const activeChat = useMemo(
    () => chats.find((c) => c.id === activeChatId) ?? chats[0],
    [chats, activeChatId],
  );

  const loadDocuments = async () => {
    try {
      const docs = await getDocuments();
      setDocuments(docs);
    } catch (error) {
      console.error("Ошибка загрузки документов:", error);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  const createNewChat = () => {
    const next = createChatSession();
    setChats((prev) => [next, ...prev]);
    setActiveChatId(next.id);
  };

  const removeChat = (chatId: string) => {
    setChats((prev) => {
      if (prev.length <= 1) {
        const fresh = createChatSession();
        setActiveChatId(fresh.id);
        return [fresh];
      }

      const filtered = prev.filter((c) => c.id !== chatId);
      if (activeChatId === chatId && filtered.length > 0) {
        setActiveChatId(filtered[0].id);
      }
      return filtered;
    });
  };

  const updateActiveChatMessages = (updater: (prev: ChatMessage[]) => ChatMessage[]) => {
    if (!activeChat) return;
    const chatId = activeChat.id;

    setChats((prev) =>
      prev.map((chat) => {
        if (chat.id !== chatId) return chat;

        const nextMessages = updater(chat.messages);
        return {
          ...chat,
          messages: nextMessages,
          title: deriveChatTitle(nextMessages),
          updatedAt: new Date().toISOString(),
        };
      }),
    );
  };

  const handleDelete = async (filename: string) => {
    if (!confirm(`Удалить документ "${filename}"?`)) return;

    setDeletingFile(filename);
    try {
      await deleteDocument(filename);
      await loadDocuments();
    } catch (error) {
      console.error("Ошибка удаления:", error);
      alert(`Ошибка удаления: ${error}`);
    } finally {
      setDeletingFile(null);
    }
  };

  return (
    <div className="flex h-screen bg-gray-900 text-white">
      <aside
        className={`${
          sidebarOpen ? "w-80" : "w-0"
        } transition-all duration-300 overflow-hidden bg-gray-950 border-r border-gray-800 flex flex-col shrink-0`}
      >
        <div className="p-4 border-b border-gray-800 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-lg font-semibold">
              <MessageSquare size={18} className="text-blue-400" />
              <span>Чаты</span>
            </div>
            <button
              onClick={createNewChat}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md bg-blue-600 hover:bg-blue-500 text-sm"
              title="Создать новый чат"
            >
              <Plus size={14} />
              Новый
            </button>
          </div>

          <div className="max-h-56 overflow-y-auto space-y-1">
            {chats.map((chat) => (
              <div
                key={chat.id}
                className={`group flex items-center gap-2 px-2 py-2 rounded-lg border transition-colors ${
                  chat.id === activeChat?.id
                    ? "bg-gray-800 border-gray-700"
                    : "bg-gray-900 border-transparent hover:bg-gray-800/70"
                }`}
              >
                <button
                  onClick={() => setActiveChatId(chat.id)}
                  className="flex-1 text-left min-w-0"
                >
                  <p className="text-sm truncate text-gray-200">{chat.title}</p>
                  <p className="text-xs text-gray-500">{chat.messages.length} сообщений</p>
                </button>
                <button
                  onClick={() => removeChat(chat.id)}
                  className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 p-1"
                  title="Удалить чат"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="px-4 py-3 border-b border-gray-800">
          <div className="flex items-center gap-2 text-base font-semibold">
            <Database size={18} className="text-blue-400" />
            <span>Документы</span>
          </div>
        </div>

        <FileUpload onUploadComplete={loadDocuments} />

        <div className="flex-1 overflow-y-auto px-3 pb-3">
          {documents.length === 0 ? (
            <p className="text-gray-600 text-sm text-center py-4">Нет загруженных документов</p>
          ) : (
            <div className="space-y-1.5">
              {documents.map((doc) => (
                <div
                  key={doc.filename}
                  className="group flex items-start gap-2 bg-gray-900 hover:bg-gray-800 rounded-lg px-3 py-2.5 transition-colors"
                >
                  <FileText size={16} className="mt-0.5 text-blue-400 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-300 truncate" title={doc.filename}>
                      {doc.filename}
                    </p>
                    <p className="text-xs text-gray-600">
                      {doc.chunks_count} чанков · {doc.pages.length} стр.
                    </p>
                  </div>
                  <button
                    onClick={() => handleDelete(doc.filename)}
                    disabled={deletingFile === doc.filename}
                    className="opacity-0 group-hover:opacity-100 text-gray-600 hover:text-red-400 transition-all p-1 shrink-0 disabled:animate-spin"
                    title="Удалить документ"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="p-3 border-t border-gray-800">
          <button
            onClick={async () => {
              setReindexing(true);
              try {
                const result = await reindexDocuments();
                await loadDocuments();
                alert(result.message);
              } catch (error) {
                alert(`Ошибка: ${error}`);
              } finally {
                setReindexing(false);
              }
            }}
            disabled={reindexing}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-sm text-gray-300 transition-colors mb-2"
          >
            <RefreshCw size={14} className={reindexing ? "animate-spin" : ""} />
            {reindexing ? "Переиндексация..." : "Переиндексировать"}
          </button>
          <p className="text-xs text-gray-600 text-center">
            {documents.length} документов · {documents.reduce((sum, d) => sum + d.chunks_count, 0)} чанков
          </p>
        </div>
      </aside>

      <main className="flex-1 flex flex-col min-w-0">
        <header className="flex items-center gap-3 px-4 py-3 border-b border-gray-800 bg-gray-900/80 backdrop-blur">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="text-gray-400 hover:text-white transition-colors p-1"
          >
            {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <div className="flex items-center gap-2 min-w-0">
            <MessageSquare size={20} className="text-blue-400" />
            <h1 className="font-semibold truncate">{activeChat?.title || "RAG Чат-бот"}</h1>
          </div>
          <span className="text-xs text-gray-600 ml-auto">Groq · llama-3.3-70b · ChromaDB</span>
        </header>

        <div className="flex-1 overflow-hidden">
          {activeChat && (
            <Chat
              chatId={activeChat.id}
              messages={activeChat.messages}
              onMessagesChange={updateActiveChatMessages}
            />
          )}
        </div>
      </main>
    </div>
  );
}
