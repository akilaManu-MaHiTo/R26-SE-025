// @vitest-environment jsdom
import React from "react";
import { afterEach, expect, it } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { TopBar } from "./TopBar";

afterEach(cleanup);

function analysis(active: boolean, progress: number, detail = {}) {
  act(() => {
    window.dispatchEvent(new CustomEvent("topbar-student-analysis", {
      detail: { active, studentId: "IT2026001", message: "Evaluating Bloom levels", progress, ...detail },
    }));
  });
}

it("keeps the bell visible and confines student progress to notifications", async () => {
  render(<TopBar title="Student Analytics" />);
  analysis(true, 35);
  const bell = screen.getByRole("button", { name: "Notifications" });
  expect(bell.querySelector("svg.lucide-bell")).toBeTruthy();
  expect(screen.queryByText("IT2026001")).toBeNull();
  expect(screen.queryByRole("img", { name: "Analysing student" })).toBeNull();
  expect(screen.queryByRole("progressbar")).toBeNull();

  fireEvent.click(bell);
  const notifications = await screen.findByRole("dialog");
  await waitFor(() => {
    const popup = notifications.closest<HTMLElement>("[data-radix-popper-content-wrapper]");
    expect(popup?.style.transform).not.toBe("translate(0, -200%)");
  });
  expect(within(notifications).getByText("IT2026001")).toBeTruthy();
  expect(within(notifications).getByText("Evaluating Bloom levels")).toBeTruthy();
  const progress = within(notifications).getByRole("progressbar", { name: "Analysis progress for IT2026001" });
  expect(progress.getAttribute("aria-valuenow")).toBe("35");

  analysis(true, 75);
  expect(progress.getAttribute("aria-valuenow")).toBe("75");
  analysis(false, 100);
  expect(progress.getAttribute("aria-valuenow")).toBe("100");
  expect(within(notifications).getByText("Complete")).toBeTruthy();
  expect(bell.querySelector("svg.lucide-bell")).toBeTruthy();
});

it("shows queued students separately and only clears finished notifications", async () => {
  render(<TopBar title="Student Analytics" />);
  analysis(true, 40, { jobId: "A", status: "analyzing" });
  analysis(true, 0, { jobId: "B", studentId: "IT2026002", status: "queued", message: "Waiting for the previous student" });
  fireEvent.click(screen.getByRole("button", { name: "Notifications" }));
  const notifications = await screen.findByRole("dialog");
  expect(within(notifications).getByText("Queued")).toBeTruthy();
  expect(within(notifications).getByRole("progressbar", { name: "Analysis progress for IT2026002" }).getAttribute("aria-valuenow")).toBe("0");
  analysis(false, 100, { jobId: "A", status: "complete" });
  fireEvent.click(within(notifications).getByRole("button", { name: "Clear finished" }));
  expect(within(notifications).queryByText("IT2026001")).toBeNull();
  expect(within(notifications).getByText("IT2026002")).toBeTruthy();
  analysis(false, 0, { jobId: "B", studentId: "IT2026002", status: "failed" });
  expect(within(notifications).getByText("Failed")).toBeTruthy();
});

it("keeps analyses of the same student in different exams separate", async () => {
  render(<TopBar title="Student Analytics" />);
  analysis(true, 40, { jobId: "exam-2026" });
  analysis(true, 0, { jobId: "exam-2027", status: "queued" });
  fireEvent.click(screen.getByRole("button", { name: "Notifications" }));
  const notifications = await screen.findByRole("dialog");
  expect(within(notifications).getAllByRole("progressbar")).toHaveLength(2);
});
