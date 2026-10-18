// @vitest-environment jsdom
import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ExamCreatorAssistant, PartReviewEditor } from "./ExamCreatorAssistant";
import { generateExamQuestions, reviewExamPaper } from "../api/examCreatorApi";

vi.mock("../api/examCreatorApi", async importOriginal => ({
  ...await importOriginal<typeof import("../api/examCreatorApi")>(),
  generateExamQuestions: vi.fn(), reviewExamPaper: vi.fn(),
}));
vi.mock("thinking-orbs", () => ({ ThinkingOrb: () => <span /> }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

it("keeps filename and page citations visible in a saved question", () => {
  render(<PartReviewEditor part={{ part: "a", question: "Question", max_marks: 10,
    sources: [{ source_id: "doc:p4:c0", kind: "lecture", text: "Normalization evidence",
      filename: "IT2040_Lecture03_2024.pdf", page_number: 4, course_code: "IT2040" }],
  }} onChange={vi.fn()} />);
  expect(screen.getByText(/IT2040_Lecture03_2024.pdf.*page 4/)).toBeTruthy();
  expect(screen.queryByText(/Lecturer notes: doc/)).toBeNull();
});

it("shows retrieval warnings even when question generation fails", async () => {
  vi.mocked(reviewExamPaper).mockResolvedValue({ topics: ["SQL"], analytics_available: true,
    recommendations: [], ranked_weak_topics: [], review: { total_marks: 0, remaining_marks: 100,
      estimated_minutes: 0, estimated_parts: 0, part_count: 0, topic_coverage: {}, bloom_coverage: {}, issues: [] },
  } as Awaited<ReturnType<typeof reviewExamPaper>>);
  const retrieval = { lectures: { status: "unavailable", mode: "unavailable", sources: [],
    warnings: ["Course material index is missing."] },
    assessment_examples: { status: "ok", mode: "keyword", sources: [], warnings: [] } };
  vi.mocked(generateExamQuestions).mockRejectedValue(Object.assign(new Error("Model unavailable"), { retrieval }));
  render(<ExamCreatorAssistant courseCode="IT2040" paper={{ exam: "DBMS", year: 2026, questions: [] }} setPaper={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("Topic"), { target: { value: "SQL" } });
  const generate = screen.getByRole("button", { name: "Generate 2 alternatives" });
  await waitFor(() => expect((generate as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(generate);
  expect(await screen.findByText("Model unavailable")).toBeTruthy();
  expect(screen.getByText("Course material index is missing.")).toBeTruthy();
});
