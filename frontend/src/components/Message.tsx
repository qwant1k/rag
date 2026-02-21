import { Bot, User } from "lucide-react";
import Sources from "./Sources";
import type { ChatMessage } from "../api/client";

interface MessageProps {
  message: ChatMessage;
  isLoading?: boolean;
}

export default function Message({ message, isLoading }: MessageProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      {/* Аватар */}
      <div
        className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
          isUser ? "bg-blue-600" : "bg-gray-700"
        }`}
      >
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>

      {/* Контент сообщения */}
      <div className={`max-w-[75%] ${isUser ? "items-end" : "items-start"}`}>
        <div
          className={`rounded-2xl px-4 py-2.5 ${
            isUser
              ? "bg-blue-600 text-white rounded-tr-sm"
              : "bg-gray-800 text-gray-100 rounded-tl-sm"
          }`}
        >
          {/* Индикатор загрузки */}
          {isLoading && !message.content ? (
            <div className="dot-animation flex gap-1.5 py-1">
              <span className="w-2 h-2 bg-gray-400 rounded-full inline-block" />
              <span className="w-2 h-2 bg-gray-400 rounded-full inline-block" />
              <span className="w-2 h-2 bg-gray-400 rounded-full inline-block" />
            </div>
          ) : (
            <div className="whitespace-pre-wrap break-words text-sm leading-relaxed">
              {message.content}
            </div>
          )}
        </div>

        {/* Источники — только для ответов бота */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <Sources sources={message.sources} />
        )}
      </div>
    </div>
  );
}
