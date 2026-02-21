const API_BASE = "http://localhost:8000";

export interface Source {
  filename: string;
  page: number | string;
  snippet?: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
}

export interface DocumentInfo {
  filename: string;
  chunks_count: number;
  pages: number[];
  upload_date: string;
}

export async function streamChat(
  question: string,
  chatHistory: ChatMessage[],
  onToken: (token: string) => void,
  onSources: (sources: Source[]) => void,
  onDone: () => void,
  onError: (error: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const history = chatHistory.map((msg) => ({ role: msg.role, content: msg.content }));

    const response = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, chat_history: history }),
      signal,
    });

    if (!response.ok) {
      const err = await response.text();
      onError(`Ошибка сервера: ${response.status} — ${err}`);
      return;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      onError("Не удалось получить ReadableStream");
      return;
    }

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data: ")) continue;

        const jsonStr = trimmed.slice(6);
        try {
          const event = JSON.parse(jsonStr);

          switch (event.type) {
            case "token":
              onToken(event.content);
              break;
            case "sources":
              onSources(event.content || []);
              break;
            case "done":
              onDone();
              break;
            case "error":
              onError(event.content);
              break;
          }
        } catch {
          // ignore invalid SSE chunks
        }
      }
    }
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      return;
    }
    onError(`Ошибка соединения: ${error}`);
  }
}

export async function uploadFile(
  file: File,
): Promise<{ status: string; filename: string; chunks_count: number; message: string }> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Ошибка загрузки: ${response.status} — ${err}`);
  }

  return response.json();
}

export async function getDocuments(): Promise<DocumentInfo[]> {
  const response = await fetch(`${API_BASE}/documents`);

  if (!response.ok) {
    throw new Error(`Ошибка получения документов: ${response.status}`);
  }

  const data = await response.json();
  return data.documents || [];
}

export async function reindexDocuments(): Promise<{
  status: string;
  message: string;
  files: Record<string, number>;
  total_chunks: number;
}> {
  const response = await fetch(`${API_BASE}/reindex`, {
    method: "POST",
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Ошибка переиндексации: ${response.status} — ${err}`);
  }

  return response.json();
}

export async function deleteDocument(
  filename: string,
): Promise<{ status: string; message: string; deleted_chunks: number }> {
  const response = await fetch(`${API_BASE}/documents/${encodeURIComponent(filename)}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Ошибка удаления: ${response.status} — ${err}`);
  }

  return response.json();
}
