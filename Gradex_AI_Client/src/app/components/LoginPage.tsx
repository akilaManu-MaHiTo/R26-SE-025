import { useState } from "react";
import { Link } from "react-router";
import { ArrowRight, Eye, EyeOff, GraduationCap, Loader2, LockKeyhole, Mail, Presentation } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { login, type AuthUser } from "../api/authApi";
import gradexLogo from "../../imports/gradex-logo.png";
import "./LoginPage.css";

export function LoginPage({ role, onLogin }: {
  role: AuthUser["role"];
  onLogin: (user: AuthUser) => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const isLecturer = role === "lecturer";
  const roleName = isLecturer ? "Lecturer" : "Student";

  return (
    <div className="gradex-login" data-role={role}>
      <a href="#login-form" className="login-skip">Skip to sign in</a>
      <header className="login-header">
        <div className="login-brand"><img src={gradexLogo} alt="GradeX AI" width="44" height="44" /><span>GradeX<span className="login-brand-ai"> AI</span></span></div>
        <span className="login-header-label">A LITTLE CLARITY. A LOT OF POSSIBILITY.</span>
      </header>
      <div className="login-stage">
      <main className="login-main" id="login-form" tabIndex={-1}>
        <div className="login-form-wrap">
          <p className="login-form-eyebrow">WELCOME BACK</p>
          <h1>{roleName} sign in</h1>
          <p className="login-description">{isLecturer ? "Sign in to your teaching workspace." : "Sign in to continue your learning journey."}</p>

          <nav aria-label="Sign-in portal" className="login-portals">
            {(["lecturer", "student"] as const).map((portal) => (
              <Link key={portal} to={`/login/${portal}`} aria-current={portal === role ? "page" : undefined}>
                {portal === "lecturer" ? <Presentation size={16} aria-hidden="true" /> : <GraduationCap size={18} aria-hidden="true" />}
                {portal === "lecturer" ? "Lecturer" : "Student"}
              </Link>
            ))}
          </nav>

          <form aria-busy={loading} onSubmit={async (event) => {
            event.preventDefault();
            if (loading) return;
            setError(null);
            setLoading(true);
            try { onLogin(await login(email.trim(), password, role)); }
            catch (err) { setError(err instanceof Error ? err.message : "Login failed"); }
            finally { setLoading(false); }
          }}>
            <div className="login-field">
              <Label htmlFor="email">University email</Label>
              <div className="login-input-wrap">
                <Mail size={17} aria-hidden="true" />
                <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder={isLecturer ? "lecturer@university.edu" : "student@university.edu"} autoComplete="username" required disabled={loading} autoCapitalize="none" spellCheck={false} className="login-input login-email" />
              </div>
            </div>
            <div className="login-field">
              <Label htmlFor="password">Password</Label>
              <div className="login-input-wrap">
                <Input id="password" type={showPassword ? "text" : "password"} autoComplete="current-password" required disabled={loading} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Enter your password" className="login-input login-password" />
                <button type="button" onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? "Hide password" : "Show password"} aria-pressed={showPassword} className="login-password-toggle">
                  {showPassword ? <EyeOff size={17} aria-hidden="true" /> : <Eye size={17} aria-hidden="true" />}
                </button>
              </div>
            </div>
            {error && <p role="alert" className="login-error">{error}</p>}
            <Button type="submit" className="login-submit" disabled={loading}>
              {loading ? <><Loader2 className="login-spinner" size={17} aria-hidden="true" /> Signing in…</> : <>Sign in as {role} <ArrowRight size={17} aria-hidden="true" /></>}
            </Button>
          </form>
          <p className="login-account-note">Use the university account provided to you.</p>
          <div className="login-help"><span>Need help signing in?</span><p>{isLecturer ? "Contact your administrator for account access or a password reset." : "Contact your lecturer or administrator for account access or a password reset."}</p></div>
        </div>
      </main>
      <aside className="login-brand-panel">
        <p className="login-eyebrow"><span /> MADE FOR YOUR NEXT CHAPTER</p>
        <h2>A brighter way<br />to <em>{isLecturer ? "teach." : "learn."}</em></h2>
        <p className="login-story-copy">{isLecturer ? "Less time on the paperwork. More time for the lightbulb moments." : "Find your strengths, follow your curiosity, and see how far you can go."}</p>
        <div className="login-characters" aria-hidden="true">
          <div className="login-character-note">{isLecturer ? "Let’s make a difference." : "You’ve got this."}<span>✧</span></div>
          <svg viewBox="0 0 540 350" fill="none" className="login-character-art">
            <ellipse cx="270" cy="322" rx="218" ry="17" fill="#dddddd" />
            <path d="M62 251C31 173 98 70 199 74C315 78 325 17 417 68C495 111 501 236 461 286" stroke="#dadada" strokeWidth="1.5" strokeDasharray="5 8" />
            <circle cx="270" cy="175" r="132" fill="#e6e6e6" />
            <g className="login-art-spark" stroke="#8c8c8c" strokeWidth="2.5" strokeLinecap="round"><path d="M82 130v18m-9-9h18M456 205v14m-7-7h14M275 46v16m-8-8h16" /></g>
            <g className="login-person login-person-student">
              <path d="M122 261l-7 53h30l16-55m10 0 12 55h31l-7-63" fill="#3b3b3b" />
              <path d="M113 309h33v14h-49c0-8 6-12 16-14m71 0h30l13 14h-43" fill="#282828" />
              <rect x="99" y="165" width="48" height="84" rx="23" fill="#7f7f7f" />
              <path d="M139 160c-28 4-37 32-31 63l7 50h94l7-52c6-34-8-56-32-61" fill="#979797" />
              <path d="M133 165l12 39m44-40-12 40" stroke="#737373" strokeWidth="6" strokeLinecap="round" />
              <path d="M150 144v25c0 14 27 14 27 0v-25" fill="#a4a4a4" />
              <g className="login-person-head">
                <rect x="128" y="91" width="71" height="71" rx="32" fill="#b8b8b8" />
                <path d="M128 124c-12-22-3-49 24-50 25-16 54 7 50 32-9 0-23-3-34-13-7 14-20 17-32 15v18" fill="#393939" />
                <circle cx="132" cy="128" r="8" fill="#b8b8b8" />
                <g className="login-person-eyes" fill="#353535"><ellipse cx="156" cy="123" rx="2.5" ry="3.5" /><ellipse cx="181" cy="123" rx="2.5" ry="3.5" /></g>
                <path d="M160 141q9 8 17-1" stroke="#5c5c5c" strokeWidth="2.5" strokeLinecap="round" />
                <path d="M168 125v9h5" stroke="#8a8a8a" strokeWidth="2" strokeLinecap="round" />
              </g>
              <g className="login-student-wave"><path d="M199 182q32 5 38-39" stroke="#979797" strokeWidth="22" strokeLinecap="round" /><path d="M237 144l3-19m-1 9 10-14m-11 15-8-12" stroke="#b8b8b8" strokeWidth="10" strokeLinecap="round" /></g>
              <g transform="rotate(-12 154 227)"><rect x="127" y="200" width="55" height="66" rx="5" fill="#ededed" /><path d="M137 200v66" stroke="#bebebe" strokeWidth="3" /><path d="M148 217h23m-23 8h18" stroke="#8e8e8e" strokeWidth="2" /></g>
              <path d="M118 202q-9 37 26 35" stroke="#979797" strokeWidth="20" strokeLinecap="round" /><path d="M142 237h11" stroke="#b8b8b8" strokeWidth="13" strokeLinecap="round" />
            </g>
            <g className="login-person login-person-lecturer">
              <path d="M324 256l-4 58h28l17-58m4 0 10 58h29l-4-65" fill="#414141" />
              <path d="M319 308h29v15h-46c0-8 7-13 16-15m60 0h29l17 15h-45" fill="#2f2f2f" />
              <path d="M341 153c-29 3-38 26-36 55l8 62h98l7-62c2-28-13-51-39-55" fill="#7b7b7b" />
              <path d="M342 156l19 48 20-48" fill="#f4f4f4" /><path d="M341 155l-13 25 15 4-5 12 23 29 27-29-8-12 14-4-13-25" stroke="#5d5d5d" strokeWidth="2" />
              <path d="M349 135v26q12 16 24 0v-26" fill="#888888" />
              <g className="login-person-head">
                <path d="M326 101q-5-42 37-42c31 0 42 21 34 50l-8 36h-57" fill="#3e3e3e" />
                <rect x="332" y="78" width="60" height="70" rx="27" fill="#a0a0a0" />
                <path d="M327 103c-3-27 16-41 34-37 19-9 39 12 34 28-12 0-27-6-33-16-6 13-18 20-35 25" fill="#3e3e3e" />
                <g stroke="#3f3f3f" strokeWidth="2.5"><rect x="336" y="103" width="21" height="16" rx="6" /><rect x="366" y="103" width="21" height="16" rx="6" /><path d="M357 108h9" /></g>
                <g className="login-person-eyes" fill="#363636"><circle cx="347" cy="110" r="2" /><circle cx="376" cy="110" r="2" /></g>
                <path d="M354 132q9 7 17-1" stroke="#565656" strokeWidth="2.5" strokeLinecap="round" />
              </g>
              <g className="login-lecturer-wave"><path d="M317 179q-28 14-38-26" stroke="#7b7b7b" strokeWidth="21" strokeLinecap="round" /><path d="M279 154l-6-18m5 9-14-10m13 7 4-15" stroke="#a0a0a0" strokeWidth="9" strokeLinecap="round" /></g>
              <g transform="rotate(10 382 230)"><rect x="352" y="202" width="59" height="58" rx="5" fill="#3f3f3f" /><rect x="357" y="207" width="49" height="43" rx="2" fill="#c2c2c2" /><path d="m368 234 7-9 8 4 13-13" stroke="#656565" strokeWidth="2.5" /><circle cx="382" cy="255" r="2" fill="#b6b6b6" /></g>
              <path d="M407 195q16 36-16 40" stroke="#7b7b7b" strokeWidth="20" strokeLinecap="round" /><path d="m392 235-10 1" stroke="#a0a0a0" strokeWidth="12" strokeLinecap="round" />
            </g>
            <g stroke="#8e8e8e" strokeWidth="2" strokeLinecap="round"><path d="M462 312v-49m0 31q-24-1-19-23 20 4 19 23m1-10q25-3 20-24-20 5-20 24" fill="#b4b4b4" /><path d="M447 305h30l-4 18h-22" fill="#b5b5b5" stroke="#b5b5b5" /></g>
          </svg>
          <div className="login-character-labels"><span className={!isLecturer ? "is-active" : ""}>The curious mind</span><span className={isLecturer ? "is-active" : ""}>The guiding light</span></div>
        </div>
        <div className="login-scene-caption"><span className="login-caption-line" /><p>{isLecturer ? "A little insight. A lasting impact." : "Big ambitions. Small steps. Your pace."}</p></div>
      </aside>
      </div>
      <footer className="login-footer"><span>© {new Date().getFullYear()} GradeX AI</span><span>Built for teaching. Designed for learning.</span><span><LockKeyhole size={12} aria-hidden="true" /> Secure university access</span></footer>

    </div>
  );
}
