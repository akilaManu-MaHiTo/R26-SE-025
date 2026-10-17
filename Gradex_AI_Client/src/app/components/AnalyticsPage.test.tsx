// @vitest-environment jsdom
import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import AnalyticsPage from "./AnalyticsPage";
import { fetchExams } from "../api/lecturerApi";
import { TeachingActions } from "./analytics/TeachingActions";
import { QuestionPerformanceTable } from "./analytics/QuestionPerformanceTable";

vi.mock("../api/lecturerApi", async importOriginal => ({ ...await importOriginal<typeof import("../api/lecturerApi")>(), fetchExams: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

it("shows a searching orb while loading exam analytics inventory", () => {
  vi.mocked(fetchExams).mockReturnValue(new Promise(() => {}));
  render(<MemoryRouter><AnalyticsPage /></MemoryRouter>);
  const orb = screen.getByRole("img", { name: "Loading exam analytics" });
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
