// @vitest-environment jsdom
import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { CourseMaterialsPage } from "./CourseMaterialsPage";
import { listMaterials, uploadMaterial, replaceMaterial, removeMaterial } from "../api/courseMaterialsApi";

vi.mock("../api/courseMaterialsApi", () => ({
  listMaterials: vi.fn(), uploadMaterial: vi.fn(), replaceMaterial: vi.fn(), removeMaterial: vi.fn(),
  materialPdfUrl: (id: string) => `/api/lecturers/materials/${id}/pdf`,
}));
vi.mock("../api/taxonomyApi", () => ({ fetchTaxonomyCourses: vi.fn().mockResolvedValue([]) }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const lecture = { document_id: "a".repeat(24), filename: "IT2040_Lecture01_2024.pdf", course_code: "IT2040",
  document_type: "lecture" as const, year: 2024, pages: 33, chunks: 33, empty_pages: [2], warnings: [], mode: "hybrid" as const, pdf_available: true };
const tutorial = { ...lecture, document_id: "b".repeat(24), filename: "IT2040_Tutorial01.pdf", document_type: "tutorial" as const };

it("shows existing materials, counts, extraction warnings, and type filters", async () => {
  vi.mocked(listMaterials).mockResolvedValue({ status: "ok", warnings: [], items: [lecture, tutorial] });
  render(<CourseMaterialsPage />);
  expect(await screen.findByText(lecture.filename)).toBeTruthy();
  expect(screen.getByText(tutorial.filename)).toBeTruthy();
  expect(screen.getByText(/2 materials/)).toBeTruthy();
  expect(screen.getAllByText(/Text-poor pages skipped: 2/)).toHaveLength(2);
  expect(screen.getByRole("link", { name: `Open ${lecture.filename}` }).getAttribute("href")).toContain(lecture.document_id);
  fireEvent.change(screen.getByLabelText("Material type filter"), { target: { value: "lecture" } });
  expect(screen.queryByText(tutorial.filename)).toBeNull();
});

it("uploads into the selected course and refreshes the existing catalog", async () => {
  vi.mocked(listMaterials).mockResolvedValue({ status: "ok", warnings: [], items: [lecture] });
  vi.mocked(uploadMaterial).mockResolvedValue({ item: tutorial, status: "indexed" });
  render(<CourseMaterialsPage />);
  await screen.findByText(lecture.filename);
  fireEvent.change(screen.getByLabelText("Material type"), { target: { value: "tutorial" } });
  const file = new File(["%PDF"], "New.pdf", { type: "application/pdf" });
  fireEvent.change(screen.getByLabelText("PDF file"), { target: { files: [file] } });
  fireEvent.click(screen.getByRole("button", { name: "Upload and index" }));
  await waitFor(() => expect(uploadMaterial).toHaveBeenCalledWith(file, "IT2040", "tutorial", undefined));
  await waitFor(() => expect(listMaterials).toHaveBeenCalledTimes(2));
});

it("requires confirmation before removal and leaves the list intact if deletion fails", async () => {
  vi.mocked(listMaterials).mockResolvedValue({ status: "ok", warnings: [], items: [lecture] });
  vi.mocked(removeMaterial).mockRejectedValue(new Error("Storage unavailable"));
  render(<CourseMaterialsPage />);
  await screen.findByText(lecture.filename);
  fireEvent.click(screen.getByRole("button", { name: `Remove ${lecture.filename}` }));
  expect(removeMaterial).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Remove material" }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Storage unavailable");
  expect(screen.getByText(lecture.filename)).toBeTruthy();
});

it("replaces the selected material only after a replacement file is confirmed", async () => {
  vi.mocked(listMaterials).mockResolvedValue({ status: "ok", warnings: [], items: [lecture] });
  vi.mocked(replaceMaterial).mockResolvedValue({ item: lecture, status: "indexed" });
  render(<CourseMaterialsPage />);
  await screen.findByText(lecture.filename);
  fireEvent.click(screen.getByRole("button", { name: `Replace ${lecture.filename}` }));
  const confirmation = screen.getByRole("button", { name: "Replace material" });
  expect((confirmation as HTMLButtonElement).disabled).toBe(true);
  const file = new File(["%PDF updated"], "Updated.pdf", { type: "application/pdf" });
  fireEvent.change(screen.getByLabelText("Replacement PDF"), { target: { files: [file] } });
  expect(replaceMaterial).not.toHaveBeenCalled();
  fireEvent.click(confirmation);
  await waitFor(() => expect(replaceMaterial).toHaveBeenCalledWith(lecture.document_id, file));
});
