import { Search, Bell, HelpCircle, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Input } from "./ui/input";
import { Button } from "./ui/button";

export function TopBar({ title, subtitle }: { title: string; subtitle?: string }) {
  const { resolvedTheme, setTheme } = useTheme();
  const toggleTheme = () => setTheme(resolvedTheme === "dark" ? "light" : "dark");

  return (
    <header className="bg-background border-b border-border px-8 py-4 flex items-center gap-4 sticky top-0 z-10 backdrop-blur bg-background/80">
      <div className="flex-1 min-w-0">
        <h1 className="tracking-tight text-xl">{title}</h1>
        {subtitle && <div className="text-sm text-muted-foreground mt-0.5">{subtitle}</div>}
      </div>
      {/* <div className="relative w-72 max-w-[40vw]">
        <Search className="size-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
        <Input
          placeholder="Search students, exams, questions…"
          className="pl-9 bg-input-background"
        />
      </div> */}
      <Button variant="ghost" size="icon" className="relative">
        <Bell className="size-5 text-muted-foreground" />
        <span className="absolute top-2 right-2 size-2 rounded-full bg-destructive" />
      </Button>
      <Button variant="ghost" size="icon" onClick={toggleTheme} aria-label="Toggle theme">
        {resolvedTheme === "dark" ? (
          <Sun className="size-5 text-muted-foreground" />
        ) : (
          <Moon className="size-5 text-muted-foreground" />
        )}
      </Button>
      <Button variant="ghost" size="icon">
        <HelpCircle className="size-5 text-muted-foreground" />
      </Button>
    </header>
  );
}
