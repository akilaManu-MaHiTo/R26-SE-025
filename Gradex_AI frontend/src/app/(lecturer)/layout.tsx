"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { Sidebar } from "@/components/Sidebar";
import { TopBar } from "@/components/TopBar";
import { Toaster } from "@/components/ui/sonner";

export type Page =
  | "dashboard"
  | "grading-diagram"
  | "grading-handwritten"
  | "analytics"
  | "exam-creator"
  | "viva";

const titleMap: Record<Page, { title: string; subtitle?: string }> = {
  dashboard: { title: "Dashboard", subtitle: "Your AI-powered command center" },
  "grading-diagram": {
    title: "Diagram Grading",
    subtitle: "AI-assisted assessment of structured diagrams",
  },
  "grading-handwritten": {
    title: "Handwritten Grading",
    subtitle: "OCR + rubric matching for scanned papers",
  },
  analytics: { title: "Analytics", subtitle: "Class, cohort and individual insights" },
  "exam-creator": { title: "Exam Creator", subtitle: "Compose balanced, level-appropriate exams" },
  viva: { title: "Viva Assessment", subtitle: "AI-aided viva voce evaluation" },
};

export default function LecturerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { role, setRole } = useAuth();

  // Redirect to login if not a lecturer
  if (role !== "lecturer") {
    router.push("/");
    return null;
  }

  // Get current page from pathname - this will be handled by the page component
  const currentPage: Page = "dashboard";
  const meta = titleMap[currentPage];

  const handleNavigate = (page: Page) => {
    const pageMap: Record<Page, string> = {
      dashboard: "/dashboard",
      "grading-diagram": "/grading-diagram",
      "grading-handwritten": "/grading-handwritten",
      analytics: "/analytics",
      "exam-creator": "/exam-creator",
      viva: "/viva",
    };
    router.push(pageMap[page]);
  };

  return (
    <div className="flex bg-slate-50 min-h-screen text-slate-900">
      <Sidebar
        current={currentPage}
        onNavigate={handleNavigate}
        role="lecturer"
        onLogout={() => {
          setRole(null);
          router.push("/");
        }}
      />
      <main className="flex-1 min-w-0 flex flex-col">
        <TopBar title={meta.title} subtitle={meta.subtitle} />
        <div className="flex-1">{children}</div>
      </main>
      <Toaster />
    </div>
  );
}
