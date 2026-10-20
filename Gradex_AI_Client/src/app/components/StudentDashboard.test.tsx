// @vitest-environment jsdom
import React from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { StudentDashboard } from "./StudentDashboard";
import * as api from "../api/studentApi";
import { Sidebar } from "./Sidebar";

vi.mock("../routeConfig", () => ({ AGENT_CONFIG: [] }));
vi.mock("./BrandOrb", () => ({ BrandOrb: ({ state }: { state: string }) => <span data-testid="practice-orb" data-state={state} /> }));

vi.mock("../api/studentApi", () => ({
  fetchStudentProfile: vi.fn(), fetchStudentExams: vi.fn(), fetchStudentDashboard: vi.fn(),
  fetchStudentMaterials: vi.fn(), fetchStudentPractice: vi.fn(), studentMaterialPdfUrl: () => "/study.pdf",
}));

const exam = { subject_code: "IT2040", subject_name: "Database Systems", session_name: "Final", year: 2024, month: 6, semester: 1, question_count: 1, analyzed: true };
const analytics = {
  ...exam, student_id: "S1", overall_performance: { score: 4, maximum: 10, percentage: 40, status: "Needs Improvement" },
  question_performance: [{ question_id: "q1", question_no: "1", question_text: "Explain normalization", topic: "Normalization", subtopic: "3NF",
    bloom_analysis: { level: "Apply", confidence: 1, reason: "Application" }, performance: { score: 4, max_score: 10, percentage: 40 },
    criteria_performance: [{ criterion: "Identify transitive dependency", max_marks: 3, awarded_marks: 0, achieved: false }] }],
  topic_performance: [{ topic: "Normalization", questions_attempted: 1, score: 4, max_score: 10, percentage: 40, status: "Needs Improvement" }],
  bloom_performance: [{ level: "Apply", questions_attempted: 1, average_score: 40, status: "Needs Improvement" }],
  learning_analysis: { overall_performance: "Needs Improvement", strong_topics: ["SQL"], developing_topics: [], weak_topics: ["Normalization"], critical_topics: [], learning_gaps: [{ topic: "Normalization", subtopic: "3NF", priority: "High" }] },
  recommendations: [{ topic: "Normalization", priority: "High", action: "Review functional dependencies before decomposing relations." }],
  next_question_strategy: { recommended_topics: ["Normalization"], recommended_bloom_levels: ["Apply"], recommended_difficulty: "Easy", number_of_questions: 1 },
  generated_at: "2024-06-20T00:00:00Z", analysis_version: "1", model_metadata: { bloom_model: "x", bloom_model_type: "x", grading_source: "x", rag_context_used: false },
};

beforeEach(() => {
  vi.mocked(api.fetchStudentProfile).mockResolvedValue({ student_id: "S1", email: "real@example.test", exam_count: 1, exams: [exam] });
  vi.mocked(api.fetchStudentDashboard).mockResolvedValue(analytics);
  vi.mocked(api.fetchStudentMaterials).mockResolvedValue({ status: "ok", warnings: [], items: [] });
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });

function show(view: "dashboard" | "profile" | "materials" | "practice" = "dashboard") {
  return render(<MemoryRouter><StudentDashboard studentId="S1" view={view} /></MemoryRouter>);
}

it("turns findings into a study-next action and never generates practice on page load", async () => {
  show();
  expect(await screen.findByRole("heading", { name: "Study next" })).toBeTruthy();
  expect(screen.getByText(analytics.recommendations[0].action)).toBeTruthy();
  expect(api.fetchStudentPractice).not.toHaveBeenCalled();
});

it("shows evidence and student details on the profile", async () => {
  show("profile");
  expect(await screen.findByText("Identify transitive dependency")).toBeTruthy();
  expect(screen.getByText("real@example.test")).toBeTruthy();
  expect(screen.getByText("Explain normalization")).toBeTruthy();
});

it("lets students find and open study materials", async () => {
  vi.mocked(api.fetchStudentMaterials).mockResolvedValue({ status: "ok", warnings: [], items: [{ document_id: "a", filename: "Normalization.pdf", course_code: "IT2040", document_type: "lecture", year: 2024, pages: 5, chunks: 5, empty_pages: [], warnings: [], mode: "keyword", pdf_available: true }] });
  show("materials");
  expect(await screen.findByRole("link", { name: "Open Normalization.pdf" })).toBeTruthy();
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "missing" } });
  expect(screen.queryByRole("link", { name: "Open Normalization.pdf" })).toBeNull();
});

