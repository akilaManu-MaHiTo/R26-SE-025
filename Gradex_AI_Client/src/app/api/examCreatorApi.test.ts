import { afterEach, expect, it, vi } from "vitest";
import { apiFetch } from "./authApi";
import { generateExamQuestions, reviewExamPaper } from "./examCreatorApi";

vi.mock("./authApi", () => ({ apiFetch: vi.fn() }));
afterEach(() => vi.clearAllMocks());

it("preserves retrieval diagnostics when the generator API returns a model failure", async () => {
  const retrieval = {
    lectures: { status: "ok", mode: "hybrid", sources: [], warnings: [] },
    assessment_examples: { status: "ok", mode: "hybrid", sources: [], warnings: [] },
  };
  vi.mocked(apiFetch).mockResolvedValue(new Response(JSON.stringify({ detail: { message: "Model timed out", retrieval } }), { status: 503 }));
  await expect(generateExamQuestions("IT2040", { exam: "DBMS", year: 2026, questions: [] }, "SQL", "Apply", 10))
    .rejects.toMatchObject({ message: "Model timed out", retrieval });
});

it("continues to show the API's existing plain validation errors", async () => {
  vi.mocked(apiFetch).mockResolvedValue(new Response(JSON.stringify({ detail: "No lecture evidence found" }), { status: 422 }));
  await expect(reviewExamPaper("IT2040", { exam: "DBMS", year: 2026, questions: [] }))
    .rejects.toThrow("No lecture evidence found");
});
