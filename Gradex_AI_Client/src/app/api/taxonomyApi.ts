import type { CourseItem } from "../utils/courseOptions";

const env = (import.meta as { env?: Record<string, string> }).env ?? {};
const API_BASE = (env.VITE_BACKEND_URL || env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export interface TaxonomyTopic {
  canonical_topic: string;
  aliases: string[];
  subtopics: string[];
}

export interface TaxonomyDocument {
  course_code: string;
  version: number;
  topics: Record<string, TaxonomyTopic>;
  updated_at: string | null;
}

export interface TaxonomyVersion {
  version: number;
  updated_at: string | null;
  updated_by: string | null;
}

async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}/api/courses${path}`, {
    method: body === undefined ? "GET" : "PUT",
    headers: {
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...(env.VITE_GRADEX_API_KEY ? { "X-API-Key": env.VITE_GRADEX_API_KEY } : {}),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const data = await response.json();
  if (!response.ok) {
    const message = typeof data.detail === "string" ? data.detail : "Could not load or save taxonomy. Check the topic fields.";
    throw new Error(message);
  }
  return data;
}

export const fetchTaxonomyCourses = async () =>
  (await request<{ items: CourseItem[] }>("")).items;

export const fetchTaxonomy = (courseCode: string, version?: number) =>
  request<TaxonomyDocument>(`/${encodeURIComponent(courseCode)}/taxonomy${version === undefined ? "" : `/history/${version}`}`);

export const fetchTaxonomyHistory = (courseCode: string) => request<TaxonomyVersion[]>(`/${encodeURIComponent(courseCode)}/taxonomy/history`);

export const saveTaxonomy = (courseCode: string, document: TaxonomyDocument) =>
  request<TaxonomyDocument>(`/${encodeURIComponent(courseCode)}/taxonomy`, { version: document.version, topics: document.topics });
