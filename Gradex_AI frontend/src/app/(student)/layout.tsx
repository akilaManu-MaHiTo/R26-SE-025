"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { Sidebar } from "@/components/Sidebar";
import { TopBar } from "@/components/TopBar";
import { Toaster } from "@/components/ui/sonner";

export default function StudentLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { role, setRole } = useAuth();

  // Redirect to login if not a student
  if (role !== "student") {
    router.push("/");
    return null;
  }

  return (
    <div className="flex bg-slate-50 min-h-screen text-slate-900">
      <Sidebar
        current="student-dashboard"
        onNavigate={() => {}}
        role="student"
        onLogout={() => {
          setRole(null);
          router.push("/");
        }}
      />
      <main className="flex-1 min-w-0 flex flex-col">
        <TopBar title="My Dashboard" subtitle="Track your progress and upcoming work" />
        <div className="flex-1">{children}</div>
      </main>
      <Toaster />
    </div>
  );
}
