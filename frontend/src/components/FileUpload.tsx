import { useState, useRef, useCallback } from "react";
import { Upload, X, FileText, Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { uploadFile } from "../api/client";

interface FileUploadProps {
  onUploadComplete: () => void;
}

type UploadStatus = "idle" | "uploading" | "success" | "error";

export default function FileUpload({ onUploadComplete }: FileUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [status, setStatus] = useState<UploadStatus>("idle");
  const [statusMessage, setStatusMessage] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const allowedExtensions = [".pdf", ".docx", ".doc", ".txt"];

  const handleUpload = useCallback(
    async (file: File) => {
      const ext = "." + file.name.split(".").pop()?.toLowerCase();
      if (!allowedExtensions.includes(ext)) {
        setStatus("error");
        setStatusMessage(`Неподдерживаемый формат: ${ext}. Допустимые: PDF, DOCX, DOC, TXT`);
        return;
      }

      setStatus("uploading");
      setStatusMessage(`Загрузка: ${file.name}...`);

      try {
        const result = await uploadFile(file);
        setStatus("success");
        setStatusMessage(result.message);
        onUploadComplete();

        // Сбрасываем статус через 3 секунды
        setTimeout(() => {
          setStatus("idle");
          setStatusMessage("");
        }, 3000);
      } catch (error) {
        setStatus("error");
        setStatusMessage(`${error}`);
      }
    },
    [onUploadComplete],
  );

  // Drag & Drop обработчики
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleUpload(file);
    },
    [handleUpload],
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleUpload(file);
      // Сбрасываем input чтобы можно было загрузить тот же файл повторно
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
    [handleUpload],
  );

  return (
    <div className="p-3">
      {/* Зона Drag & Drop */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-all ${
          isDragging
            ? "border-blue-500 bg-blue-500/10"
            : "border-gray-700 hover:border-gray-500 hover:bg-gray-800/50"
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.doc,.txt"
          onChange={handleFileSelect}
          className="hidden"
        />

        {status === "uploading" ? (
          <div className="flex flex-col items-center gap-2">
            <Loader2 size={24} className="text-blue-400 animate-spin" />
            <span className="text-sm text-gray-400">{statusMessage}</span>
          </div>
        ) : status === "success" ? (
          <div className="flex flex-col items-center gap-2">
            <CheckCircle2 size={24} className="text-green-400" />
            <span className="text-sm text-green-400">{statusMessage}</span>
          </div>
        ) : status === "error" ? (
          <div className="flex flex-col items-center gap-2">
            <AlertCircle size={24} className="text-red-400" />
            <span className="text-sm text-red-400">{statusMessage}</span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setStatus("idle");
                setStatusMessage("");
              }}
              className="text-xs text-gray-500 hover:text-gray-300"
            >
              Попробовать снова
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <Upload size={24} className="text-gray-500" />
            <span className="text-sm text-gray-400">
              Перетащите файл или нажмите
            </span>
            <span className="text-xs text-gray-600">PDF, DOCX, DOC, TXT</span>
          </div>
        )}
      </div>
    </div>
  );
}
