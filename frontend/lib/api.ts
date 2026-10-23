import type {
  DemoScenario,
  DocumentDetail,
  DocumentsResponse,
  Health,
  QueryResult,
  SampleLoadResponse,
  ScenariosResponse,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE || "/backend";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: {
        ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...(init?.headers || {}),
      },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      "Could not reach the TruthGuard API. Start the backend on port 8000 and try again.",
    );
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      if (typeof payload.detail === "string") {
        message = payload.detail;
      } else if (Array.isArray(payload.detail)) {
        message = payload.detail
          .map((item: { msg?: string }) => item.msg || "Invalid request")
          .join("; ");
      }
    } catch {
      // Keep the status-based message.
    }
    throw new ApiError(message, response.status);
  }
  return (await response.json()) as T;
}

export function getHealth(): Promise<Health> {
  return request("/health");
}

export function getDocuments(): Promise<DocumentsResponse> {
  return request("/documents");
}

export function getDocument(id: string): Promise<DocumentDetail> {
  return request(`/documents/${encodeURIComponent(id)}`);
}

export function getScenarios(): Promise<ScenariosResponse> {
  return request("/demo/scenarios");
}

export function loadSampleCorpus(): Promise<SampleLoadResponse> {
  return request("/demo/load-sample", { method: "POST" });
}

export function askQuestion(question: string, asOf?: string): Promise<QueryResult> {
  return request("/query", {
    method: "POST",
    body: JSON.stringify({ question, as_of: asOf || null }),
  });
}

export function uploadDocument(formData: FormData): Promise<{ document: DocumentDetail; message: string }> {
  return request("/documents/upload", { method: "POST", body: formData });
}

export function deleteDocument(id: string): Promise<{ message: string; deleted_id: string }> {
  return request(`/documents/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export type { DemoScenario };
