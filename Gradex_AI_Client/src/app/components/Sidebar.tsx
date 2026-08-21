import { LayoutDashboard, LogOut, GraduationCap } from "lucide-react";
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
    "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors duration-200",
    isActive
      ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
      : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground",
  );

const headerClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "w-full flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium tracking-wide transition-colors",
    isActive
      ? "text-foreground"
      : "text-muted-foreground hover:text-foreground",
  );

const subItemClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors duration-200",
    isActive
      ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
      : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground",
  );

export function Sidebar({ role, onLogout }: SidebarProps) {
  return (
    <aside className="w-64 shrink-0 bg-sidebar border-r border-sidebar-border flex flex-col h-screen sticky top-0 print:hidden">
      <div className="px-6 py-5 border-b border-sidebar-border flex items-center gap-3">
        <div className="size-9 rounded-lg bg-primary text-primary-foreground flex items-center justify-center">
          <GraduationCap className="size-5" />
        </div>
        <div className="leading-tight">
          <div className="text-sidebar-foreground tracking-tight font-medium">GradeX AI</div>
          <div className="text-xs text-muted-foreground">Learning Suite</div>
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
                    <div className="ml-4 space-y-0.5 border-l border-sidebar-border pl-2">
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

      <div className="p-3 border-t border-sidebar-border">
        <div className="flex items-center gap-3 p-2.5 rounded-lg bg-sidebar-accent/60">
          <div className="size-9 rounded-lg bg-secondary text-secondary-foreground flex items-center justify-center text-sm font-medium">
            {role === "lecturer" ? "DR" : "SP"}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm text-sidebar-foreground truncate">
              {role === "lecturer" ? "Dr. R. Mendis" : "Sahan Perera"}
            </div>
            <div className="text-xs text-muted-foreground truncate capitalize">{role}</div>
          </div>
          <Button variant="ghost" size="icon" onClick={onLogout} className="size-8">
            <LogOut className="size-4" />
          </Button>
        </div>
      </div>
    </aside>
  );
}
