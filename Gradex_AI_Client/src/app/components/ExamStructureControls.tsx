import { useState, type DragEvent } from "react";
import { GripVertical, ArrowUp, ArrowDown } from "lucide-react";
import { Button } from "./ui/button";
import type { PaperQuestion, Part } from "../api/examCreatorApi";
import type { PlacementSource, PlacementTarget } from "./examStructure";

export type StructureActions = {
  insert: (source: PlacementSource, target?: PlacementTarget) => void;
  startDrag: (source: PlacementSource, event: DragEvent) => void;
  endDrag: () => void;
  selected?: PaperQuestion;
};

export function CandidateActions({ topic, part, actions, disabled = false, fallback }: {
  topic: string; part: Part; actions?: StructureActions; disabled?: boolean; fallback?: () => void;
}) {
  const source: PlacementSource = { kind: "candidate", topic, part };
  return <div className="flex flex-wrap items-center gap-2">
    {actions && <Button variant="ghost" size="sm" disabled={disabled} draggable={!disabled}
      aria-label="Drag question into paper" className="cursor-grab active:cursor-grabbing"
      onDragStart={e => actions.startDrag(source, e)} onDragEnd={actions.endDrag}>
      <GripVertical className="size-4" aria-hidden="true" /> Drag
    </Button>}
    <Button size="sm" disabled={disabled} onClick={() => actions ? actions.insert(source) : fallback?.()}>Add to paper</Button>
    {actions?.selected && <Button size="sm" variant="outline" disabled={disabled || actions.selected.topic !== topic}
      title={actions.selected.topic !== topic ? "Subparts must share the question's topic" : undefined}
      onClick={() => actions.insert(source, { question: actions.selected!.question_number - 1, part: actions.selected!.parts.length })}>
      Add to Q{actions.selected.question_number}
    </Button>}
  </div>;
}

export function DropZone({ active, label, onDrop }: { active: boolean; label: string; onDrop: () => void }) {
  const [over, setOver] = useState(false);
  if (!active) return null;
  return <div onDragOver={e => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; setOver(true); }}
    onDragLeave={() => setOver(false)} onDrop={e => { e.preventDefault(); e.stopPropagation(); setOver(false); onDrop(); }}
    className={`rounded border-2 border-dashed px-3 py-2 text-xs text-center ${over ? "border-primary bg-primary/15 text-foreground" : "border-muted-foreground/40 text-muted-foreground"}`}>
    {over ? `Drop here: ${label}` : label}
  </div>;
}

export function MoveControls({ label, source, actions, up, down }: {
  label: string; source: PlacementSource; actions: StructureActions; up?: PlacementTarget; down?: PlacementTarget;
}) {
  return <div className="flex items-center gap-1 shrink-0">
    <Button size="icon" variant="ghost" draggable aria-label={`Drag ${label}`} className="cursor-grab active:cursor-grabbing"
      onDragStart={e => actions.startDrag(source, e)} onDragEnd={actions.endDrag}><GripVertical className="size-4" aria-hidden="true" /></Button>
    <Button size="icon" variant="ghost" aria-label={`Move ${label} up`} disabled={!up}
      onClick={() => up && actions.insert(source, up)}><ArrowUp className="size-4" aria-hidden="true" /></Button>
    <Button size="icon" variant="ghost" aria-label={`Move ${label} down`} disabled={!down}
      onClick={() => down && actions.insert(source, down)}><ArrowDown className="size-4" aria-hidden="true" /></Button>
  </div>;
}
