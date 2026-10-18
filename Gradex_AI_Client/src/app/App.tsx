import { Fragment, useEffect, useState, createContext, useContext } from "react";
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from "react-router";
import { PageErrorBoundary } from "./components/PageErrorBoundary";
import { Sidebar } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { LoginPage } from "./components/LoginPage";
import { LecturerDashboard } from "./components/LecturerDashboard";
import { ExamKeysPage } from "./components/ExamKeysPage";
import { StudentDashboard } from "./components/StudentDashboard";
import { AgentOverview } from "./components/AgentOverview";
import { AGENT_CONFIG, titleFor } from "./routeConfig";
import { Toaster } from "./components/ui/sonner";
import { currentUser, logout, type AuthUser } from "./api/authApi";
import { toast } from "sonner";

type Role = "lecturer" | "student";

export const HideSidebarContext = createContext<{ setHide: (v: boolean) => void } | null>(null);
export function useHideSidebar() {
  return useContext(HideSidebarContext);
}

function Layout({ role, email, onLogout }: { role: Role; email: string; onLogout: () => void }) {
  const location = useLocation();
  const meta = titleFor(location.pathname);
  const [hideForEditor, setHideForEditor] = useState(false);
  const hideSidebar = hideForEditor && location.pathname === "/question-exam/exam-creator";
  return (
    <HideSidebarContext.Provider value={{ setHide: setHideForEditor }}>
      <div className="flex bg-background min-h-screen text-foreground">
        {!hideSidebar && <Sidebar role={role} email={email} onLogout={onLogout} />}
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
  const [user, setUser] = useState<AuthUser | null>(null);
  const [checking, setChecking] = useState(true);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const role = user?.role;
  const studentId = user?.student_id;

  useEffect(() => {
    let active = true;
    const unauthorized = () => setUser(null);
    window.addEventListener("gradex:unauthorized", unauthorized);
    currentUser().then((value) => { if (active) setUser(value); })
      .catch((error) => { if (active) setSessionError(error.message); })
      .finally(() => { if (active) setChecking(false); });
    return () => { active = false; window.removeEventListener("gradex:unauthorized", unauthorized); };
  }, []);

  const handleLogout = async () => {
    try { await logout(); setUser(null); }
    catch (error) { toast.error(error instanceof Error ? error.message : "Could not sign out"); }
  };

  if (checking) return <p role="status" className="p-6">Checking your session…</p>;
  if (sessionError) return <div className="p-6"><p role="alert">{sessionError}</p><button onClick={() => window.location.reload()}>Retry</button></div>;

  if (!role) {
    return (
      <>
        <LoginPage onLogin={setUser} />
        <Toaster />
      </>
    );
  }

  const defaultPath = role === "lecturer" ? "/dashboard" : "/student-dashboard";

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout role={role} email={user!.email} onLogout={handleLogout} />}>
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
              role === "student" && studentId ? <StudentDashboard studentId={studentId} /> : <Navigate to={defaultPath} replace />
            }
          />
          <Route path="/exam-keys" element={role === "lecturer" ? <ExamKeysPage /> : <Navigate to={defaultPath} replace />} />
          {role === "lecturer" &&
            AGENT_CONFIG.map((agent) => (
              <Fragment key={agent.id}>
                <Route path={agent.basePath} element={<AgentOverview agent={agent} />} />
                {agent.features.map((feature) => (
                  <Route
                    key={feature.path}
                    path={feature.path}
                    element={<PageErrorBoundary key={feature.path}>{feature.element}</PageErrorBoundary>}
                  />
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
