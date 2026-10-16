// @vitest-environment jsdom
import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ExamKeysPage } from "./ExamKeysPage";
import { createExamKey, fetchExamKeys } from "../api/examKeysApi";
import { createCourse, fetchTaxonomyCourses } from "../api/taxonomyApi";

vi.mock("../api/examKeysApi", () => ({ fetchExamKeys: vi.fn(), createExamKey: vi.fn() }));
vi.mock("../utils/courseOptions", () => ({
  formatCourseLabel: (course: { code: string }) => course.code,
}));
vi.mock("../api/taxonomyApi", () => ({
  createCourse: vi.fn(),
  fetchTaxonomyCourses: vi.fn().mockResolvedValue([{ _id: "1", code: "IT2040", name: "Database Management System" }]),
}));

afterEach(() => { cleanup(); vi.clearAllMocks(); });

async function fillForm() {
  await screen.findByRole("option", { name: "IT2040" });
  fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "IT2040" } });
  fireEvent.change(screen.getByLabelText("Year"), { target: { value: "2025" } });
  fireEvent.change(screen.getByLabelText("Month"), { target: { value: "April" } });
}

it("creates an exam with ordered question types and displays the saved key", async () => {
  vi.mocked(fetchExamKeys).mockResolvedValue([]);
  vi.mocked(createExamKey).mockImplementation(async (exam) => ({ ...exam, examKey: "EXAM-IT2040-2025-S1-Apr-FINAL" }));
  render(<ExamKeysPage />);
  await fillForm();
  const key = screen.getByLabelText("Exam key") as HTMLInputElement;
  expect(key.readOnly).toBe(true);
  expect(key.value).toBe("EXAM-IT2040-2025-S1-Apr-FINAL");
  fireEvent.click(screen.getByRole("button", { name: "Add question" }));
  fireEvent.change(screen.getByLabelText("Question 2 type"), { target: { value: "Diagram" } });
  fireEvent.click(screen.getByRole("button", { name: "Create exam key" }));
  await waitFor(() => expect(createExamKey).toHaveBeenCalledWith({
    subjectCode: "IT2040", subjectName: "Database Management System",
    examYear: 2025, examSemester: 1, examMonth: "April", session: "Final", examStructure: ["Essay", "Diagram"],
  }));
  expect(await screen.findByRole("cell", { name: "EXAM-IT2040-2025-S1-Apr-FINAL" })).toBeTruthy();
});

it("keeps the draft and shows duplicate errors", async () => {
  vi.mocked(fetchExamKeys).mockResolvedValue([]);
  vi.mocked(createExamKey).mockRejectedValue(new Error("These exam details already exist."));
  render(<ExamKeysPage />);
  await fillForm();
  fireEvent.click(screen.getByRole("button", { name: "Create exam key" }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "These exam details already exist.");
  expect((screen.getByLabelText("Exam key") as HTMLInputElement).value).toBe("EXAM-IT2040-2025-S1-Apr-FINAL");
});

it("updates the read-only preview when exam details change", async () => {
  vi.mocked(fetchExamKeys).mockResolvedValue([]);
  render(<ExamKeysPage />);
  await fillForm();
  fireEvent.change(screen.getByLabelText("Session"), { target: { value: "Mid Term" } });
  fireEvent.change(screen.getByLabelText("Semester"), { target: { value: "2" } });
  expect((screen.getByLabelText("Exam key") as HTMLInputElement).value).toBe("EXAM-IT2040-2025-S2-Apr-MIDTERM");
});

it("shows existing exam keys even when the courses collection cannot load", async () => {
  vi.mocked(fetchTaxonomyCourses).mockRejectedValueOnce(new Error("Could not load courses."));
  vi.mocked(fetchExamKeys).mockResolvedValue([{
    examKey: "EXAM-2025-S1-Apr", subjectCode: "IT2040", subjectName: "Database Management System",
    examYear: 2025, examSemester: 1, examMonth: "April", session: "Final", examStructure: ["Essay", "Diagram"],
  }]);
  render(<ExamKeysPage />);
  expect(await screen.findByRole("cell", { name: "EXAM-2025-S1-Apr" })).toBeTruthy();
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", expect.stringContaining("Could not load courses."));
});

it("loads subjects from courses even when exam keys cannot load", async () => {
  vi.mocked(fetchExamKeys).mockRejectedValue(new Error("Could not load exam keys."));
  render(<ExamKeysPage />);
  await fillForm();
  expect((screen.getByLabelText("Subject name") as HTMLInputElement).value).toBe("Database Management System");
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", expect.stringContaining("Could not load exam keys."));
});

it("adds a course and selects it without submitting the exam", async () => {
  vi.mocked(fetchExamKeys).mockResolvedValue([]);
  vi.mocked(createCourse).mockResolvedValue({ _id: "2", code: "IT2050", name: "New Course", description: "Course description" });
  render(<ExamKeysPage />);
  await screen.findByRole("option", { name: "IT2040" });
  fireEvent.click(screen.getByRole("button", { name: "Add course" }));
  fireEvent.change(screen.getByLabelText("Course code"), { target: { value: "IT2050" } });
  fireEvent.change(screen.getByLabelText("Course name"), { target: { value: "New Course" } });
  fireEvent.change(screen.getByLabelText("Description"), { target: { value: "Course description" } });
  fireEvent.click(screen.getByRole("button", { name: "Save course" }));
  await waitFor(() => expect((screen.getByLabelText("Subject") as HTMLSelectElement).value).toBe("IT2050"));
  expect((screen.getByLabelText("Subject name") as HTMLInputElement).value).toBe("New Course");
  expect(createCourse).toHaveBeenCalledWith({ code: "IT2050", name: "New Course", description: "Course description" });
  expect(createExamKey).not.toHaveBeenCalled();
});

it("keeps the course dialog and its draft when the code already exists", async () => {
  vi.mocked(fetchExamKeys).mockResolvedValue([]);
  vi.mocked(createCourse).mockRejectedValue(new Error("Course code already exists."));
  render(<ExamKeysPage />);
  await screen.findByRole("option", { name: "IT2040" });
  fireEvent.click(screen.getByRole("button", { name: "Add course" }));
  fireEvent.change(screen.getByLabelText("Course code"), { target: { value: "IT2040" } });
  fireEvent.change(screen.getByLabelText("Course name"), { target: { value: "Duplicate" } });
  fireEvent.click(screen.getByRole("button", { name: "Save course" }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Course code already exists.");
  expect((screen.getByLabelText("Course code") as HTMLInputElement).value).toBe("IT2040");
});
