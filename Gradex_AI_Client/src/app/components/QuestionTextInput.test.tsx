// @vitest-environment jsdom
import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QuestionTextInput } from "./QuestionTextInput";

afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });

it("types a new generated result while keeping the complete value in props", () => {
  vi.useFakeTimers();
  const text = "Compare two database indexes and explain their performance tradeoffs.";
  const { rerender } = render(<QuestionTextInput aria-label="Question" value="Lecturer text" />);
  const input = screen.getByLabelText("Question") as HTMLTextAreaElement;
  expect(input.value).toBe("Lecturer text");
  rerender(<QuestionTextInput aria-label="Question" value={text} questionId="generated-1" />);
  expect(input.value).toBe("");
  act(() => { vi.advanceTimersByTime(200); });
  expect(input.value.length).toBeGreaterThan(0);
  expect(input.value.length).toBeLessThan(text.length);
  act(() => { vi.advanceTimersByTime(2500); });
  expect(input.value).toBe(text);
});

it("stops typing when the lecturer changes the question", () => {
  vi.useFakeTimers();
  const { rerender } = render(<QuestionTextInput aria-label="Question" value="" />);
  rerender(<QuestionTextInput aria-label="Question" value="Generated question" questionId="generated-1" />);
  act(() => { vi.advanceTimersByTime(50); });
  rerender(<QuestionTextInput aria-label="Question" value="Lecturer edit" questionId="generated-1" />);
  act(() => { vi.advanceTimersByTime(3000); });
  expect((screen.getByLabelText("Question") as HTMLTextAreaElement).value).toBe("Lecturer edit");
});

it("shows the complete result immediately with reduced motion", () => {
  vi.stubGlobal("matchMedia", () => ({ matches: true }));
  const { rerender } = render(<QuestionTextInput aria-label="Question" value="" />);
  rerender(<QuestionTextInput aria-label="Question" value="Generated question" questionId="generated-1" />);
  expect((screen.getByLabelText("Question") as HTMLTextAreaElement).value).toBe("Generated question");
});

it("reveals all text before the lecturer can edit an animated result", () => {
  vi.useFakeTimers();
  const onChange = vi.fn();
  const { rerender } = render(<QuestionTextInput aria-label="Question" value="" onChange={onChange} />);
  rerender(<QuestionTextInput aria-label="Question" value="Complete generated question" questionId="generated-1" onChange={onChange} />);
  act(() => { vi.advanceTimersByTime(50); });
  const input = screen.getByLabelText("Question") as HTMLTextAreaElement;
  fireEvent.focus(input);
  expect(input.value).toBe("Complete generated question");
  act(() => { vi.advanceTimersByTime(3000); });
  expect(input.value).toBe("Complete generated question");
});

it("does not animate a result in the textarea the lecturer is editing", () => {
  const { rerender } = render(<QuestionTextInput aria-label="Question" value="" />);
  act(() => { (screen.getByLabelText("Question") as HTMLTextAreaElement).focus(); });
  rerender(<QuestionTextInput aria-label="Question" value="Complete generated question" questionId="generated-1" />);
  expect((screen.getByLabelText("Question") as HTMLTextAreaElement).value).toBe("Complete generated question");
});
