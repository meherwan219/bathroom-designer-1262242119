/**
 * Thin fetch wrapper over the FastAPI backend.
 * Base URL comes from NEXT_PUBLIC_API_BASE_URL (see .env.example).
 */
import type {
  ChatResponse,
  ConfigFlags,
  DesignSpecPayload,
  FloorplanResponse,
  GenerateResponse,
} from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${path} failed: ${res.status} ${body}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  config: () => request<ConfigFlags>("/config"),
  extractFloorplan: (imageBase64: string) =>
    request<FloorplanResponse>("/vision/floorplan", {
      method: "POST",
      body: JSON.stringify({ image_base64: imageBase64 }),
    }),
  listProducts: (params: Record<string, string> = {}) =>
    request(`/catalog/products?${new URLSearchParams(params)}`),
  createDesign: (payload: DesignSpecPayload) =>
    request<{ id: string; status: string; spec: DesignSpecPayload }>("/designs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateSpec: (id: string, patch: Partial<DesignSpecPayload>) =>
    request<{ id: string; status: string; spec: DesignSpecPayload }>(
      `/designs/${id}/spec`,
      { method: "PATCH", body: JSON.stringify(patch) },
    ),
  generateDesign: (id: string) =>
    request<GenerateResponse>(`/designs/${id}/generate`, { method: "POST" }),
  selectAlternative: (id: string, rank: number) =>
    request<GenerateResponse>(`/designs/${id}/select/${rank}`, { method: "POST" }),
  chatModify: (id: string, message: string) =>
    request<ChatResponse>(`/designs/${id}/chat`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
};
