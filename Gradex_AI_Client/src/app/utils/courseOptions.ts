import { SERVER_BASE_URL } from "../api/gradingApiBase";
import { apiFetch } from "../api/authApi";
export type CourseItem = {
  _id: string;
  code: string;
  name?: string;
  description?: string;
};

export const SAMPLE_COURSES: CourseItem[] = [
  {
    _id: "ObjectId(66a100000000000000000002)",
    code: "IT2040",
    name: "Database Management Systems",
    description: "Relational modeling, SQL, normalization, and transactions.",
  },
  {
    _id: "ObjectId(66a100000000000000000003)",
    code: "CS3010",
    name: "Operating Systems",
    description: "Processes, memory, scheduling, synchronization, and file systems.",
  },
];


/** Server root only — same as viva/diagram. Grading callers pass GRADING_API_BASE_URL explicitly. */
const DEFAULT_API_BASE_URL = SERVER_BASE_URL;

function parseApiError(data: unknown, fallback: string): string {
  if (data == null || typeof data !== "object") return fallback;
  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      if (item && typeof item === "object" && "msg" in item) {
        return String((item as { msg: string }).msg);
      }
      return String(item);
    });
    return parts.length ? parts.join("; ") : fallback;
  }
  return fallback;
}

async function readJsonResponse(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text.trim()) return {};
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text.slice(0, 200) };
  }
}

export async function fetchCourses(
  apiBaseUrl: string = DEFAULT_API_BASE_URL,
): Promise<CourseItem[]> {
  const response = await apiFetch(`${apiBaseUrl}/courses`);
  const data = (await readJsonResponse(response)) as { items?: CourseItem[] };

  if (!response.ok) {
    throw new Error(parseApiError(data, "Failed to load courses."));
  }

  return data.items ?? [];
}

export function formatCourseLabel(course: CourseItem): string {
  const name = (course.name || "").trim();
  if (!name || name === course.code) return course.code;
  return `${course.code} — ${name}`;
}