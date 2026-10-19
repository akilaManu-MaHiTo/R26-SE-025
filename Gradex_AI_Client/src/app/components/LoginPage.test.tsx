// @vitest-environment jsdom
import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router";
import { LoginPage } from "./LoginPage";
import { login } from "../api/authApi";

vi.mock("../api/authApi", () => ({ login: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

it("switches the character scene and sign-in form with the portal", () => {
  render(<MemoryRouter initialEntries={["/login/lecturer"]}><Routes>
    <Route path="/login/lecturer" element={<LoginPage key="lecturer" role="lecturer" onLogin={vi.fn()} />} />
    <Route path="/login/student" element={<LoginPage key="student" role="student" onLogin={vi.fn()} />} />
  </Routes></MemoryRouter>);
  expect(screen.getByText("A little insight. A lasting impact.")).toBeTruthy();
  fireEvent.click(screen.getByRole("link", { name: "Student" }));
  expect(screen.getByRole("heading", { name: "Student sign in" })).toBeTruthy();
  expect(screen.getByRole("link", { name: "Student" }).getAttribute("aria-current")).toBe("page");
  expect(screen.getByText("Big ambitions. Small steps. Your pace.")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Show password" }));
  expect(screen.getByLabelText("Password").getAttribute("type")).toBe("text");
  fireEvent.click(screen.getByRole("link", { name: "Lecturer" }));
  expect(screen.getByRole("heading", { name: "Lecturer sign in" })).toBeTruthy();
  expect(screen.getByLabelText("Password").getAttribute("type")).toBe("password");
});

it.each(["lecturer", "student"] as const)("signs in through the %s portal using the server identity", async (role) => {
  const user = { email: "user@example.edu", role, student_id: role === "student" ? "IT001" : null };
  vi.mocked(login).mockResolvedValue(user);
  const onLogin = vi.fn();
  render(<MemoryRouter><LoginPage role={role} onLogin={onLogin} /></MemoryRouter>);
  expect(screen.getByRole("heading", { name: `${role === "lecturer" ? "Lecturer" : "Student"} sign in` })).toBeTruthy();
  expect(screen.getByRole("img", { name: "GradeX AI" }).getAttribute("src")).toContain("gradex-logo.png");
  fireEvent.change(screen.getByLabelText("University email"), { target: { value: "user@example.edu" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "secret" } });
  fireEvent.click(screen.getByRole("button", { name: `Sign in as ${role}` }));
  await vi.waitFor(() => expect(onLogin).toHaveBeenCalledWith(user));
  expect(login).toHaveBeenCalledWith("user@example.edu", "secret", role);
});

it("surfaces a rejected login without entering the app", async () => {
  vi.mocked(login).mockRejectedValue(new Error("Use the student sign-in page for this account."));
  const onLogin = vi.fn();
  render(<MemoryRouter><LoginPage role="lecturer" onLogin={onLogin} /></MemoryRouter>);
  fireEvent.change(screen.getByLabelText("University email"), { target: { value: "student@example.edu" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "secret" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in as lecturer" }));
  expect((await screen.findByRole("alert")).textContent).toContain("student sign-in");
  expect(onLogin).not.toHaveBeenCalled();
});
