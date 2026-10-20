import { Fragment, useEffect, useState, createContext, useContext } from "react";
import { motion } from "framer-motion";
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from "react-router";
import { PageErrorBoundary } from "./components/PageErrorBoundary";
import sessionRetryAnimation from "./components/animations/validation/bloub-capsule-effraye-rouge-anime-danger.svg";
import sessionCheckingAnimation from "./components/animations/bloub-capsule-attentif-vert-anime.svg";
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
  return <BrowserRouter><SessionApp /></BrowserRouter>;
}

function SessionApp() {
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

  if (checking) return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 p-6 text-center">
      <motion.img
        src={sessionCheckingAnimation}
        alt=""
        width={140}
        height={140}
        className="size-32 object-contain"
        aria-hidden="true"
        initial={{ scale: 0.8, opacity: 0, y: 12 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      />
      <motion.div
        className="max-w-md space-y-2"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}
      >
        <h1 role="status" className="text-2xl font-semibold tracking-tight">Checking your session…</h1>
        <p className="text-sm text-muted-foreground">Hang tight while we confirm who you are.</p>
      </motion.div>
    </div>
  );
  if (sessionError) return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 p-6 text-center">
      <motion.img
        src={sessionRetryAnimation}
        alt=""
        width={140}
        height={140}
        className="size-32 object-contain"
        aria-hidden="true"
        initial={{ scale: 0.8, opacity: 0, y: 12 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      />
      <motion.div
        className="max-w-md space-y-2"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}
      >
        <h1 className="text-2xl font-semibold tracking-tight">We couldn't verify your session</h1>
        <p role="alert" className="text-muted-foreground">{sessionError}</p>
        <p className="text-sm text-muted-foreground">This can happen if your connection dropped or your session expired. Please try again.</p>
      </motion.div>
      <motion.button
        onClick={() => window.location.reload()}
        className="inline-flex items-center justify-center rounded-md bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.3, ease: [0.22, 1, 0.36, 1] }}
      >
        Retry
      </motion.button>
    </div>
  );

  if (!role) {
    return (
      <>
        <Routes>
          <Route path="/login/lecturer" element={<LoginPage key="lecturer" role="lecturer" onLogin={setUser} />} />
          <Route path="/login/student" element={<LoginPage key="student" role="student" onLogin={setUser} />} />
          <Route path="*" element={<Navigate to="/login/lecturer" replace />} />
        </Routes>
        <Toaster />
      </>
    );
  }

  const defaultPath = role === "lecturer" ? "/dashboard" : "/student-dashboard";

  return (
    <>
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
    </>
  );
}
