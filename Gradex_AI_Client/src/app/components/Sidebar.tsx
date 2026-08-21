import { LayoutDashboard, FileCheck2, FileText, Video, BarChart3, GraduationCap, LogOut, Sparkles } from "lucide-react";
import { Button } from "./ui/button";
import { cn } from "./ui/utils";

export type Page =
  | "dashboard"
  | "grading-diagram"
  | "grading-handwritten"
  | "analytics"
  | "exam-creator"
  | "viva"
  | "student-dashboard";

interface SidebarProps {
  current: Page;
  onNavigate: (p: Page) => void;
  role: "lecturer" | "student";
  onLogout: () => void;
}

export function Sidebar({ current, onNavigate, role, onLogout }: SidebarProps) {
  const lecturerItems: { id: Page; label: string; icon: any }[] = [
    { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
    { id: "grading-diagram", label: "Diagram Grading", icon: FileCheck2 },
    { id: "grading-handwritten", label: "Handwritten Grading", icon: FileText },
    { id: "analytics", label: "Student Analytics", icon: BarChart3 },
    { id: "exam-creator", label: "Exam Creator", icon: GraduationCap },
    { id: "viva", label: "Viva Assessment", icon: Video },
  ];

  const studentItems: { id: Page; label: string; icon: any }[] = [
    { id: "student-dashboard", label: "My Dashboard", icon: LayoutDashboard },
  ];

  const items = role === "lecturer" ? lecturerItems : studentItems;

  return (
    <aside className="w-64 shrink-0 bg-white border-r border-slate-200 flex flex-col h-screen sticky top-0">
      <div className="px-6 py-5 border-b border-slate-100 flex items-center gap-2.5">
        <div className="size-9 rounded-xl bg-gradient-to-br from-blue-600 to-blue-500 flex items-center justify-center shadow-sm shadow-blue-200">
          <Sparkles className="size-5 text-white" />
        </div>
        <div className="leading-tight">
          <div className="text-slate-900 tracking-tight">GradeX AI</div>
          <div className="text-xs text-slate-500">Learning Suite</div>
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {items.map((it) => {
          const Icon = it.icon;
          const active = current === it.id;
          return (
            <button
              key={it.id}
              onClick={() => onNavigate(it.id)}
              className={cn(
                "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors",
                active
                  ? "bg-blue-50 text-blue-700"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900",
              )}
            >
              <Icon className={cn("size-4", active && "text-blue-600")} />
              <span>{it.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="p-3 border-t border-slate-100">
        <div className="flex items-center gap-3 p-3 rounded-lg bg-slate-50">
          <div className="size-9 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 text-white flex items-center justify-center text-sm">
            {role === "lecturer" ? "DR" : "ST"}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm text-slate-900 truncate">
              {role === "lecturer" ? "Dr. R. Mendis" : "Sahan Perera"}
            </div>
            <div className="text-xs text-slate-500 truncate capitalize">{role}</div>
          </div>
          <Button variant="ghost" size="icon" onClick={onLogout} className="size-8">
            <LogOut className="size-4" />
          </Button>
        </div>
      </div>
    </aside>
  );
}
