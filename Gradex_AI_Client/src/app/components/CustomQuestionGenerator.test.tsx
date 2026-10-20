// @vitest-environment jsdom
import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { CustomQuestionGenerator } from "./CustomQuestionGenerator";
import { generateExamQuestions } from "../api/examCreatorApi";

vi.mock("../api/examCreatorApi", async importOriginal => ({
  ...await importOriginal<typeof import("../api/examCreatorApi")>(), generateExamQuestions: vi.fn(),
}));
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("renders the real solving orb without crashing while generation is pending", () => {
  // jsdom has no canvas renderer; keep the real orb and stub only drawing APIs.
  const context = { setTransform: vi.fn(), clearRect: vi.fn(), beginPath: vi.fn(), arc: vi.fn(),
    fill: vi.fn(), moveTo: vi.fn(), lineTo: vi.fn(), stroke: vi.fn() };
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(context as unknown as CanvasRenderingContext2D);
  vi.stubGlobal("requestAnimationFrame", vi.fn(() => 1));
  vi.stubGlobal("cancelAnimationFrame", vi.fn());
  vi.mocked(generateExamQuestions).mockReturnValue(new Promise(() => {}));
  const part = { part: "a", question: "", max_marks: 10 };
  const question = { question_number: 1, topic: "Indexes", parts: [part] };
  render(<CustomQuestionGenerator courseCode="IT2040" paper={{ exam: "DBMS", year: 2026, questions: [question] }}
    question={question} part={part} onGenerated={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Generate Q1 part a with AI" }));
  fireEvent.click(screen.getByRole("button", { name: "Generate question", exact: true }));
  expect(screen.queryByLabelText("Lecture topic")).toBeNull();
  expect(screen.getByRole("status").textContent).toBe("Generating question. Please wait.");
  expect(context.arc).toHaveBeenCalled();
});
