// @vitest-environment jsdom
import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ExamCreator } from "./ExamCreator";
import { fetchExams, type ExamListItem } from "../api/lecturerApi";

vi.mock("../App", () => ({ useHideSidebar: () => undefined }));
vi.mock("thinking-orbs", () => ({ ThinkingOrb: () => <span /> }));
vi.mock("./ExamCreatorAssistant", () => ({ ExamCreatorAssistant: () => null, PartReviewEditor: () => null }));
vi.mock("../api/lecturerApi", async importOriginal => ({
  ...await importOriginal<typeof import("../api/lecturerApi")>(),
  fetchExams: vi.fn(),
  listExamDrafts: async () => [],
}));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

it.each([
  [null, null, "Avg N/A · Pass N/A"],
  [62.34, null, "Avg 62.3% · Pass N/A"],
  [null, 80, "Avg N/A · Pass 80%"],
  [0, 0, "Avg 0.0% · Pass 0%"],
  [62.34, 79.6, "Avg 62.3% · Pass 80%"],
])("renders exam inventory with average %s and pass rate %s", async (average, passRate, label) => {
  vi.mocked(fetchExams).mockResolvedValue([{
    course_code: "IT2040", subject_name: "Database Systems", session_name: "Final",
    year: 2026, month: 7, semester: 1, student_count: 1,
    average_percentage: average, pass_rate: passRate,
  } as ExamListItem]);
  render(<ExamCreator />);
  expect(await screen.findByText(label)).toBeTruthy();
  expect(screen.getByText("IT2040 — Final")).toBeTruthy();
});

async function openEditor() {
  vi.mocked(fetchExams).mockResolvedValue([{
    course_code: "IT2040", subject_name: "Database Systems", session_name: "Final",
    year: 2026, month: 7, semester: 1, student_count: 1,
    average_percentage: 60, pass_rate: 80,
  } as ExamListItem]);
  render(<ExamCreator />);
  fireEvent.click(await screen.findByText("IT2040 — Final"));
  fireEvent.click(screen.getByRole("button", { name: "Add Custom Question" }));
  fireEvent.change(screen.getByLabelText("Q1 part a text"), { target: { value: "First question" } });
  fireEvent.click(screen.getByRole("button", { name: "Add Custom Question" }));
  fireEvent.change(screen.getByLabelText("Q2 part a text"), { target: { value: "Second question" } });
}

it("reorders questions using buttons and undo, without losing text", async () => {
  await openEditor();
  fireEvent.click(screen.getByRole("button", { name: "Move question 1 down" }));
  expect((screen.getByLabelText("Q1 part a text") as HTMLTextAreaElement).value).toBe("Second question");
  fireEvent.click(screen.getByRole("button", { name: "Undo move / add" }));
  expect((screen.getByLabelText("Q1 part a text") as HTMLTextAreaElement).value).toBe("First question");
});

it("shows destinations during a drag and moves the question on drop", async () => {
  await openEditor();
  const dataTransfer = { setData: vi.fn(), effectAllowed: "", dropEffect: "" };
  fireEvent.dragStart(screen.getByRole("button", { name: "Drag question 1" }), { dataTransfer });
  const destination = screen.getByText("Add new question at end");
  fireEvent.dragOver(destination, { dataTransfer });
  fireEvent.drop(destination, { dataTransfer });
  expect((screen.getByLabelText("Q2 part a text") as HTMLTextAreaElement).value).toBe("First question");
  expect(screen.queryByText("Add new question at end")).toBeNull();
  fireEvent.change(screen.getByLabelText("Q2 part a text"), { target: { value: "Edited after move" } });
  expect((screen.getByRole("button", { name: "Undo move / add" }) as HTMLButtonElement).disabled).toBe(true);
});
