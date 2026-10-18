// @vitest-environment jsdom
import React from "react";
import { afterEach, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ERDiagramViewer } from "./ERDiagramViewer";

afterEach(cleanup);
const entities = [
  { entity_name: "Course", attributes: ["name", "C_id"], primary_keys: ["C_id"] },
  { entity_name: "Students", attributes: ["S_id", "email", "name"] },
];
it("renders every attribute, explicit keys and a diamond for each relationship", () => {
  const { container } = render(<ERDiagramViewer entities={entities} relationships={[{ relation_name: "has", entities: ["Course", "Students"] }]} />);
  expect(screen.getByText("has")).toBeTruthy();
  expect(screen.getAllByText("name")).toHaveLength(2);
  expect(screen.getByText("C_id").getAttribute("text-decoration")).toBe("underline");
  expect(container.querySelector("polygon")?.getAttribute("points")?.split(" ")).toHaveLength(4);
  fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));
  expect(screen.getByText("125%")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Fit diagram" }));
  expect(screen.getByText("100%")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Zoom out" }));
  const svg = screen.getByRole("img", { name: /Reconstructed entities/ });
  expect(svg.style.width).toBe("75%");
  expect(svg.style.height).toBe("75%");
  expect(svg.style.minWidth).toBe("");
});
it("fits both viewport dimensions and connects Joins at distinct diamond boundaries", () => {
  const { container } = render(<ERDiagramViewer entities={entities} relationships={[{ relation_name: "Joins", entities: ["Course", "Students"] }]} />);
  const viewport = screen.getByRole("region");
  expect(viewport.style.height).toBe("60vh");
  expect(viewport.style.maxHeight).toBe("520px");
  const svg = screen.getByRole("img", { name: /Reconstructed entities/ });
  expect(svg.style.height).toBe("100%");
  const diamond = container.querySelector("polygon")!.getAttribute("points")!.split(" ").map(p => p.split(",").map(Number));
  const [cx, top] = diamond[0], [right, cy] = diamond[1];
  const edges = [...container.querySelector("svg > g")!.querySelectorAll("line")];
  expect(edges).toHaveLength(2);
  const ends = edges.map(edge => [Number(edge.getAttribute("x2")), Number(edge.getAttribute("y2"))]);
  expect(ends[0][0]).toBeLessThan(cx);
  expect(ends[1][0]).toBeGreaterThan(cx);
  for (const [x, y] of ends) expect(Math.abs(x - cx) / (right - cx) + Math.abs(y - cy) / (cy - top)).toBeCloseTo(1);
  viewport.scrollTop = 120;
  fireEvent.click(screen.getByRole("button", { name: "Fit diagram" }));
  expect(viewport.scrollTop).toBe(0);
});
it("routes later connections around unrelated relationship diamonds", () => {
  const { container } = render(<ERDiagramViewer entities={[...entities, { entity_name: "Lecturer", attributes: [] }]} relationships={[
    { relation_name: "teaches", entities: ["Course", "Lecturer"] },
    { relation_name: "enrolls", entities: ["Students", "Course"] },
  ]} />);
  const diamonds = [...container.querySelectorAll("polygon")];
  const rightmost = Math.max(...diamonds.flatMap(d => d.getAttribute("points")!.split(" ").map(p => Number(p.split(",")[0]))));
  const edges = [...container.querySelectorAll("polyline")];
  expect(edges).toHaveLength(4);
  for (const edge of edges) {
    const points = edge.getAttribute("points")!.split(" ").map(p => p.split(",").map(Number));
    expect(points[2][0]).toBeGreaterThan(rightmost);
    expect(points[3][0]).toBe(points[2][0]);
  }
});
it("does not invent ISA connections from entity names or omit extra attributes", () => {
  render(<ERDiagramViewer entities={[{ entity_name: "Person", attributes: Array.from({ length: 8 }, (_, i) => `attribute ${i}`) }, { entity_name: "Instructor", attributes: [] }]} relationships={[]} />);
  expect(screen.getByText("attribute 7")).toBeTruthy();
  expect(screen.queryByText("ISA")).toBeNull();
  expect(screen.getByText(/Cardinality and inheritance/)).toBeTruthy();
});
it("keeps unresolved relationships visible and handles absent structures and images", () => {
  render(<ERDiagramViewer entities={entities} relationships={[{ relation_name: "unknown link", entities: ["Missing"] }]} />);
  expect(screen.getByText(/Unresolved: unknown link/)).toBeTruthy();
  expect(screen.getByText(/No saved submission image/)).toBeTruthy();
});
it("shows a saved annotated submission and reports image failures", () => {
  render(<ERDiagramViewer entities={[]} relationships={[]} image="data:image/png;base64,AAAA" />);
  expect(screen.getByText(/No extracted entities/)).toBeTruthy();
  fireEvent.error(screen.getByRole("img"));
  expect(screen.getByText(/Saved image could not be loaded/)).toBeTruthy();
});
it("opens and closes fullscreen without duplicating the diagram", () => {
  render(<ERDiagramViewer entities={entities} relationships={[]} />);
  fireEvent.click(screen.getByRole("button", { name: "Fullscreen" }));
  expect(screen.getByRole("dialog")).toBeTruthy();
  expect(screen.getAllByText("Course")).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(screen.getByText("Course")).toBeTruthy();
});
it("keeps long relationship attributes inside the canvas", () => {
  const attribute = "Very long relationship attribute ".repeat(8);
  const { container } = render(<ERDiagramViewer entities={entities} relationships={[{ relation_name: "has", entities: ["Course", "Students"], attributes: [attribute] }]} />);
  const svgWidth = Number(container.querySelector("svg")!.getAttribute("viewBox")!.split(" ")[2]);
  const oval = screen.getByText(attribute.trim()).previousElementSibling!;
  expect(Number(oval.getAttribute("cx")) + Number(oval.getAttribute("rx"))).toBeLessThan(svgWidth);
});
