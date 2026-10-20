// @vitest-environment jsdom
import React from "react";
import { afterEach, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { GradingOverview, StudentGradingCells, canViewStudent, ExamInventoryScore } from "./GradingStatus";
import type { StudentRow, ExamListItem } from "../../api/lecturerApi";

afterEach(cleanup);

it("shows why exam grades are unavailable", () => {
  render(<ExamInventoryScore exam={{ average_percentage: null,
    grading_warning: "Duplicate diagram evaluations for a student and exam" } as ExamListItem} />);
  expect(screen.getByRole("status").textContent).toContain("Duplicate diagram evaluations");
  expect(screen.queryByText("No valid grades")).toBeNull();
});

it("distinguishes an ungraded exam from an awarded zero in the exam inventory", () => {
  const exam = { average_percentage: null, score_basis: "Essay", graded_student_count: 0 } as ExamListItem;
  const view = render(<ExamInventoryScore exam={exam} />);
  expect(screen.getByText("No valid grades")).toBeTruthy();
  view.rerender(<ExamInventoryScore exam={{ ...exam, average_percentage: 0, graded_student_count: 1 }} />);
  expect(screen.getByText("0.0%")).toBeTruthy();
  expect(screen.getByText("Essay · 1 graded")).toBeTruthy();
});

function student(id: string, status: "complete" | "pending" | "needs_review", essay = "graded"): StudentRow {
  return {
    student_id: id, grading_status: status, status: "Pending", analysis_status: "diagram_only", submitted_at: null,
    score: { obtained: status === "pending" ? null : 44.5, maximum: 55, percentage: status === "pending" ? null : 80.91 },
    components: {
      essay: { status: essay, obtained: essay === "graded" ? 31.5 : null, maximum: 35 },
      diagram: { status: "graded", obtained: 13, maximum: 20 },
    },
  };
}

it("shows all component counts and excludes pending/review grades from the overall average", () => {
  const review = student("S1", "needs_review");
  review.score.percentage = 97.27;
  render(<GradingOverview students={[review, student("S2", "complete"), student("S3", "pending", "processing"), student("S4", "pending", "not_started"), student("S5", "pending", "not_started")]} />);
  const toggle = screen.getByRole("button", { name: /Grading progress/ });
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
  expect(screen.queryByRole("progressbar")).toBeNull();
  expect(screen.getByText(/3 pending/)).toBeTruthy();
  expect(screen.getByText("80.91%")).toBeTruthy();
  expect(screen.queryByText("97.27%")).toBeNull();
  fireEvent.click(toggle);
  expect(toggle.getAttribute("aria-expanded")).toBe("true");
  expect(screen.getByRole("progressbar", { name: "Essay grading" }).getAttribute("aria-valuenow")).toBe("40");
  expect(screen.getByRole("progressbar", { name: "Diagram grading" }).getAttribute("aria-valuenow")).toBe("100");
  expect(screen.getByRole("status").textContent).toContain("3 students are awaiting essay grades");
  expect(screen.getByRole("status").textContent).toContain("1 grade needs review");
  fireEvent.click(toggle);
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
  expect(screen.queryByRole("progressbar")).toBeNull();
  expect(screen.getByText("80.91%")).toBeTruthy();
});

it("handles an empty roster and components that are not required", () => {
  const view = render(<GradingOverview students={[]} />);
  fireEvent.click(screen.getByRole("button", { name: /Grading progress/ }));
  expect(screen.getByText("0 students")).toBeTruthy();
  expect(screen.getAllByText("Not required")).toHaveLength(2);
  expect(screen.queryByRole("progressbar")).toBeNull();
  const row = student("S1", "complete");
  row.components!.diagram.status = "not_required";
  view.rerender(<GradingOverview students={[row]} />);
  expect(screen.getByRole("progressbar", { name: "Essay grading" }).getAttribute("aria-valuenow")).toBe("100");
  expect(screen.queryByRole("progressbar", { name: "Diagram grading" })).toBeNull();
  expect(screen.getByText("Not required")).toBeTruthy();
  expect(screen.queryByText(/awaiting/)).toBeNull();
});

it("renders processing with an available diagram and no invented overall zero", () => {
  render(<table><tbody><tr><StudentGradingCells student={student("S3", "pending", "processing")} /></tr></tbody></table>);
  expect(screen.getByText("Processing")).toBeTruthy();
  expect(screen.getByText("13.0 / 20.0")).toBeTruthy();
  expect(screen.getByText("Pending essay grading")).toBeTruthy();
  expect(screen.queryByText("0.00%")).toBeNull();
});

it("labels review totals provisional and preserves genuinely awarded zero marks", () => {
  const review = student("S1", "needs_review");
  review.components!.essay.obtained = 0;
  render(<table><tbody><tr><StudentGradingCells student={review} /></tr></tbody></table>);
  expect(screen.getByText("0.0 / 35.0")).toBeTruthy();
  expect(screen.getByText("Review needed")).toBeTruthy();
  expect(screen.getByText(/Provisional/)).toBeTruthy();
});

it("does not report a zero overall average when no grades are complete", () => {
  render(<GradingOverview students={[student("S1", "pending", "not_started")]} />);
  expect(screen.getByText("No complete overall grades yet")).toBeTruthy();
  expect(screen.queryByText("0.00%")).toBeNull();
});

it("does not invent progress for legacy rows without component status", () => {
  const legacy = student("S1", "complete");
  delete legacy.components;
  delete legacy.grading_status;
  render(<GradingOverview students={[legacy]} />);
  expect(screen.getByRole("status").textContent).toContain("unavailable for legacy records");
  expect(screen.queryByText("80.91%")).toBeNull();
});

it("keeps diagram-only details available but does not open analysis for ungraded roster students", () => {
  const row = student("S1", "pending", "not_started");
  expect(canViewStudent(row)).toBe(true);
  row.analysis_status = "pending";
  row.components!.diagram = { status: "missing_submission", obtained: null, maximum: 20 };
  expect(canViewStudent(row)).toBe(false);
});
