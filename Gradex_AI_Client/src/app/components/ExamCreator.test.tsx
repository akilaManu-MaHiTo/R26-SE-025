// @vitest-environment jsdom
import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ExamCreator } from "./ExamCreator";
import { fetchExams, type ExamListItem } from "../api/lecturerApi";
import { generateExamQuestions, type Generation } from "../api/examCreatorApi";

vi.mock("../api/examCreatorApi", async importOriginal => ({
  ...await importOriginal<typeof import("../api/examCreatorApi")>(),
  generateExamQuestions: vi.fn(),
}));

vi.mock("../App", () => ({ useHideSidebar: () => undefined }));
vi.mock("thinking-orbs", () => ({ ThinkingOrb: ({ state }: { state: string }) => <span data-testid="thinking-orb" data-state={state} /> }));
vi.mock("./ExamCreatorAssistant", () => ({ ExamCreatorAssistant: () => <datalist id="creator-topics"><option value="Indexes" /></datalist>, PartReviewEditor: () => null }));
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

const generated: Generation = {
  candidates: [{ text: "Compare two database indexes.", topic: "Indexes", bloom_level: "Analyze", marks: 10,
    question_id: "generated-1", model_answer: "Compare lookup and write costs.", marking_scheme: [],
    estimated_minutes: 12, sources: [], review_status: "needs_review" }],
  similarity_available: true, similarity_checks: [], model: "test",
};

async function openGenerator() {
  await openEditor();
  fireEvent.change(screen.getByLabelText("Question 1 topic"), { target: { value: "Indexes" } });
  fireEvent.click(screen.getByRole("button", { name: "Generate Q1 part a with AI" }));
}

it("generates into the selected custom question and keeps it editable", async () => {
  vi.mocked(generateExamQuestions).mockResolvedValue(generated);
  await openGenerator();
  expect((screen.getByLabelText("Lecture topic") as HTMLInputElement).value).toBe("Indexes");
  expect(screen.getByLabelText("Lecture topic").getAttribute("list")).toBe("creator-topics");
  fireEvent.mouseDown(screen.getByRole("tab", { name: "Browse Bank" }), { button: 0, ctrlKey: false });
  expect(document.getElementById("creator-topics")?.querySelector("option")?.value).toBe("Indexes");
  fireEvent.change(screen.getByLabelText("Bloom level"), { target: { value: "Analyze" } });
  fireEvent.click(screen.getByRole("button", { name: "Generate question", exact: true }));
  await waitFor(() => expect((screen.getByLabelText("Q1 part a text") as HTMLTextAreaElement).value).toBe(generated.candidates[0].text));
  expect(generateExamQuestions).toHaveBeenCalledWith("IT2040", expect.any(Object), "Indexes", "Analyze", 10, expect.any(AbortSignal), 1);
  const context = vi.mocked(generateExamQuestions).mock.calls[0][1];
  expect(context.questions.flatMap(q => q.parts).map(p => p.question)).toEqual(["Second question"]);
  expect((screen.getByLabelText("Q2 part a text") as HTMLTextAreaElement).value).toBe("Second question");
  fireEvent.change(screen.getByLabelText("Q1 part a text"), { target: { value: "Edited generated question" } });
  expect((screen.getByLabelText("Q1 part a text") as HTMLTextAreaElement).value).toBe("Edited generated question");
});

it("requires a topic and preserves written text when generation fails", async () => {
  vi.mocked(generateExamQuestions).mockRejectedValue(new Error("Lecture material unavailable"));
  await openGenerator();
  fireEvent.change(screen.getByLabelText("Lecture topic"), { target: { value: "   " } });
  expect((screen.getByRole("button", { name: "Generate question", exact: true }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Lecture topic"), { target: { value: "Indexes" } });
  fireEvent.click(screen.getByRole("button", { name: "Generate question", exact: true }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Lecture material unavailable");
  expect((screen.getByLabelText("Q1 part a text") as HTMLTextAreaElement).value).toBe("First question");
});

it("discards generation if the question changes while waiting", async () => {
  let resolve!: (result: Generation) => void;
  vi.mocked(generateExamQuestions).mockImplementation(() => new Promise(done => { resolve = done; }));
  await openGenerator();
  fireEvent.click(screen.getByRole("button", { name: "Generate question", exact: true }));
  expect(screen.queryByLabelText("Lecture topic")).toBeNull();
  expect(screen.getByTestId("thinking-orb").getAttribute("data-state")).toBe("solving");
  expect((screen.getByRole("button", { name: "Generate Q1 part a with AI" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Q1 part a text"), { target: { value: "New lecturer text" } });
  await act(async () => resolve(generated));
  expect((screen.getByLabelText("Q1 part a text") as HTMLTextAreaElement).value).toBe("New lecturer text");
});

it("does not reclassify sibling parts when a different topic is entered", async () => {
  await openEditor();
  fireEvent.change(screen.getByLabelText("Question 1 topic"), { target: { value: "SQL" } });
  fireEvent.click(screen.getAllByRole("button", { name: "Add part", exact: true })[0]);
  fireEvent.click(screen.getByRole("button", { name: "Generate Q1 part a with AI" }));
  fireEvent.change(screen.getByLabelText("Lecture topic"), { target: { value: "Indexes" } });
  fireEvent.click(screen.getByRole("button", { name: "Generate question", exact: true }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Make this part a separate question before changing its topic.");
  expect(generateExamQuestions).not.toHaveBeenCalled();
  expect((screen.getByLabelText("Question 1 topic") as HTMLInputElement).value).toBe("SQL");
});
