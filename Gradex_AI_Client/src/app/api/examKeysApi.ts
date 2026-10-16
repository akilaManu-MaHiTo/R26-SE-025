import { apiFetch } from "./authApi";
import { SERVER_BASE_URL } from "./gradingApiBase";
import type { ExamKeyLookupResponse } from "./diagramEvaluationApi";

export interface ExamKeyRecord extends ExamKeyLookupResponse {
  subjectName: string;
  examStructure: string[];
}
export type ExamKeyInput = Omit<ExamKeyRecord, "examKey">;

async function request<T>(body?: ExamKeyInput): Promise<T> {
  const response = await apiFetch(`${SERVER_BASE_URL}/api/exam-keys`, body ? {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  } : undefined);
  const data = await response.json();
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === "string" ? detail : Array.isArray(detail)
      ? detail.map((item: { msg: string }) => item.msg).join("; ")
      : "Could not load or save exam keys. Please retry.");
  }
  return data;
}

export const fetchExamKeys = () => request<ExamKeyRecord[]>();
export const createExamKey = (exam: ExamKeyInput) => request<ExamKeyRecord>(exam);
