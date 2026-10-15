import { useState } from "react";
import { ArrowRight, Sparkles } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { login, type AuthUser } from "../api/authApi";

export function LoginPage({
  onLogin,
}: {
  onLogin: (user: AuthUser) => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  return (
    <div className="min-h-screen flex bg-background">
      {/* Editorial panel */}
      <div className="hidden lg:flex flex-1 relative overflow-hidden p-14 flex-col justify-between border-r border-border">
        <div className="absolute inset-0 -z-10 bg-gradient-to-br from-accent/70 via-background to-transparent" />
        <div className="absolute -top-40 -right-40 size-[480px] rounded-full bg-primary/5 blur-3xl" />

        <div className="relative flex items-center gap-3">
          <div className="size-10 rounded-lg bg-primary text-primary-foreground flex items-center justify-center">
            <Sparkles className="size-5" />
          </div>
          <div className="tracking-tight text-lg font-medium">GradeX AI</div>
        </div>

        <div className="relative space-y-8 max-w-lg">
          <div className="inline-flex items-center gap-2 text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
            <span className="size-1.5 rounded-full bg-primary" /> AI-powered assessment
          </div>
          <h1 className="text-[2.75rem] leading-[1.1] tracking-tight">
            Smarter grading.
            <br />
            Deeper insight.
            <br />
            Better outcomes.
          </h1>
          <p className="text-muted-foreground leading-relaxed max-w-md">
            GradeX AI helps lecturers grade diagrams, handwritten exams, and viva
            voce sessions in minutes — and gives students a clear view of their
            mastery across every topic.
          </p>
          <div className="grid grid-cols-3 gap-4 pt-2 max-w-lg">
            {[
              { k: "92%", v: "Time saved" },
              { k: "12k+", v: "Exams graded" },
              { k: "4.9", v: "Lecturer rating" },
            ].map((s) => (
              <div key={s.k} className="rounded-xl border border-border bg-card/60 p-5">
                <div className="text-2xl tracking-tight tabular-nums">{s.k}</div>
                <div className="text-xs text-muted-foreground mt-1.5">{s.v}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="relative text-sm text-muted-foreground">© 2026 GradeX AI · University Edition</div>
      </div>

      {/* Form panel */}
      <div className="flex-1 flex items-center justify-center p-6 lg:p-12">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex items-center gap-2.5 mb-8">
            <div className="size-9 rounded-lg bg-primary text-primary-foreground flex items-center justify-center">
              <Sparkles className="size-5" />
            </div>
            <div className="tracking-tight text-lg font-medium text-foreground">GradeX AI</div>
          </div>

          <h2 className="tracking-tight text-2xl text-foreground">Welcome back</h2>
          <p className="text-muted-foreground mt-2">Sign in to continue to your workspace.</p>

          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setError(null);
              setLoading(true);
              try {
                onLogin(await login(email.trim(), password));
              } catch (err) {
                setError(err instanceof Error ? err.message : "Login failed");
              } finally {
                setLoading(false);
              }
            }}
            className="space-y-4 mt-6"
          >
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@university.edu"
                autoComplete="username"
                required
              />

            </div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor="password">Password</Label>

              </div>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••"
              />

            </div>
            {error && <div role="alert" className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</div>}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Signing in..." : "Sign in"} <ArrowRight className="size-4 ml-1" />
            </Button>
            <p className="text-center text-sm text-muted-foreground">Contact your lecturer or administrator for an account or password reset.</p>
          </form>
        </div>
      </div>
    </div>
  );
}
