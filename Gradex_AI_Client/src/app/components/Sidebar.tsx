import { LayoutDashboard, LogOut, Sparkles } from "lucide-react";
import { NavLink } from "react-router";
import { Button } from "./ui/button";
import { cn } from "./ui/utils";
import { AGENT_CONFIG } from "../routeConfig";

interface SidebarProps {
  role: "lecturer" | "student";
  onLogout: () => void;
}

const itemClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors",
    isActive ? "bg-blue-50 text-blue-700" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
  );

const headerClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "w-full flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium uppercase tracking-wider transition-colors",
    isActive ? "text-blue-700" : "text-slate-400 hover:text-slate-600"
  );

const subItemClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
    isActive ? "bg-blue-50 text-blue-700" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
  );

export function Sidebar({ role, onLogout }: SidebarProps) {
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

      <nav className="flex-1 px-3 py-4 space-y-4 overflow-y-auto">
        {role === "lecturer" ? (
          <>
            <NavLink to="/dashboard" end className={itemClass}>
              <LayoutDashboard className="size-4" />
              <span>Dashboard</span>
            </NavLink>

            <div className="space-y-1">
              {AGENT_CONFIG.map((agent) => {
                const Icon = agent.icon;
                return (
                  <div key={agent.id} className="space-y-0.5">
                    <NavLink to={agent.basePath} className={headerClass}>
                      <Icon className="size-4" />
                      <span className="truncate">{agent.name}</span>
                    </NavLink>
                    <div className="ml-4 space-y-0.5 border-l border-slate-100 pl-2">
                      {agent.features.map((feature) => (
                        <NavLink key={feature.path} to={feature.path} end className={subItemClass}>
                          <span className="truncate">{feature.label}</span>
                        </NavLink>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        ) : (
          <NavLink to="/student-dashboard" end className={itemClass}>
            <LayoutDashboard className="size-4" />
            <span>My Dashboard</span>
          </NavLink>
        )}
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
