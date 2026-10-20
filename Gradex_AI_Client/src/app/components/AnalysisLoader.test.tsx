// @vitest-environment jsdom
import React from "react";
import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { AnalysisLoader } from "./AnalysisLoader";

vi.mock("thinking-orbs", () => ({ ThinkingOrb: () => <div aria-hidden="true" /> }));

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

it("keeps advancing without server updates and holds at 99 until results replace it", () => {
  vi.useFakeTimers();
  const { unmount } = render(<AnalysisLoader />);
  const progress = screen.getByRole("progressbar", { name: "Analyzing exam" });
  expect(progress.getAttribute("aria-valuenow")).toBe("1");
  act(() => vi.advanceTimersByTime(1000));
  expect(progress.getAttribute("aria-valuenow")).toBe("2");
  act(() => vi.advanceTimersByTime(1000));
  expect(progress.getAttribute("aria-valuenow")).toBe("3");
  act(() => vi.advanceTimersByTime(120000));
  expect(progress.getAttribute("aria-valuenow")).toBe("99");
  expect(screen.getByText("99%")).toBeTruthy();
  act(() => vi.advanceTimersByTime(60000));
  expect(progress.getAttribute("aria-valuenow")).toBe("99");
  unmount();
  expect(vi.getTimerCount()).toBe(0);
});

it("cleans up on early completion and starts a new analysis at 1%", () => {
  vi.useFakeTimers();
  const first = render(<AnalysisLoader />);
  act(() => vi.advanceTimersByTime(5000));
  first.unmount();
  expect(vi.getTimerCount()).toBe(0);
  render(<AnalysisLoader label="Loading exams" />);
  expect(screen.getByRole("progressbar", { name: "Loading exams" }).getAttribute("aria-valuenow")).toBe("1");
});

it.each([2000, 120000])("finishes at 100 before revealing results after %i ms", (elapsed) => {
  vi.useFakeTimers();
  const onComplete = vi.fn();
  const { rerender } = render(<AnalysisLoader complete={false} onComplete={onComplete} />);
  act(() => vi.advanceTimersByTime(elapsed));
  rerender(<AnalysisLoader complete onComplete={onComplete} />);
  expect(onComplete).not.toHaveBeenCalled();
  act(() => vi.advanceTimersByTime(260));
  expect(screen.getByText("100%")).toBeTruthy();
  expect(onComplete).not.toHaveBeenCalled();
  act(() => vi.advanceTimersByTime(160));
  expect(onComplete).toHaveBeenCalledTimes(1);
  expect(vi.getTimerCount()).toBe(0);
});

it("cancels the completion callback when the loader unmounts", () => {
  vi.useFakeTimers();
  const onComplete = vi.fn();
  const { unmount } = render(<AnalysisLoader complete onComplete={onComplete} />);
  act(() => vi.advanceTimersByTime(100));
  unmount();
  act(() => vi.advanceTimersByTime(1000));
  expect(onComplete).not.toHaveBeenCalled();
  expect(vi.getTimerCount()).toBe(0);
});
