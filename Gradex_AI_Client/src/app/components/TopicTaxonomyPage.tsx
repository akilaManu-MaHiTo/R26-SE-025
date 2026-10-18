import { useEffect, useState } from "react";
import { toast } from "sonner";
import { formatCourseLabel, type CourseItem } from "../utils/courseOptions";
import { fetchTaxonomyCourses, fetchTaxonomy, fetchTaxonomyHistory, saveTaxonomy, type TaxonomyDocument, type TaxonomyTopic, type TaxonomyVersion } from "../api/taxonomyApi";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";

export function TopicTaxonomyPage() {
  const [courses, setCourses] = useState<CourseItem[]>([]);
  const [courseCode, setCourseCode] = useState("");
  const [selectedVersion, setSelectedVersion] = useState("latest");
  const [document, setDocument] = useState<TaxonomyDocument | null>(null);
  const [history, setHistory] = useState<TaxonomyVersion[]>([]);
  const [dirty, setDirty] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const [newTopic, setNewTopic] = useState("");
  const readonly = selectedVersion !== "latest";

  useEffect(() => {
    let cancelled = false;
    fetchTaxonomyCourses().then((items) => {
      if (cancelled) return;
      setCourses(items);
      setCourseCode((current) => current || items.find((item) => item.code === "IT2040")?.code || items[0]?.code || "");
      if (!items.length) { setError("Create a course before editing its taxonomy."); setLoading(false); }
    }).catch((err) => { if (!cancelled) { setError(err.message); setLoading(false); } });
    return () => { cancelled = true; };
  }, [reload]);

  useEffect(() => {
    if (!courseCode) return;
    let cancelled = false;
    setLoading(true);
    setError("");
    Promise.all([
      fetchTaxonomy(courseCode, readonly ? Number(selectedVersion) : undefined),
      fetchTaxonomyHistory(courseCode),
    ]).then(([next, versions]) => {
      if (cancelled) return;
      setDocument(next); setHistory(versions); setDirty(false); setNewTopic("");
    }).catch((err) => { if (!cancelled) setError(err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [courseCode, selectedVersion, reload]);

  function discardDraft() {
    return !dirty || window.confirm("Discard unsaved taxonomy changes?");
  }

  function editTopic(id: string, changes: Partial<TaxonomyTopic>) {
    setDocument((current) => current && ({ ...current, topics: { ...current.topics, [id]: { ...current.topics[id], ...changes } } }));
    setDirty(true);
  }

  function addTopic() {
    const name = newTopic.trim();
    const id = name.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 64).replace(/_+$/, "");
    if (!document || name.length < 3 || id.length < 2) { toast.error("Enter a topic name with at least three characters."); return; }
    if (document.topics[id]) { toast.error("That topic already exists."); return; }
    editTopic(id, { canonical_topic: name, aliases: [], subtopics: [] });
    setNewTopic("");
  }

  async function save() {
    if (!document || readonly) return;
    setSaving(true);
    try {
      const next = await saveTaxonomy(courseCode, document);
      setDocument(next); setDirty(false);
      toast.success(`Saved V${next.version}. Reanalyze exams to apply this taxonomy.`);
      setReload((value) => value + 1);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save taxonomy");
    } finally { setSaving(false); }
  }

  return (
    <div className="p-8 space-y-6">
      <div>
        <h2 className="text-2xl font-semibold">Topic Taxonomy</h2>
        <p className="text-sm text-muted-foreground mt-1">Manage topic names, aliases and subtopics. Each save preserves the previous version. Reanalyze exams to apply changes.</p>
      </div>
      <div className="flex flex-wrap items-end gap-4">
        <label className="grid gap-1 text-sm">Course
          <select className="border rounded-md p-2 bg-background" value={courseCode} disabled={loading || saving} onChange={(event) => {
            if (!discardDraft()) return;
            setSelectedVersion("latest"); setCourseCode(event.target.value);
          }}>
            {!courses.length && <option value="">No courses</option>}
            {courses.map((course) => <option key={course.code} value={course.code}>{formatCourseLabel(course)}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-sm">Version
          <select className="border rounded-md p-2 bg-background" value={selectedVersion} disabled={loading || saving} onChange={(event) => {
            if (discardDraft()) setSelectedVersion(event.target.value);
          }}>
            <option value="latest">Latest{document && !readonly ? ` — V${document.version}` : ""} (editable)</option>
            {history.map((version) => <option key={version.version} value={version.version}>V{version.version}{version.updated_at ? ` — ${new Date(version.updated_at).toLocaleString()}` : ""}</option>)}
          </select>
        </label>
        <Button variant="outline" disabled={loading || saving} onClick={() => { if (discardDraft()) setReload((value) => value + 1); }}>Refresh</Button>
        {!readonly && <Button disabled={!dirty || loading || saving || !!error} onClick={save}>{saving ? "Saving…" : `Save as V${(document?.version ?? 0) + 1}`}</Button>}
      </div>
      {error && <p role="alert" className="text-destructive">{error}</p>}
      {loading ? <p role="status">Loading taxonomy…</p> : !error && document && <>
        {readonly && <p className="text-sm text-muted-foreground">Viewing V{document.version}. Select Latest to edit. Historical versions are read-only.</p>}
        <fieldset disabled={readonly || saving} className="space-y-4">
          {Object.entries(document.topics).map(([id, topic]) => (
            <Card key={id} className="p-5 space-y-3">
              <label className="grid gap-1 text-sm">Topic name
                <Input value={topic.canonical_topic} maxLength={120} onChange={(event) => editTopic(id, { canonical_topic: event.target.value })} />
              </label>
              <div className="grid md:grid-cols-2 gap-4">
                <label className="grid gap-1 text-sm">Aliases (one per line)
                  <Textarea value={topic.aliases.join("\n")} rows={4} onChange={(event) => editTopic(id, { aliases: event.target.value.split("\n") })} />
                </label>
                <label className="grid gap-1 text-sm">Subtopics (one per line)
                  <Textarea value={topic.subtopics.join("\n")} rows={4} onChange={(event) => editTopic(id, { subtopics: event.target.value.split("\n") })} />
                </label>
              </div>
            </Card>
          ))}
          {!readonly && <div className="flex gap-3">
            <Input aria-label="New topic name" placeholder="New topic name" value={newTopic} onChange={(event) => setNewTopic(event.target.value)} />
            <Button variant="outline" onClick={addTopic}>Add topic</Button>
          </div>}
        </fieldset>
      </>}
    </div>
  );
}
