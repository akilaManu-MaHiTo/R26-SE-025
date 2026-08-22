import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  Layers3,
  RefreshCw,
  Search,
  Shapes,
  Workflow,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Separator } from "./ui/separator";
import { AIPageBanner, AIBadgePill } from "./AIBrand";

const API_BASE_URL =
  (import.meta as { env?: Record<string, string> }).env?.VITE_API_BASE_URL ??
  "http://127.0.0.1:8000";

type DiagramDetailRecord = {
  _id?: string;
  student_id?: string;
  subject_code?: string;
  subject_name?: string;
  year?: number;
  month?: number;
  semester?: number;
  session_name?: string;
  diagram_marks?: number;
  diagram_details?: {
    label_count?: number;
    entity_count?: number;
    relationship_count?: number;
    detections?: Array<{
      id?: string | number;
      label?: string;
      text?: string;
      bbox?: [number, number, number, number];
      confidence?: number;
    }>;
    entities?: Array<{
      entity_name?: string;
      attributes?: string[];
    }>;
    relationships?: Array<{
      relation_name?: string;
      entities?: string[];
      attributes?: string[];
    }>;
    structure?: {
      entities?: Record<string, { attributes?: string[] }>;
      relationships?: Array<{
        name?: string;
        entities?: string[];
        attributes?: string[];
      }>;
    };
  };
  diagram_entity_relations?: Array<{
    entity_name?: string;
    attributes?: string[];
  }>;
  diagram_relations?: Array<{
    relation_name?: string;
    entities?: string[];
    attributes?: string[];
  }>;
  evaluation_result?: {
    annotated_image?: string;
    structure?: {
      entities?: Record<string, { attributes?: string[] }>;
      relationships?: Array<{
        name?: string;
        entities?: string[];
        attributes?: string[];
      }>;
    };
  };
  created_at?: string;
};

function parseJsonResponse(response: Response): Promise<unknown> {
  return response.text().then((text) => {
    if (!text.trim()) return {};
    try {
      return JSON.parse(text);
    } catch {
      return { detail: text.slice(0, 200) };
    }
  });
}

function normalizeStructure(record: DiagramDetailRecord) {
  const details = record.diagram_details ?? {};
  const structure = details.structure ?? record.evaluation_result?.structure ?? {};

  const entityEntries = Object.entries(structure.entities ?? {});
  const relationshipEntries = structure.relationships ?? [];

  const entities = entityEntries.map(([name, value]) => ({
    name,
    attributes: value.attributes ?? [],
  }));

  const relationships = relationshipEntries.map((relationship) => ({
    name: relationship.name ?? "Relationship",
    entities: relationship.entities ?? [],
    attributes: relationship.attributes ?? [],
  }));

  return { entities, relationships };
}

