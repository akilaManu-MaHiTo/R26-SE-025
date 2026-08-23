import { Fragment, useState, createContext, useContext } from "react";
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from "react-router";
import { Sidebar } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { LoginPage } from "./components/LoginPage";
import { LecturerDashboard } from "./components/LecturerDashboard";
import { StudentDashboard } from "./components/StudentDashboard";
import { AgentOverview } from "./components/AgentOverview";
import { AGENT_CONFIG, titleFor } from "./routeConfig";
import { Toaster } from "./components/ui/sonner";

type Role = "lecturer" | "student";

export const HideSidebarContext = createContext<{ setHide: (v: boolean) => void } | null>(null);
export function useHideSidebar() {
  return useContext(HideSidebarContext);
}

function Layout({ role, onLogout }: { role: Role; onLogout: () => void }) {
  const location = useLocation();
  const meta = titleFor(location.pathname);
  const [hideForEditor, setHideForEditor] = useState(false);
  const hideSidebar = hideForEditor && location.pathname === "/question-exam/exam-creator";
  return (
    <HideSidebarContext.Provider value={{ setHide: setHideForEditor }}>
      <div className="flex bg-background min-h-screen text-foreground">
        {!hideSidebar && <Sidebar role={role} onLogout={onLogout} />}
        <main className="flex-1 min-w-0 flex flex-col">
          <TopBar title={meta.title} subtitle={meta.subtitle} />
          <div className="flex-1">
            <Outlet />
          </div>
        </main>
      </div>
    </HideSidebarContext.Provider>
  );
}

export default function App() {
  const [role, setRole] = useState<Role | null>(null);

  if (!role) {
    return (
      <>
        <LoginPage onLogin={(r) => setRole(r)} />
        <Toaster />
      </>
    );
  }

  const defaultPath = role === "lecturer" ? "/dashboard" : "/student-dashboard";

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout role={role} onLogout={() => setRole(null)} />}>
          <Route index element={<Navigate to={defaultPath} replace />} />
          <Route
            path="/dashboard"
            element={
              role === "lecturer" ? <LecturerDashboard /> : <Navigate to={defaultPath} replace />
            }
          />
          <Route
            path="/student-dashboard"
            element={
              role === "student" ? <StudentDashboard /> : <Navigate to={defaultPath} replace />
            }
          />
          {role === "lecturer" &&
            AGENT_CONFIG.map((agent) => (
              <Fragment key={agent.id}>
                <Route path={agent.basePath} element={<AgentOverview agent={agent} />} />
                {agent.features.map((feature) => (
                  <Route key={feature.path} path={feature.path} element={feature.element} />
                ))}
              </Fragment>
            ))}
          <Route path="*" element={<Navigate to={defaultPath} replace />} />
        </Route>
      </Routes>
      <Toaster />
    </BrowserRouter>
  );
}
