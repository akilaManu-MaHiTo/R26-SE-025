// @vitest-environment jsdom
import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ExamPaperModal } from "./ExamPaperModal";
import { fetchExamPaperDefinition, type ExamListItem } from "../../api/lecturerApi";

vi.mock("../../api/lecturerApi", () => ({ fetchExamPaperDefinition: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });
const exam = { course_code: "IT2040", session_name: "Final Examination", year: 2025, month: 4, semester: 1 } as ExamListItem;
const paper = {
  maximum_marks: 55, expected_structure: ["Essay", "Diagram"],
  essay_questions: [{ question_no: "01", question_text: "Explain normalization", max_marks: 35, criteria: [{ point: "Explain dependencies", marks: 35 }] }],
  diagram_rubrics: [{ rubric_id: "r1", exam_code: "ERD-004", total_marks: 20, criteria: [{ id: 1, criterion: "Entities", description: "Identify entities", marks: 20, expected: { entity: "Book" } }] }],
  validation: { status: "incomplete", messages: ["Original diagram question wording is missing."] },
};

it("loads the selected exam and shows question definitions, both rubrics and missing wording", async () => {
  vi.mocked(fetchExamPaperDefinition).mockResolvedValue(paper as any);
  render(<ExamPaperModal exam={exam} open onClose={() => {}} />);
  expect(await screen.findByText("Explain normalization")).toBeTruthy();
  expect(screen.getByText(/Explain dependencies/)).toBeTruthy();
  expect(screen.getByText("Identify entities")).toBeTruthy();
  expect(screen.getByText("Verified maximum: 55 marks")).toBeTruthy();
  expect(screen.getByText("Original diagram question wording is missing.")).toBeTruthy();
  expect(fetchExamPaperDefinition).toHaveBeenCalledWith(exam);
});

it("offers retry after a failed read", async () => {
  vi.mocked(fetchExamPaperDefinition).mockRejectedValueOnce(new Error("Unavailable")).mockResolvedValue(paper as any);
  render(<ExamPaperModal exam={exam} open onClose={() => {}} />);
  expect(await screen.findByRole("alert")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByText("Explain normalization")).toBeTruthy();
});

it("ignores a response from the previously selected exam", async () => {
  let finish!: (value: any) => void;
  vi.mocked(fetchExamPaperDefinition).mockReturnValueOnce(new Promise(resolve => { finish = resolve; })).mockResolvedValueOnce({ ...paper, essay_questions: [] } as any);
  const view = render(<ExamPaperModal exam={exam} open onClose={() => {}} />);
  view.rerender(<ExamPaperModal exam={{ ...exam, year: 2027 }} open onClose={() => {}} />);
  await screen.findByText("No essay question definitions available.");
  finish(paper);
  await Promise.resolve();
  expect(screen.queryByText("Explain normalization")).toBeNull();
});
