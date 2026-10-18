import { apiFetch } from "./authApi";
import { SERVER_BASE_URL } from "./gradingApiBase";

export type DocumentType = "lecture" | "tutorial" | "exam";
export type CourseMaterial = {
  document_id: string; course_code: string; document_type: DocumentType; filename: string;
  year: number | null; pages: number; chunks: number; empty_pages: number[]; warnings: string[];
  mode: "hybrid" | "keyword"; pdf_available: boolean;
};
export type MaterialInventory = { status: "ok" | "unavailable"; items: CourseMaterial[]; warnings: string[] };
const BASE = `${SERVER_BASE_URL}/api/lecturers/materials`;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await apiFetch(`${BASE}${path}`, init);
  const data = await response.json();
  if (!response.ok) {
    const message = typeof data.detail === "string" ? data.detail : Array.isArray(data.detail)
      ? data.detail.map((item: { msg: string }) => item.msg).join("; ") : "Could not update course materials.";
    throw new Error(message);
  }
  return data;
}

export const listMaterials = () => request<MaterialInventory>("");
export const materialPdfUrl = (id: string) => `${BASE}/${encodeURIComponent(id)}/pdf`;
export function uploadMaterial(file: File, courseCode: string, type: DocumentType, year?: number) {
  const body = new FormData();
  body.append("file", file); body.append("course_code", courseCode); body.append("document_type", type);
  if (year !== undefined) body.append("year", String(year));
  return request<{ item: CourseMaterial; status: string }>("", { method: "POST", body });
}
export function replaceMaterial(id: string, file: File) {
  const body = new FormData(); body.append("file", file);
  return request<{ item: CourseMaterial; status: string }>(`/${encodeURIComponent(id)}`, { method: "PUT", body });
}
export const removeMaterial = (id: string) => request<{ removed: string }>(`/${encodeURIComponent(id)}`, { method: "DELETE" });
