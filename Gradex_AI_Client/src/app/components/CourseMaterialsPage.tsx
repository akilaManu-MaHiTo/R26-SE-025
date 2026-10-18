import { useCallback, useEffect, useRef, useState } from "react";
import { BookOpen, FileText, RefreshCw, Trash2, Upload } from "lucide-react";
import { listMaterials, uploadMaterial, replaceMaterial, removeMaterial, materialPdfUrl,
  type CourseMaterial, type DocumentType } from "../api/courseMaterialsApi";
import { fetchTaxonomyCourses } from "../api/taxonomyApi";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Input } from "./ui/input";
import { Badge } from "./ui/badge";
import { AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction } from "./ui/alert-dialog";

const labels: Record<DocumentType, string> = { lecture: "Lecture", tutorial: "Tutorial", exam: "Past exam" };
const selectClass = "w-full rounded-md border border-input bg-background p-2 text-sm";
function validPdf(file: File) {
  if (!file.name.toLowerCase().endsWith(".pdf") || !file.size) throw new Error("Choose a nonempty PDF file.");
  if (file.size > 20 * 1024 * 1024) throw new Error("PDF must be 20 MB or smaller.");
}

export function CourseMaterialsPage() {
  const [items, setItems] = useState<CourseMaterial[]>([]);
  const [courseOptions, setCourseOptions] = useState<string[]>([]);
  const [course, setCourse] = useState("");
  const [type, setType] = useState<DocumentType>("lecture");
  const [year, setYear] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [showAll, setShowAll] = useState(true);
  const [typeFilter, setTypeFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [pending, setPending] = useState<{ action: "remove" | "replace"; item: CourseMaterial } | null>(null);
  const [replacement, setReplacement] = useState<File | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const inventory = await listMaterials();
      setItems(inventory.items); setWarnings(inventory.warnings);
      setCourse(current => current || inventory.items[0]?.course_code || "");
    } catch (err) { setError(err instanceof Error ? err.message : "Could not load materials."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    let cancelled = false;
    fetchTaxonomyCourses().then(courses => {
      if (!cancelled) setCourseOptions(courses.map(c => c.code));
    }).catch(() => { /* Indexed courses and manual course entry remain available. */ });
    return () => { cancelled = true; };
  }, []);

  async function upload() {
    if (!file) return;
    setError(""); setSuccess("");
    try {
      validPdf(file);
      const code = course.trim().toUpperCase();
      if (!/^[A-Z0-9_-]{1,50}$/.test(code)) throw new Error("Enter a valid course code, such as IT2040.");
      const parsedYear = year ? Number(year) : undefined;
      if (parsedYear !== undefined && (!Number.isInteger(parsedYear) || parsedYear < 1900 || parsedYear > 2200)) throw new Error("Year must be between 1900 and 2200.");
      setBusy(true);
      const result = await uploadMaterial(file, code, type, parsedYear);
      setSuccess(`Indexed ${result.item.filename} for ${code}. It is now available to Exam Creator.`);
      setFile(null); if (fileInput.current) fileInput.current.value = "";
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Upload failed."); }
    finally { setBusy(false); }
  }

  async function confirm() {
    if (!pending) return;
    setError(""); setSuccess("");
    try {
      if (pending.action === "replace") {
        if (!replacement) throw new Error("Choose a replacement PDF.");
        validPdf(replacement);
      }
      setBusy(true);
      if (pending.action === "remove") await removeMaterial(pending.item.document_id);
      else await replaceMaterial(pending.item.document_id, replacement!);
      setSuccess(pending.action === "remove" ? `Removed ${pending.item.filename} from retrieval.` : `Updated ${pending.item.filename}.`);
      setPending(null); setReplacement(null);
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not update this material."); }
    finally { setBusy(false); }
  }

  const filtered = items.filter(item => (showAll || item.course_code === course.trim().toUpperCase()) &&
    (typeFilter === "all" || item.document_type === typeFilter));
  const courses = Array.from(new Set([...courseOptions, ...items.map(item => item.course_code)])).sort();
  return <div className="space-y-6">
    <div>
      <h2 className="flex items-center gap-2 text-xl font-semibold"><BookOpen className="size-5" />Course Materials</h2>
      <p className="mt-2 text-sm text-muted-foreground">Manage lectures, tutorials and past exam PDFs used by Exam Creator. Your previously indexed materials are included below.</p>
    </div>
    <Card className="p-4 space-y-4">
      <h3 className="font-semibold">Upload course material</h3>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="text-sm">Course code<Input list="material-courses" value={course} onChange={e => setCourse(e.target.value.toUpperCase())} placeholder="IT2040" disabled={busy} /></label>
        <datalist id="material-courses">{courses.map(code => <option key={code} value={code} />)}</datalist>
        <label className="text-sm">Material type<select className={selectClass} value={type} onChange={e => setType(e.target.value as DocumentType)} disabled={busy}>
          {Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select></label>
        <label className="text-sm">Year (optional)<Input type="number" min={1900} max={2200} value={year} onChange={e => setYear(e.target.value)} disabled={busy} /></label>
      </div>
      <label className="block text-sm">PDF file<Input ref={fileInput} type="file" accept=".pdf,application/pdf" onChange={e => setFile(e.target.files?.[0] ?? null)} disabled={busy} /></label>
      <p className="text-xs text-muted-foreground">PDF only, up to 20 MB. Text is extracted and indexed; scanned pages and diagrams may need separate preparation. Use Replace below to update an existing file.</p>
      <Button onClick={() => void upload()} disabled={busy || !file || !course.trim()}>
        {busy ? <RefreshCw className="size-4 animate-spin" /> : <Upload className="size-4" />} {busy ? "Updating materials…" : "Upload and index"}
      </Button>
      {busy && <p role="status" className="text-xs text-muted-foreground">Please wait while the material index is updated.</p>}
    </Card>
    {error && !pending && <p role="alert" className="text-sm text-destructive">{error}</p>}
    {success && <p role="status" className="text-sm text-emerald-700 dark:text-emerald-400">{success}</p>}
    {warnings.map(warning => <p key={warning} className="text-sm text-amber-700">{warning}</p>)}
    <Card className="p-4 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div><h3 className="font-semibold">Indexed materials</h3><p className="text-xs text-muted-foreground">{items.length} materials · {items.reduce((n, item) => n + item.pages, 0)} pages · {items.reduce((n, item) => n + item.chunks, 0)} indexed passages</p></div>
        <Button variant="outline" disabled={loading || busy} onClick={() => { setError(""); void load(); }}><RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />Refresh</Button>
      </div>
      <div className="flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={showAll} onChange={e => setShowAll(e.target.checked)} />Show all courses</label>
        <label className="text-sm">Material type filter<select className={selectClass} value={typeFilter} onChange={e => setTypeFilter(e.target.value)}>
          <option value="all">All materials</option>{Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select></label>
      </div>
      {loading ? <p role="status">Loading materials…</p> : filtered.length === 0 ? <p className="text-sm text-muted-foreground">No materials match this selection. Upload a PDF above or change the filters.</p> :
        <div className="space-y-3">{filtered.map(item => <div key={item.document_id} className="rounded-lg border p-3 space-y-2">
          <div className="flex items-start gap-2"><FileText className="size-4 shrink-0 mt-1 text-primary" /><p className="text-sm font-medium break-all">{item.filename}</p></div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground"><Badge variant="outline">{labels[item.document_type]}</Badge><span>{item.course_code}{item.year ? ` · ${item.year}` : ""}</span><span>{item.pages} pages · {item.chunks} passages</span><span>{item.mode === "hybrid" ? "Semantic + keyword index" : "Keyword index"}</span></div>
          {!!item.empty_pages.length && <p className="text-xs text-amber-700">Text-poor pages skipped: {item.empty_pages.join(", ")}. Review the original PDF.</p>}
          {item.warnings.map(warning => <p key={warning} className="text-xs text-amber-700">{warning}</p>)}
          <div className="flex flex-wrap gap-2">
            {item.pdf_available && <Button asChild size="sm" variant="outline"><a href={materialPdfUrl(item.document_id)} target="_blank" rel="noreferrer" aria-label={`Open ${item.filename}`}>Open PDF</a></Button>}
            <Button size="sm" variant="outline" disabled={busy} aria-label={`Replace ${item.filename}`} onClick={() => { setError(""); setReplacement(null); setPending({ action: "replace", item }); }}>Replace</Button>
            <Button size="sm" variant="ghost" disabled={busy} aria-label={`Remove ${item.filename}`} onClick={() => { setError(""); setPending({ action: "remove", item }); }}><Trash2 className="size-4" />Remove</Button>
          </div>
        </div>)}</div>}
    </Card>
    <AlertDialog open={!!pending} onOpenChange={open => { if (!open && !busy) { setPending(null); setError(""); } }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{pending?.action === "remove" ? "Remove course material?" : "Replace course material?"}</AlertDialogTitle>
          <AlertDialogDescription>{pending?.action === "remove"
            ? `Remove ${pending.item.filename} and its indexed passages? Future searches will stop using this document. Bundled source files and existing exam drafts are preserved.`
            : `Replace the contents of ${pending?.item.filename}? Its course, material type, year and filename will stay the same. The previous version stays available if indexing fails.`}</AlertDialogDescription>
        </AlertDialogHeader>
        {pending?.action === "replace" && <label className="text-sm">Replacement PDF<Input type="file" accept=".pdf,application/pdf" disabled={busy} onChange={e => setReplacement(e.target.files?.[0] ?? null)} /></label>}
        {error && pending && <p role="alert" className="text-sm text-destructive">{error}</p>}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={busy}>Cancel</AlertDialogCancel>
          <AlertDialogAction disabled={busy || (pending?.action === "replace" && !replacement)} onClick={e => { e.preventDefault(); void confirm(); }}>
            {busy ? "Updating…" : pending?.action === "remove" ? "Remove material" : "Replace material"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </div>;
}
