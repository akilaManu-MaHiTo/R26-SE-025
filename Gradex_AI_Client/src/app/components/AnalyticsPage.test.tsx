// @vitest-environment jsdom
import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation, useNavigate } from "react-router";
import AnalyticsPage from "./AnalyticsPage";
import { fetchExams, fetchExamAnalyticsStream, fetchExamStudents } from "../api/lecturerApi";
import { TeachingActions } from "./analytics/TeachingActions";
import { QuestionPerformanceTable } from "./analytics/QuestionPerformanceTable";

vi.mock("../api/lecturerApi", async importOriginal => ({ ...await importOriginal<typeof import("../api/lecturerApi")>(), fetchExams: vi.fn(), fetchExamAnalyticsStream: vi.fn(), fetchExamStudents: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

const exam = {
  course_code: "IT2040", subject_name: "Database Systems", session_name: "Final",
  year: 2026, month: 7, semester: 1, total_marks: 100, question_count: 5,
  student_count: 0, average_score: null, average_percentage: null, highest_score: null,
  lowest_score: null, pass_rate: null, analyzed: false, analyzed_at: null,
};
const examQuery = "course=IT2040&session=Final&year=2026&month=7&semester=1";

function NavigationHarness() {
  const location = useLocation();
  const navigate = useNavigate();
  return <>
    <output aria-label="Current URL">{location.pathname}{location.search}</output>
    <button onClick={() => navigate(-1)}>Browser back</button>
    <button onClick={() => navigate(1)}>Browser forward</button>
    <AnalyticsPage />
  </>;
}

function renderNavigation(entry = "/question-exam/analytics") {
  vi.mocked(fetchExams).mockResolvedValue([exam]);
  vi.mocked(fetchExamAnalyticsStream).mockReturnValue(new Promise(() => {}));
  vi.mocked(fetchExamStudents).mockResolvedValue([]);
  return render(<MemoryRouter initialEntries={[entry]}><NavigationHarness /></MemoryRouter>);
}

it("puts the full exam identity in the URL and follows browser back and forward", async () => {
  renderNavigation();
  fireEvent.click(await screen.findByRole("link", { name: /View analytics.*IT2040/ }));
  expect(screen.getByLabelText("Current URL").textContent).toBe(`/question-exam/analytics?${examQuery}`);
  expect(await screen.findByRole("button", { name: /Reanalyse$/ })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Browser back" }));
  expect(await screen.findByRole("link", { name: /View analytics.*IT2040/ })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Browser forward" }));
  expect(await screen.findByRole("button", { name: /Reanalyse$/ })).toBeTruthy();
});

it("opens a student deep link and keeps exam context when navigating up", async () => {
  renderNavigation(`/question-exam/analytics?${examQuery}&student=S001`);
  expect(await screen.findByRole("link", { name: "Back to exam" })).toBeTruthy();
  fireEvent.click(screen.getByRole("link", { name: "Back to exam" }));
  expect(screen.getByLabelText("Current URL").textContent).toBe(`/question-exam/analytics?${examQuery}`);
  expect(await screen.findByRole("button", { name: /Reanalyse$/ })).toBeTruthy();
  fireEvent.click(screen.getByRole("link", { name: "Back to exams" }));
  expect(await screen.findByRole("link", { name: /View analytics.*IT2040/ })).toBeTruthy();
});

it("shows a recovery link for an unknown exam instead of loading student details forever", async () => {
  renderNavigation("/question-exam/analytics?course=missing&student=S001");
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", expect.stringContaining("could not be found"));
  fireEvent.click(screen.getByRole("link", { name: "Back to exams" }));
  expect(await screen.findByRole("link", { name: /View analytics.*IT2040/ })).toBeTruthy();
});

it("shows a searching orb while loading exam analytics inventory", () => {
  vi.mocked(fetchExams).mockReturnValue(new Promise(() => {}));
  render(<MemoryRouter><AnalyticsPage /></MemoryRouter>);
  const orb = screen.getByRole("img", { name: "Loading exams" });
  expect(orb.tagName).toBe("CANVAS");
  expect(orb.style.width).toBe("64px");
});

it("distinguishes an inventory read failure from no exams and allows retry", async () => {
  vi.mocked(fetchExams).mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce([]);
  render(<MemoryRouter><AnalyticsPage /></MemoryRouter>);
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect(screen.queryByText("No exams found")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByText("No exams found")).toBeTruthy();
});

it("labels template teaching suggestions without a disabled action button", () => {
  render(<TeachingActions loading={false} actions={[{ topic: "SQL", priority: "High", performance_percentage: 40, actions: ["Practice joins"], provenance: "template", generated_at: "2026-10-16T00:00:00Z" }]} />);
  expect(screen.getByText(/Template suggestion/)).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Generate Practice Questions" })).toBeNull();
});

it("shows classification review and limited assessment evidence", () => {
  render(<QuestionPerformanceTable onSelectQuestion={() => {}} questions={[{ question_id: "Q01", question_no: "01", topic: "SQL", bloom_level: "Apply", average_percentage: 40, needs_review: true, coverage_warning: "insufficient_evidence" }]} />);
  expect(screen.getByText("Classification needs review")).toBeTruthy();
  expect(screen.getByText(/Limited assessment evidence/)).toBeTruthy();
});