export function DiagramReconstructionPage() {
  const [records, setRecords] = useState<DiagramDetailRecord[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    const loadRecords = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`${API_BASE_URL}/api/diagram-evaluate-details`);
        const data = (await parseJsonResponse(response)) as DiagramDetailRecord[] | { detail?: unknown };
        if (!response.ok) {
          const detail = data && typeof data === "object" ? (data as { detail?: unknown }).detail : null;
          throw new Error(typeof detail === "string" ? detail : "Failed to load diagram evaluations.");
        }
        if (!active) return;
        const list = Array.isArray(data) ? data : [];
        setRecords(list);
        setSelectedId((current) => current || list[0]?._id || "");
      } catch (loadError) {
        if (!active) return;
        setRecords([]);
        setError(loadError instanceof Error ? loadError.message : "Failed to load diagram evaluations.");
      } finally {
        if (active) setLoading(false);
      }
    };

    void loadRecords();

    return () => {
      active = false;
    };
  }, []);

  const selectedRecord = useMemo(
    () => records.find((record) => record._id === selectedId) ?? records[0] ?? null,
    [records, selectedId],
  );
  const summary = selectedRecord?.diagram_details ?? {};
  const structure = summary.structure ?? selectedRecord?.evaluation_result?.structure ?? {};
  const entities = Object.entries(structure.entities ?? {});
  const relationships = structure.relationships ?? [];

  return (
    <div className="p-6 md:p-8 space-y-6">
      <AIPageBanner model="structr" />
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-2 max-w-3xl">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Workflow className="size-4" /> Diagram Reconstruction
          </div>
          <h2 className="tracking-tight text-foreground">Recreate the saved ER structure from server details</h2>
          <p className="text-sm text-muted-foreground">
            Load a stored evaluation, inspect the normalized entities and relationships, and visualize the diagram
            structure without uploading a new image.
          </p>
        </div>
        <AIBadgePill model="structr" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(340px,0.8fr)]">
        <Card className="overflow-hidden border-border">
          <CardHeader className="border-b border-border bg-muted/30">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <CardTitle className="text-xl">Saved diagram structure</CardTitle>
                <p className="text-sm text-muted-foreground mt-1">
                  {selectedRecord
                    ? `${selectedRecord.student_id ?? "UNKNOWN"} · ${selectedRecord.subject_code ?? ""} · ${selectedRecord.subject_name ?? ""}`
                    : "Select a stored evaluation to reconstruct."}
                </p>
              </div>
              <Badge variant="secondary" className="w-fit">
                {selectedRecord?.diagram_marks ?? 0} marks
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="border-b border-border p-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="relative w-full sm:max-w-sm">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={selectedId}
                  onChange={(event) => setSelectedId(event.target.value)}
                  placeholder="Paste record _id or pick from the list"
                  className="pl-9"
                />
              </div>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Layers3 className="size-4" />
                {records.length} saved evaluations
                <Button variant="outline" size="sm" onClick={() => window.location.reload()} disabled={loading}>
                  <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />
                  Reload
                </Button>
              </div>
            </div>

            {error ? (
              <div className="p-6 text-sm text-destructive flex items-center gap-2">
                <AlertCircle className="size-4" />
                {error}
              </div>
            ) : null}

            {!error && selectedRecord ? (
              <div className="p-4 space-y-5">
                <div className="grid gap-4 lg:grid-cols-3">
                  <Card className="border-border lg:col-span-2">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base flex items-center gap-2">
                        <Shapes className="size-4" /> Textable structure
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="rounded-2xl border border-border bg-muted/20 p-4">
                        <div className="text-sm font-medium">Entities</div>
                        <div className="mt-3 space-y-3">
                          {entities.map(([name, value]) => (
                            <div key={name} className="rounded-xl border border-border bg-background p-3">
                              <div className="flex items-center justify-between gap-3">
                                <div className="font-medium">{name}</div>
                                <Badge variant="secondary">entity</Badge>
                              </div>
                              <div className="mt-2 text-sm text-muted-foreground">
                                {value.attributes?.length
                                  ? `Attributes: ${value.attributes.join(", ")}`
                                  : "No attributes recorded"}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="rounded-2xl border border-border bg-muted/20 p-4">
                        <div className="text-sm font-medium">Relationships</div>
                        <div className="mt-3 space-y-3">
                          {relationships.map((relationship) => (
                            <div key={relationship.name} className="rounded-xl border border-border bg-background p-3">
                              <div className="flex items-center justify-between gap-3">
                                <div className="font-medium">{relationship.name}</div>
                                <Badge variant="secondary">relationship</Badge>
                              </div>
                              <div className="mt-2 text-sm text-muted-foreground">
                                Connected entities: {(relationship.entities ?? []).join(" ↔ ") || "None"}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  <Card className="border-border">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base flex items-center gap-2">
                        <Workflow className="size-4" /> Summary
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3 text-sm">
                      <div className="flex items-center justify-between"><span>Labels</span><span>{summary.label_count ?? 0}</span></div>
                      <Separator />
                      <div className="flex items-center justify-between"><span>Entities</span><span>{summary.entity_count ?? entities.length}</span></div>
                      <Separator />
                      <div className="flex items-center justify-between"><span>Relationships</span><span>{summary.relationship_count ?? relationships.length}</span></div>
                      <Separator />
                      <div className="flex items-center justify-between"><span>Saved at</span><span>{selectedRecord.created_at ? new Date(selectedRecord.created_at).toLocaleString() : "Unknown"}</span></div>
                      <Separator />
                      <div className="text-muted-foreground">
                        This view is driven only by the stored structure object and shows the reconstructed text for each student.
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </div>
            ) : (
              <div className="p-10 text-center text-muted-foreground">
                <div className="mx-auto mb-3 size-12 rounded-full bg-muted flex items-center justify-center">
                  <RefreshCw className={`size-5 ${loading ? "animate-spin" : ""}`} />
                </div>
                <div className="font-medium text-foreground">{loading ? "Loading evaluations…" : "No saved diagram evaluations found."}</div>
                <p className="mt-1 text-sm max-w-md mx-auto">
                  When the server returns records from <span className="font-medium">/api/diagram-evaluate-details</span>, this page will reconstruct the diagram structure automatically.
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="border-border">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2"><Workflow className="size-4" /> Record picker</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="text-sm text-muted-foreground">
                Use the list to switch between saved evaluations and inspect the structure on the left.
              </div>
              <div className="max-h-[360px] space-y-2 overflow-auto pr-1">
                {records.map((record) => {
                  const isActive = record._id === selectedRecord?._id;
                  return (
                    <button
                      key={record._id}
                      type="button"
                      onClick={() => setSelectedId(record._id ?? "")}
                      className={`w-full rounded-xl border p-3 text-left transition-colors ${isActive ? "border-primary bg-primary/5" : "border-border hover:bg-muted/60"}`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="font-medium truncate">{record.student_id ?? "UNKNOWN"}</div>
                        <Badge variant={isActive ? "default" : "secondary"}>{record.diagram_marks ?? 0}</Badge>
                      </div>
                      <div className="text-xs text-muted-foreground mt-1 truncate">
                        {record.subject_code ?? ""} {record.subject_name ? `· ${record.subject_name}` : ""}
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        {record.session_name ?? "Final Examination"} · {record.year ?? ""}/{record.month ?? ""}
                      </div>
                    </button>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          <Card className="border-border">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2"><AlertCircle className="size-4" /> Source details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div>
                <div className="text-muted-foreground">Entity relations</div>
                <pre className="mt-1 overflow-auto rounded-xl border border-border bg-muted/40 p-3 text-xs whitespace-pre-wrap">
                  {JSON.stringify(selectedRecord?.diagram_entity_relations ?? [], null, 2)}
                </pre>
              </div>
              <div>
                <div className="text-muted-foreground">Diagram relations</div>
                <pre className="mt-1 overflow-auto rounded-xl border border-border bg-muted/40 p-3 text-xs whitespace-pre-wrap">
                  {JSON.stringify(selectedRecord?.diagram_relations ?? [], null, 2)}
                </pre>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
