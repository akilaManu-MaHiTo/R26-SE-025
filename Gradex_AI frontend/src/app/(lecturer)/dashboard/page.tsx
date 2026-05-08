"use client";

import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import type { Page } from "@/components/Sidebar";

const LecturerDashboard = dynamic(
  () => import("@/components/LecturerDashboard").then((m) => m.LecturerDashboard),
  { ssr: false }
);

export default function DashboardPage() {
  const router = useRouter();

  const handleNavigate = (page: Page) => {
    const pageMap: Record<Page, string> = {
      dashboard: "/dashboard",
      "grading-diagram": "/grading-diagram",
      "grading-handwritten": "/grading-handwritten",
      analytics: "/analytics",
      "exam-creator": "/exam-creator",
      viva: "/viva",
      "student-dashboard": "/student-dashboard",
    };
    router.push(pageMap[page]);
  };

  return <LecturerDashboard onNavigate={handleNavigate} />;
}