it("requests practice only on click using the complete exam identity", async () => {
  vi.mocked(api.fetchStudentPractice).mockResolvedValue({ questions: [{ prompt: "Decompose this relation into 3NF.", topic: "Normalization", difficulty: "Easy", bloom_level: "Apply", hints: ["Find the dependencies."] }], generated_at: "2024-06-20" });
  show("practice");
  const button = await screen.findByRole("button", { name: "Generate practice questions" });
  fireEvent.click(button);
  expect(await screen.findByText("Decompose this relation into 3NF.")).toBeTruthy();
  expect(api.fetchStudentPractice).toHaveBeenCalledWith("S1", exam);
  fireEvent.click(screen.getByText("Show hints"));
  expect(screen.getByText("Find the dependencies.")).toBeTruthy();
});

it("keeps course resources reachable when the latest exam is pending", async () => {
  vi.mocked(api.fetchStudentProfile).mockResolvedValue({ student_id: "S1", email: "real@example.test", exam_count: 1, exams: [{ ...exam, analyzed: false }] });
  show();
  expect(await screen.findByText("Waiting for lecturer analysis")).toBeTruthy();
  expect(screen.getByRole("link", { name: "Browse study materials" })).toBeTruthy();
  expect(api.fetchStudentDashboard).not.toHaveBeenCalled();
});

it("preserves the selected exam when using sidebar navigation", () => {
  render(<MemoryRouter initialEntries={["/student-profile?exam=IT2040%40Final%402024-6-1"]}><Sidebar role="student" email="s@example.test" onLogout={() => {}} /></MemoryRouter>);
  expect(screen.getByRole("link", { name: "Practice" }).getAttribute("href")).toBe("/student-practice?exam=IT2040%40Final%402024-6-1");
});

it("does not display results returned for another exam", async () => {
  vi.mocked(api.fetchStudentDashboard).mockResolvedValue({ ...analytics, year: 2023 });
  show();
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "The returned results do not match this exam. Please retry.");
  expect(screen.queryByRole("heading", { name: "Study next" })).toBeNull();
});

it("ignores a late analytics response after switching exams", async () => {
  const olderExam = { ...exam, year: 2023 };
  let finishFirst!: (value: typeof analytics) => void;
  vi.mocked(api.fetchStudentProfile).mockResolvedValue({ student_id: "S1", email: "real@example.test", exam_count: 2, exams: [exam, olderExam] });
  vi.mocked(api.fetchStudentDashboard).mockImplementationOnce(() => new Promise(resolve => { finishFirst = resolve; }))
    .mockResolvedValueOnce({ ...analytics, year: 2023, recommendations: [{ topic: "SQL", priority: "High", action: "Older exam revision plan" }] });
  show();
  await waitFor(() => expect(api.fetchStudentDashboard).toHaveBeenCalledTimes(1));
  fireEvent.change(screen.getByLabelText("Selected exam"), { target: { value: "IT2040@Final@2023-6-1" } });
  await screen.findByText("Older exam revision plan");
  finishFirst(analytics);
  await waitFor(() => expect(screen.queryByText(analytics.recommendations[0].action)).toBeNull());
  expect(screen.getByText("Older exam revision plan")).toBeTruthy();
});

it("shows a practice failure without losing the revision context", async () => {
  vi.mocked(api.fetchStudentPractice).mockRejectedValue(new Error("Practice is temporarily unavailable"));
  show("practice");
  fireEvent.click(await screen.findByRole("button", { name: "Generate practice questions" }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Practice is temporarily unavailable");
  expect(screen.getByRole("button", { name: "Generate practice questions" }).hasAttribute("disabled")).toBe(false);
  expect(screen.getByRole("link", { name: "Browse study materials" })).toBeTruthy();
});

it("replaces the practice button mascot with a solving orb while generating", async () => {
  let finish!: (value: api.StudentPractice) => void;
  vi.mocked(api.fetchStudentPractice).mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  show("practice");
  const button = await screen.findByRole("button", { name: "Generate practice questions" });
  expect(button.querySelector("img")?.getAttribute("src")).toContain("bloub-cercle-surpris-turquoise-anime.svg");
  expect(button.querySelector("svg")).toBeNull();
  fireEvent.click(button);
  expect(button.getAttribute("aria-busy")).toBe("true");
  expect(button.hasAttribute("disabled")).toBe(true);
  expect(screen.getByTestId("practice-orb").getAttribute("data-state")).toBe("solving");
  expect(button.querySelector("img")).toBeNull();
  await act(async () => { finish({ questions: [], generated_at: "2024-06-20" }); });
  expect(button.getAttribute("aria-busy")).toBe("false");
  expect(button.querySelector("img")).toBeTruthy();
  expect(screen.queryByTestId("practice-orb")).toBeNull();
});
