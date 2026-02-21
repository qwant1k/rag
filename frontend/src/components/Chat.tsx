import { useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";
import Message from "./Message";
import { streamChat } from "../api/client";
import type { ChatMessage, Source } from "../api/client";

interface ChatProps {
  chatId: string;
  messages: ChatMessage[];
  onMessagesChange: (updater: (prev: ChatMessage[]) => ChatMessage[]) => void;
}

export default function Chat({ chatId, messages, onMessagesChange }: ChatProps) {
  const TYPEWRITER_INTERVAL_MS = 14;
  const CHARS_PER_TICK = 1;

  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const requestControllerRef = useRef<AbortController | null>(null);
  const tokenQueueRef = useRef("");
  const streamDoneRef = useRef(false);
  const typingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    inputRef.current?.focus();
  }, [isLoading, chatId]);

  useEffect(() => {
    if (typingTimerRef.current) {
      clearInterval(typingTimerRef.current);
      typingTimerRef.current = null;
    }
    tokenQueueRef.current = "";
    streamDoneRef.current = false;
    requestControllerRef.current?.abort();
    requestControllerRef.current = null;
    setIsLoading(false);
    setInput("");
  }, [chatId]);

  useEffect(() => {
    return () => {
      if (typingTimerRef.current) {
        clearInterval(typingTimerRef.current);
        typingTimerRef.current = null;
      }
      requestControllerRef.current?.abort();
      requestControllerRef.current = null;
    };
  }, []);

  const appendAssistantChunk = (chunk: string) => {
    onMessagesChange((prev) => {
      const updated = [...prev];
      const last = updated[updated.length - 1];
      if (last?.role === "assistant") {
        updated[updated.length - 1] = {
          ...last,
          content: last.content + chunk,
        };
      }
      return updated;
    });
  };

  const stopTypingTimer = () => {
    if (typingTimerRef.current) {
      clearInterval(typingTimerRef.current);
      typingTimerRef.current = null;
    }
  };

  const finalizeIfStreamFinished = () => {
    if (streamDoneRef.current && tokenQueueRef.current.length === 0) {
      stopTypingTimer();
      setIsLoading(false);
      requestControllerRef.current = null;
    }
  };

  const startTypewriter = () => {
    if (typingTimerRef.current) return;

    typingTimerRef.current = setInterval(() => {
      if (tokenQueueRef.current.length === 0) {
        finalizeIfStreamFinished();
        return;
      }

      const chunk = tokenQueueRef.current.slice(0, CHARS_PER_TICK);
      tokenQueueRef.current = tokenQueueRef.current.slice(CHARS_PER_TICK);
      appendAssistantChunk(chunk);
      finalizeIfStreamFinished();
    }, TYPEWRITER_INTERVAL_MS);
  };

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const question = input.trim();
    if (!question || isLoading) return;

    const controller = new AbortController();
    requestControllerRef.current = controller;
    tokenQueueRef.current = "";
    streamDoneRef.current = false;
    stopTypingTimer();

    const userMessage: ChatMessage = { role: "user", content: question };
    const assistantMessage: ChatMessage = { role: "assistant", content: "", sources: [] };

    onMessagesChange((prev) => [...prev, userMessage, assistantMessage]);
    setInput("");
    setIsLoading(true);

    await streamChat(
      question,
      messages,
      (token: string) => {
        if (controller.signal.aborted) return;
        tokenQueueRef.current += token;
        startTypewriter();
      },
      (sources: Source[]) => {
        if (controller.signal.aborted) return;

        onMessagesChange((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last?.role === "assistant") {
            updated[updated.length - 1] = { ...last, sources };
          }
          return updated;
        });
      },
      () => {
        if (controller.signal.aborted) return;
        streamDoneRef.current = true;
        finalizeIfStreamFinished();
      },
      (error: string) => {
        if (controller.signal.aborted) return;
        stopTypingTimer();
        tokenQueueRef.current = "";
        streamDoneRef.current = false;

        onMessagesChange((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last?.role === "assistant") {
            updated[updated.length - 1] = {
              ...last,
              content: `Ошибка: ${error}`,
            };
          }
          return updated;
        });

        setIsLoading(false);
        requestControllerRef.current = null;
      },
      controller.signal,
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center text-gray-500">
              <p className="text-xl mb-2">RAG Чат-бот</p>
              <p className="text-sm">Создайте новый диалог или задайте вопрос по документам</p>
            </div>
          </div>
        ) : (
          messages.map((msg, index) => (
            <Message
              key={index}
              message={msg}
              isLoading={isLoading && index === messages.length - 1 && msg.role === "assistant"}
            />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="border-t border-gray-800 p-4">
        <form onSubmit={handleSubmit} className="flex gap-3 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Задайте вопрос по документам..."
            disabled={isLoading}
            rows={1}
            className="flex-1 bg-gray-800 text-white rounded-xl px-4 py-3 resize-none placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-600 disabled:opacity-50 max-h-32 overflow-y-auto text-sm"
            style={{ minHeight: "48px" }}
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-xl p-3 transition-colors shrink-0"
          >
            <Send size={18} />
          </button>
        </form>
      </div>
    </div>
  );
}
