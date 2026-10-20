// @vitest-environment jsdom
import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { BloomChart } from "./BloomChart";

// jsdom has no layout or ResizeObserver; give the real charts a fixed size.
vi.mock("recharts", async importOriginal => ({
  ...await importOriginal<typeof import("recharts")>(),
  ResponsiveContainer: ({ children }: { children: React.ReactElement }) =>
    React.cloneElement(children, { width: 600, height: 300 }),
}));

afterEach(cleanup);

it("reports missing assessment coverage rather than insufficient students", () => {
  render(<BloomChart bloomPerformance={["Understand", "Apply", "Analyze"].map(level => ({
    level, average_percentage: 70, student_count: 50,
  }))} />);
  expect(screen.getByText("3 of 6 levels assessed")).toBeTruthy();
  expect(screen.getByText("Not assessed: Remember, Evaluate, Create.")).toBeTruthy();
  expect(screen.queryByText("insufficient evidence")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Bar" }));
  expect(screen.getByText("3 of 6 levels assessed")).toBeTruthy();
  expect(screen.getByText("Not assessed: Remember, Evaluate, Create.")).toBeTruthy();
});

it("keeps an awarded zero as assessed and shows weaknesses despite missing levels", () => {
  render(<BloomChart bloomPerformance={[{
    level: "Apply", average_percentage: 0, evidence_status: "confirmed_weakness",
  }]} />);
  expect(screen.getByText("1 of 6 levels assessed")).toBeTruthy();
  expect(screen.getByText("weak")).toBeTruthy();
  expect(screen.getByText("0% is an assessed score; unassessed levels have no score.")).toBeTruthy();
});

it("retains genuine evidence warnings for assessed levels", () => {
  render(<BloomChart bloomPerformance={[{
    level: "Apply", average_percentage: 40, evidence_status: "insufficient_evidence",
  }]} />);
  expect(screen.getByText("Limited evidence for assessed levels")).toBeTruthy();
});

it("shows an explicit empty state when no levels have results", () => {
  render(<BloomChart bloomPerformance={[]} />);
  expect(screen.getByText("No cognitive assessment results available yet.")).toBeTruthy();
  expect(screen.queryByText("insufficient evidence")).toBeNull();
});

it("reports complete coverage even when every assessed score is zero", () => {
  render(<BloomChart bloomPerformance={["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"].map(level => ({
    level, average_percentage: 0,
  }))} />);
  expect(screen.getByText("6 of 6 levels assessed")).toBeTruthy();
  expect(screen.queryByText(/Not assessed:/)).toBeNull();
  expect(screen.queryByText(/Limited evidence/)).toBeNull();
});
