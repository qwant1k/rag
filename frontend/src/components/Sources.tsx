import { useState } from "react";
import { ChevronDown, ChevronUp, FileText } from "lucide-react";
import type { Source } from "../api/client";

interface SourcesProps {
  sources: Source[];
}

export default function Sources({ sources }: SourcesProps) {
  const [isOpen, setIsOpen] = useState(false);

  if (!sources || sources.length === 0) return null;

  return (
    <div className="mt-2">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-200 transition-colors"
      >
        {isOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        <span>Источники ({sources.length})</span>
      </button>

      {isOpen && (
        <div className="mt-2 space-y-1.5 pl-2 border-l-2 border-gray-700">
          {sources.map((source, index) => (
            <div
              key={index}
              className="flex items-start gap-2 text-sm text-gray-400 bg-gray-800/50 rounded px-3 py-2"
            >
              <FileText size={14} className="mt-0.5 shrink-0 text-blue-400" />
              <div>
                <span className="text-gray-300 font-medium">
                  {source.filename}
                </span>
                <span className="text-gray-500 ml-1.5">стр. {source.page}</span>
                {source.snippet && (
                  <p className="text-gray-500 text-xs mt-1 line-clamp-2">
                    {source.snippet}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
