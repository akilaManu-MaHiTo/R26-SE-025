// @vitest-environment jsdom
import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
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
