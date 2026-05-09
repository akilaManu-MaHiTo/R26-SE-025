import { useState } from "react";
import { Sidebar, type Page } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { LoginPage } from "./components/LoginPage";
import { LecturerDashboard } from "./components/LecturerDashboard";
import { GradingPage } from "./components/GradingPage";
import { AnalyticsPage } from "./components/AnalyticsPage";
import { ExamCreator } from "./components/ExamCreator";
import { VivaPage } from "./components/VivaPage";
import { StudentDashboard } from "./components/StudentDashboard";
import { Toaster } from "./components/ui/sonner";

type Role = "lecturer" | "student";

const titleMap: Record<Page, { title: string; subtitle?: string }> = {
  "dashboard": { title: "Dashboard", subtitle: "Your AI-powered command center" },
  "grading-diagram": { title: "Diagram Grading", subtitle: "AI-assisted assessment of structured diagrams" },
  "grading-handwritten": { title: "Handwritten Grading", subtitle: "OCR + rubric matching for scanned papers" },
  "analytics": { title: "Analytics", subtitle: "Class, cohort and individual insights" },
  "exam-creator": { title: "Exam Creator", subtitle: "Compose balanced, level-appropriate exams" },
  "viva": { title: "Viva Assessment", subtitle: "AI-aided viva voce evaluation" },
  "student-dashboard": { title: "My Dashboard", subtitle: "Track your progress and upcoming work" },
};

export default function App() {
  const [role, setRole] = useState<Role | null>(null);
  const [page, setPage] = useState<Page>("dashboard");

  if (!role) {
    return (
      <>
        <LoginPage
          onLogin={(r) => {
            setRole(r);
            setPage(r === "lecturer" ? "dashboard" : "student-dashboard");
          }}
        />
        <Toaster />
      </>
    );
  }

  const meta = titleMap[page];

  return (
    <div className="flex bg-slate-50 min-h-screen text-slate-900">
      <Sidebar
        current={page}
        onNavigate={setPage}
        role={role}
        onLogout={() => setRole(null)}
      />
      <main className="flex-1 min-w-0 flex flex-col">
        <TopBar title={meta.title} subtitle={meta.subtitle} />
        <div className="flex-1">
          {page === "dashboard" && <LecturerDashboard onNavigate={setPage} />}
          {page === "grading-diagram" && <GradingPage mode="diagram" />}
          {page === "grading-handwritten" && <GradingPage mode="handwritten" />}
          {page === "analytics" && <AnalyticsPage />}
          {page === "exam-creator" && <ExamCreator />}
          {page === "viva" && <VivaPage />}
          {page === "student-dashboard" && <StudentDashboard />}
        </div>
      </main>
      <Toaster />
    </div>
  );
}
