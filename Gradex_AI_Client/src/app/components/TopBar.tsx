import { Search, Bell, HelpCircle } from "lucide-react";
import { Input } from "./ui/input";
import { Button } from "./ui/button";

export function TopBar({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header className="bg-white border-b border-slate-200 px-8 py-4 flex items-center gap-6 sticky top-0 z-10">
      <div className="flex-1">
        <div className="text-slate-900 tracking-tight">{title}</div>
        {subtitle && <div className="text-sm text-slate-500 mt-0.5">{subtitle}</div>}
      </div>
      <div className="relative w-72">
        <Search className="size-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
        <Input
          placeholder="Search students, exams, questions…"
          className="pl-9 bg-slate-50 border-slate-200"
        />
      </div>
      <Button variant="ghost" size="icon" className="relative">
        <Bell className="size-5 text-slate-600" />
        <span className="absolute top-2 right-2 size-2 rounded-full bg-red-500" />
      </Button>
      <Button variant="ghost" size="icon">
        <HelpCircle className="size-5 text-slate-600" />
      </Button>
    </header>
  );
}
