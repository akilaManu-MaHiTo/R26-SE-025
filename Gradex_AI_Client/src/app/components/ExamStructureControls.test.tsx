// @vitest-environment jsdom
import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { CandidateActions, type StructureActions } from "./ExamStructureControls";

afterEach(cleanup);
it("adds the complete candidate to the selected question and supports dragging", () => {
  const part = { part: "a", question: "Explain SQL", max_marks: 10, model_answer: "Answer", sources: [] };
  const actions: StructureActions = { insert: vi.fn(), startDrag: vi.fn(), endDrag: vi.fn(),
    selected: { question_number: 2, topic: "SQL", parts: [part] } };
  render(<CandidateActions topic="SQL" part={part} actions={actions} />);
  fireEvent.click(screen.getByRole("button", { name: "Add to Q2" }));
  expect(actions.insert).toHaveBeenCalledWith({ kind: "candidate", topic: "SQL", part }, { question: 1, part: 1 });
  fireEvent.dragStart(screen.getByRole("button", { name: "Drag question into paper" }));
  expect(actions.startDrag).toHaveBeenCalled();
});

it("disables invalid candidates and mismatched subpart insertion", () => {
  const actions: StructureActions = { insert: vi.fn(), startDrag: vi.fn(), endDrag: vi.fn(),
    selected: { question_number: 1, topic: "ER", parts: [] } };
  const { rerender } = render(<CandidateActions topic="SQL" part={{ part: "a", question: "SQL", max_marks: 10 }} actions={actions} />);
  expect((screen.getByRole("button", { name: "Add to Q1" }) as HTMLButtonElement).disabled).toBe(true);
  rerender(<CandidateActions topic="SQL" part={{ part: "a", question: "SQL", max_marks: 0 }} actions={actions} disabled />);
  expect((screen.getByRole("button", { name: "Add to paper" }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByRole("button", { name: "Drag question into paper" }).draggable).toBe(false);
});
