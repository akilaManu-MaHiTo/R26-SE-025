import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../ui/table";
import { Workflow, Target, AlertTriangle, CheckCircle2, XCircle, Eye } from "lucide-react";
import type { DiagramAnalysis } from "../../api/lecturerApi";

interface Props {
  diagramAnalysis: DiagramAnalysis;
}

function StatusDot({ status }: { status: string }) {
  const color =
    status === "Strong"
      ? "bg-emerald-500"
      : status === "Developing"
        ? "bg-blue-500"
        : status === "Needs Improvement"
          ? "bg-amber-500"
          : "bg-red-500";
  return <span className={`inline-block size-2 rounded-full ${color}`} />;
}

export function DiagramAnalysisPanel({ diagramAnalysis }: Props) {
  const { statistics, criterion_performance, student_summaries, detection_summary, weakest_criteria, insights } =
    diagramAnalysis;

  return (
    <div className="space-y-4">
      {/* KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card className="p-4">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Workflow className="size-3.5" />
            Avg Score
          </div>
          <div className="mt-2 text-xl font-semibold tabular-nums">{statistics.average_percentage.toFixed(1)}%</div>
          <div className="text-xs text-muted-foreground mt-0.5">
            {statistics.average_score.toFixed(1)} / {statistics.max_score.toFixed(1)}
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <CheckCircle2 className="size-3.5" />
            Pass Rate
          </div>
          <div className="mt-2 text-xl font-semibold tabular-nums">{statistics.pass_rate.toFixed(0)}%</div>
          <div className="text-xs text-muted-foreground mt-0.5">
            {statistics.total_students} students
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Target className="size-3.5" />
            Highest
          </div>
          <div className="mt-2 text-xl font-semibold tabular-nums">{statistics.highest_score.toFixed(1)}</div>
          <div className="text-xs text-muted-foreground mt-0.5">/ {statistics.max_score.toFixed(1)}</div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <AlertTriangle className="size-3.5" />
            Lowest
          </div>
          <div className="mt-2 text-xl font-semibold tabular-nums">{statistics.lowest_score.toFixed(1)}</div>
          <div className="text-xs text-muted-foreground mt-0.5">/ {statistics.max_score.toFixed(1)}</div>
        </Card>
      </div>

      {/* Detection Summary */}
      {detection_summary && (
        <Card className="p-4">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Eye className="size-4 text-primary" />
            Detection Summary
          </div>
          <div className="mt-3 grid grid-cols-2 sm:grid-cols-5 gap-4 text-sm">
            <div>
              <div className="text-muted-foreground text-xs">Avg Entities</div>
              <div className="font-medium tabular-nums">{detection_summary.avg_entity_count}</div>
            </div>
            <div>
              <div className="text-muted-foreground text-xs">Avg Relationships</div>
              <div className="font-medium tabular-nums">{detection_summary.avg_relationship_count}</div>
            </div>
            <div>
              <div className="text-muted-foreground text-xs">Avg Labels</div>
              <div className="font-medium tabular-nums">{detection_summary.avg_label_count}</div>
            </div>
            <div>
              <div className="text-muted-foreground text-xs">Total Detections</div>
              <div className="font-medium tabular-nums">{detection_summary.total_detections}</div>
            </div>
            <div>
              <div className="text-muted-foreground text-xs">Avg Marking Score</div>
              <div className="font-medium tabular-nums">{detection_summary.avg_marking_score}</div>
            </div>
          </div>
        </Card>
      )}

      {/* Criterion Performance */}
      <Card className="overflow-hidden">
        <div className="p-4 border-b">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Target className="size-4 text-primary" />
            Rubric Criterion Breakdown
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Per-criterion pass/partial/fail rates across all students.
          </p>
        </div>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/40">
                <TableHead className="text-xs uppercase tracking-wider font-semibold text-muted-foreground">Criterion</TableHead>
                <TableHead className="text-center text-xs uppercase tracking-wider font-semibold text-muted-foreground">Max</TableHead>
                <TableHead className="text-center text-xs uppercase tracking-wider font-semibold text-muted-foreground">Avg</TableHead>
                <TableHead className="text-center text-xs uppercase tracking-wider font-semibold text-muted-foreground">%</TableHead>
                <TableHead className="text-center text-xs uppercase tracking-wider font-semibold text-muted-foreground">Pass</TableHead>
                <TableHead className="text-center text-xs uppercase tracking-wider font-semibold text-muted-foreground">Partial</TableHead>
                <TableHead className="text-center text-xs uppercase tracking-wider font-semibold text-muted-foreground">Fail</TableHead>
                <TableHead className="text-center text-xs uppercase tracking-wider font-semibold text-muted-foreground">Fail Rate</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {criterion_performance.map((c) => (
                <TableRow key={c.criterion_id} className="h-11">
                  <TableCell className="text-xs font-medium max-w-[280px] truncate" title={c.criterion}>
                    <span className="text-muted-foreground mr-1.5">#{c.criterion_id}</span>
                    {c.criterion}
                  </TableCell>
                  <TableCell className="text-center text-xs tabular-nums">{c.max_marks}</TableCell>
                  <TableCell className="text-center text-xs tabular-nums">{c.average_awarded_marks}</TableCell>
                  <TableCell className="text-center text-xs tabular-nums font-medium">
                    <span className={c.average_percentage >= 80 ? "text-emerald-700" : c.average_percentage >= 50 ? "text-amber-700" : "text-red-700"}>
                      {c.average_percentage.toFixed(0)}%
                    </span>
                  </TableCell>
                  <TableCell className="text-center">
                    <span className="inline-flex items-center gap-1 text-xs text-emerald-700">
                      <CheckCircle2 className="size-3" /> {c.pass_count}
                    </span>
                  </TableCell>
                  <TableCell className="text-center">
                    <span className="inline-flex items-center gap-1 text-xs text-amber-700">
                      <AlertTriangle className="size-3" /> {c.partial_count}
                    </span>
                  </TableCell>
                  <TableCell className="text-center">
                    <span className="inline-flex items-center gap-1 text-xs text-red-700">
                      <XCircle className="size-3" /> {c.fail_count}
                    </span>
                  </TableCell>
                  <TableCell className="text-center text-xs tabular-nums">
                    <Badge
                      variant="outline"
                      className={c.fail_rate > 0.3 ? "bg-red-500/10 text-red-700 border-red-500/20" : c.fail_rate > 0 ? "bg-amber-500/10 text-amber-700 border-amber-500/20" : "bg-emerald-500/10 text-emerald-700 border-emerald-500/20"}
                    >
                      {(c.fail_rate * 100).toFixed(0)}%
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </Card>

      {/* Weakest Criteria */}
      {weakest_criteria.length > 0 && (
        <Card className="p-4">
          <div className="flex items-center gap-2 text-sm font-medium">
            <AlertTriangle className="size-4 text-amber-600" />
            Weakest Criteria
          </div>
          <div className="mt-3 space-y-2">
            {weakest_criteria.map((wc) => (
              <div key={wc.criterion_id} className="flex items-center gap-3 text-sm">
                <Badge variant="outline" className="bg-red-500/10 text-red-700 border-red-500/20 text-xs shrink-0">
                  {(wc.fail_rate * 100).toFixed(0)}% fail
                </Badge>
                <span className="text-xs text-muted-foreground shrink-0">#{wc.criterion_id}</span>
                <span className="truncate">{wc.criterion}</span>
                <span className="text-xs text-muted-foreground ml-auto shrink-0">
                  {wc.fail_count} student{wc.fail_count !== 1 ? "s" : ""}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Student Diagram Scores */}
      <Card className="overflow-hidden">
        <div className="p-4 border-b">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Workflow className="size-4 text-primary" />
            Student Diagram Scores
          </div>
        </div>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/40">
                <TableHead className="text-xs uppercase tracking-wider font-semibold text-muted-foreground">Student</TableHead>
                <TableHead className="text-center text-xs uppercase tracking-wider font-semibold text-muted-foreground">Score</TableHead>
                <TableHead className="text-center text-xs uppercase tracking-wider font-semibold text-muted-foreground">%</TableHead>
                <TableHead className="text-xs uppercase tracking-wider font-semibold text-muted-foreground">Status</TableHead>
                <TableHead className="text-xs uppercase tracking-wider font-semibold text-muted-foreground">Feedback</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {student_summaries.map((s) => (
                <TableRow key={s.student_id} className="h-11">
                  <TableCell className="text-xs font-medium font-mono">{s.student_id}</TableCell>
                  <TableCell className="text-center text-xs tabular-nums">
                    {s.score.toFixed(1)} / {s.max_score.toFixed(1)}
                  </TableCell>
                  <TableCell className="text-center text-xs tabular-nums font-medium">
                    <span className={s.percentage >= 80 ? "text-emerald-700" : s.percentage >= 50 ? "text-amber-700" : "text-red-700"}>
                      {s.percentage.toFixed(1)}%
                    </span>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5">
                      <StatusDot status={s.status} />
                      <Badge variant="outline" className="text-xs">{s.status}</Badge>
                    </div>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground max-w-[300px] truncate" title={s.feedback}>
                    {s.feedback}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </Card>

      {/* Insights */}
      {insights.length > 0 && (
        <Card className="p-4">
          <div className="text-sm font-medium mb-2">Diagram Insights</div>
          <ul className="space-y-1.5">
            {insights.map((insight, i) => (
              <li key={i} className="text-xs text-muted-foreground flex items-start gap-2">
                <span className="text-primary mt-0.5">•</span>
                {insight}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
