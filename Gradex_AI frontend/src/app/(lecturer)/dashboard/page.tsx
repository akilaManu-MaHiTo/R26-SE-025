import { LecturerDashboard } from "@/components/LecturerDashboard";

export default function DashboardPage() {
  const handleNavigate = (page: string) => {
    // Navigation is handled by the layout
  };

  return <LecturerDashboard onNavigate={handleNavigate} />;
}
