import React, { useRef, useState } from "react";
import { Button } from "../ui/button";
import { Dialog, DialogContent, DialogTitle } from "../ui/dialog";

type Entity = { entity_name: string; attributes?: string[]; primary_keys?: string[] };
type Relationship = { relation_name?: string; name?: string; entities?: string[]; attributes?: string[] };
type Props = { entities: Entity[]; relationships: Relationship[]; image?: string };

export function ERDiagramViewer({ entities, relationships, image }: Props) {
  const [zoom, setZoom] = useState(1);
  const [expanded, setExpanded] = useState(false);
  const [failedImage, setFailedImage] = useState<string>();
  const viewport = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; y: number; left: number; top: number } | null>(null);
  const labelWidth = (label: string) => Math.max(120, label.length * 9 + 32);
  const columnWidths = entities.map(e => Math.max(labelWidth(e.entity_name) + 80, 2 * Math.max(120, ...(e.attributes ?? []).map(labelWidth)) + 100));
  let offset = 24;
  const centers = columnWidths.map(width => { const center = offset + width / 2; offset += width; return center; });
  const contentWidth = Math.max(600, offset + 24, ...relationships.map(r => Math.max(labelWidth(r.relation_name || r.name || "Relationship") * 2 + 80, ...(r.attributes ?? []).map(a => labelWidth(a) + 80))));
  const width = contentWidth + relationships.length * 16 + 24;
  const entityY = 90 + Math.max(0, ...entities.map(e => Math.ceil((e.attributes?.length ?? 0) / 2))) * 64;
  let nextY = entityY + 120 + relationships.length * 16;
  const relationYs = relationships.map(r => { const y = nextY; nextY += 110 + (r.attributes?.length ?? 0) * 56; return y; });
  const height = relationships.length ? nextY : entityY + 70;
  const unresolved = relationships.filter(r => (r.entities?.length ?? 0) < 2 || r.entities?.some(name => !entities.some(e => e.entity_name === name)));
  const line = (x1: number, y1: number, x2: number, y2: number, key?: string | number) => <line key={key} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#64748b" strokeWidth="1.5" />;
  const oval = (label: string, x: number, y: number, key: string | number, isKey = false) => <g key={key}>
    <ellipse cx={x} cy={y} rx={labelWidth(label) / 2} ry={22} fill="#ecfeff" stroke="#0891b2" strokeWidth="1.5" />
    <text x={x} y={y + 5} textAnchor="middle" fontSize="15" fill="#155e75" textDecoration={isKey ? "underline" : "none"}>{label}</text>
  </g>;

  const content = <div className="space-y-3">
    <div className="flex flex-wrap items-center gap-2">
      <span className="mr-auto text-sm font-medium">ER diagram · {entities.length} entities · {relationships.length} relationships</span>
      <Button size="sm" variant="outline" aria-label="Zoom out" disabled={zoom <= 0.5} onClick={() => setZoom(z => Math.max(0.5, z - 0.25))}>−</Button>
      <span className="text-xs tabular-nums" aria-live="polite">{Math.round(zoom * 100)}%</span>
      <Button size="sm" variant="outline" aria-label="Zoom in" disabled={zoom >= 3} onClick={() => setZoom(z => Math.min(3, z + 0.25))}>+</Button>
      <Button size="sm" variant="outline" onClick={() => { setZoom(1); if (viewport.current) { viewport.current.scrollLeft = 0; viewport.current.scrollTop = 0; } }}>Fit diagram</Button>
      {!expanded && <Button size="sm" variant="outline" onClick={() => { setZoom(1); setExpanded(true); }}>Fullscreen</Button>}
    </div>
    <div className={image && failedImage !== image ? "grid gap-3 lg:grid-cols-2" : ""}>
      <div ref={viewport} role="region" aria-label="Reconstructed ER diagram, drag or scroll to pan" tabIndex={0}
        className="min-w-0 overflow-auto rounded-lg border bg-white cursor-grab active:cursor-grabbing" style={{ height: expanded ? "65vh" : "60vh", maxHeight: expanded ? undefined : 520, touchAction: "pan-x pan-y" }}
        onPointerDown={event => { if (event.button !== 0 || event.pointerType === "touch") return; const el = event.currentTarget; drag.current = { x: event.clientX, y: event.clientY, left: el.scrollLeft, top: el.scrollTop }; el.setPointerCapture(event.pointerId); }}
        onPointerMove={event => { if (!drag.current) return; event.currentTarget.scrollLeft = drag.current.left - event.clientX + drag.current.x; event.currentTarget.scrollTop = drag.current.top - event.clientY + drag.current.y; }}
        onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }} onLostPointerCapture={() => { drag.current = null; }}>
        {entities.length ? <svg role="img" aria-label="Reconstructed entities, attributes and relationships" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet" style={{ width: `${zoom * 100}%`, height: `${zoom * 100}%`, display: "block", marginInline: "auto" }}>
          {relationships.map((r, i) => <g key={i}>{(r.entities ?? []).map((name, j) => {
            const index = entities.findIndex(e => e.entity_name === name);
            if (index < 0) return null;
            if (relationships.length === 1) {
              const diamondX = contentWidth / 2, diamondY = relationYs[i];
              const dx = centers[index] - diamondX, dy = entityY - diamondY;
              const half = labelWidth(r.relation_name || r.name || "Relationship");
              // Intersect the center-to-center line with each shape's boundary.
              const diamondScale = 1 / (Math.abs(dx) / half + Math.abs(dy) / 32);
              const entityScale = Math.min(labelWidth(entities[index].entity_name) / 2 / Math.abs(dx), 25 / Math.abs(dy));
              return line(centers[index] - dx * entityScale, entityY - dy * entityScale, diamondX + dx * diamondScale, diamondY + dy * diamondScale, j);
            }
            const laneX = contentWidth + i * 16, laneY = entityY + 50 + i * 16;
            const diamondRight = contentWidth / 2 + labelWidth(r.relation_name || r.name || "Relationship");
            // Route outside the relationship area so edges cannot cross unrelated diamonds.
            return <polyline key={j} points={`${centers[index]},${entityY + 25} ${centers[index]},${laneY} ${laneX},${laneY} ${laneX},${relationYs[i]} ${diamondRight},${relationYs[i]}`} fill="none" stroke="#64748b" strokeWidth="1.5" />;
          })}</g>)}
          {entities.map((e, i) => <g key={i}>
            {(e.attributes ?? []).map((attribute, j) => {
              const y = 48 + Math.floor(j / 2) * 64;
              const side = j % 2 === 0 ? -1 : 1;
              const x = centers[i] + side * columnWidths[i] / 4;
              return <g key={j}>{line(centers[i], entityY - 25, centers[i], y)}{line(centers[i], y, x - side * labelWidth(attribute) / 2, y)}{oval(attribute, x, y, j, e.primary_keys?.includes(attribute))}</g>;
            })}
            <rect x={centers[i] - labelWidth(e.entity_name) / 2} y={entityY - 25} width={labelWidth(e.entity_name)} height={50} rx={4} fill="#eef2ff" stroke="#6366f1" strokeWidth={2} />
            <text x={centers[i]} y={entityY + 6} textAnchor="middle" fontSize={17} fontWeight={600} fill="#312e81">{e.entity_name}</text>
          </g>)}
          {relationships.map((r, i) => {
            const x = contentWidth / 2, y = relationYs[i], label = r.relation_name || r.name || "Relationship", half = labelWidth(label);
            return <g key={i}>
              {(r.attributes ?? []).map((attribute, j) => <g key={j}>{line(x + half, y, x + half, y + 64 + j * 56)}{line(x + half, y + 64 + j * 56, x + labelWidth(attribute) / 2, y + 64 + j * 56)}{oval(attribute, x, y + 64 + j * 56, j)}</g>)}
              <polygon points={`${x},${y - 32} ${x + half},${y} ${x},${y + 32} ${x - half},${y}`} fill="#ecfdf5" stroke="#059669" strokeWidth={2} />
              <text x={x} y={y + 5} textAnchor="middle" fontSize={15} fill="#065f46">{label}</text>
            </g>;
          })}
        </svg> : <p className="p-8 text-sm text-muted-foreground">No extracted entities available. Use the saved image and detection summary to review this submission.</p>}
      </div>
      {image && failedImage !== image ? <figure className="rounded-lg border p-2"><figcaption className="mb-2 text-xs text-muted-foreground">Saved submission with detection annotations</figcaption><img src={image} alt="Student diagram with detection annotations" className="w-full object-contain" onError={() => setFailedImage(image)} /></figure> : <p className="py-2 text-xs text-muted-foreground">{image ? "Saved image could not be loaded." : "No saved submission image is available for comparison."}</p>}
    </div>
    <p className="text-xs text-muted-foreground">Rectangle: entity · Oval: attribute · Diamond: relationship · Underline: detected primary key. Drag or scroll to pan; use + to inspect labels.</p>
    <p className="text-xs text-muted-foreground">Cardinality and inheritance are not available in this saved structure. Reconstruction reflects extracted data, not a corrected answer.</p>
    {unresolved.map((r, i) => <p key={i} className="text-xs text-amber-700">Unresolved: {r.relation_name || r.name || "Relationship"} — {(r.entities ?? []).join(", ") || "no endpoints detected"}. Check the submission.</p>)}
  </div>;
  return <div className="rounded-lg border bg-card p-3">
    {!expanded && content}
    <Dialog open={expanded} onOpenChange={setExpanded}><DialogContent aria-describedby={undefined} className="!max-w-[96vw] max-h-[96vh] overflow-auto"><DialogTitle>Diagram inspection</DialogTitle>{expanded && content}</DialogContent></Dialog>
  </div>;
}
