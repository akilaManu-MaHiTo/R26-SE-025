"use client";

import dynamic from "next/dynamic";

const StudentDashboard = dynamic(
  () => import("@/components/StudentDashboard").then((m) => m.StudentDashboard),
  { ssr: false }
);

export default function StudentDashboardPage() {
  return <StudentDashboard />;
}
