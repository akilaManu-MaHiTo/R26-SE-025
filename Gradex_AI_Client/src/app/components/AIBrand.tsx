import React from "react";

/* ════════════════════════════════════════════════════════════════════════════
   AI Brand System — GradeX AI
   Four distinct AI identities, each with unique logo, palette & personality
═══════════════════════════════════════════════════════════════════════════════ */

export type AIModel = "structr" | "lexo" | "pulse" | "voca";

/* ─── Identity definitions ──────────────────────────────────────────────── */
export const AI_IDENTITIES = {
  structr: {
    id: "structr" as AIModel,
    name: "STRUCTR",
    dot: "·AI",
    fullName: "STRUCTR·AI",
    tagline: "Visual Structure Intelligence",
    sub: "Diagram Extraction & Grading Engine",
    version: "v2.4",
    c1: "#1d4ed8",   // deep blue
    c2: "#0891b2",   // cyan
    loadingMessages: [
      "Parsing diagram topology…",
      "Detecting entities & relationships…",
      "Mapping cardinality constraints…",
      "Scoring against rubric…",
      "Generating confidence scores…",
    ],
  },
  lexo: {
    id: "lexo" as AIModel,
    name: "LEXO",
    dot: "·AI",
    fullName: "LEXO·AI",
    tagline: "Handwriting Recognition Engine",
    sub: "OCR Extraction & Semantic Grading",
    version: "v3.1",
    c1: "#6d28d9",   // deep violet
    c2: "#9333ea",   // purple
    loadingMessages: [
      "Preprocessing image…",
      "Running OCR pipeline…",
      "Tokenising extracted text…",
      "Matching against rubric keywords…",
      "Computing semantic similarity…",
    ],
  },
  pulse: {
    id: "pulse" as AIModel,
    name: "PULSE",
    dot: "·AI",
    fullName: "PULSE·AI",
    tagline: "Cognitive Performance Intelligence",
    sub: "Class Analytics & Insight Engine",
    version: "v1.8",
    c1: "#0f766e",   // teal
    c2: "#059669",   // emerald
    loadingMessages: [
      "Ingesting exam submissions…",
      "Computing Bloom's taxonomy mapping…",
      "Detecting cognitive gaps…",
      "Building heatmap matrix…",
      "Generating insight report…",
    ],
  },
  voca: {
    id: "voca" as AIModel,
    name: "VOCA",
    dot: "·AI",
    fullName: "VOCA·AI",
    tagline: "Verbal Assessment Intelligence",
    sub: "Viva Voce Transcription & Scoring",
    version: "v2.0",
    c1: "#be123c",   // rose
    c2: "#ea580c",   // orange
    loadingMessages: [
      "Initialising audio pipeline…",
      "Running speech-to-text model…",
      "Detecting key moments…",
      "Aligning transcript with rubric…",
      "Scoring verbal competencies…",
    ],
  },
} as const;

/* ─── SVG Logos ──────────────────────────────────────────────────────────── */

/** STRUCTR·AI — interconnected node graph */
export function StructrLogo({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none">
      <defs>
        <radialGradient id="structr-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#60a5fa" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#1d4ed8" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="structr-node" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#60a5fa" />
          <stop offset="100%" stopColor="#2563eb" />
        </linearGradient>
        <linearGradient id="structr-outer" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#06b6d4" />
          <stop offset="100%" stopColor="#0891b2" />
        </linearGradient>
      </defs>
      {/* Glow */}
      <circle cx="20" cy="20" r="18" fill="url(#structr-glow)" />
      {/* Connection lines */}
      <line x1="20" y1="20" x2="9" y2="9"  stroke="#93c5fd" strokeWidth="1.2" strokeLinecap="round" />
      <line x1="20" y1="20" x2="31" y2="9"  stroke="#93c5fd" strokeWidth="1.2" strokeLinecap="round" />
      <line x1="20" y1="20" x2="9"  y2="31" stroke="#93c5fd" strokeWidth="1.2" strokeLinecap="round" />
      <line x1="20" y1="20" x2="31" y2="31" stroke="#93c5fd" strokeWidth="1.2" strokeLinecap="round" />
      <line x1="20" y1="20" x2="20" y2="5"  stroke="#93c5fd" strokeWidth="1.2" strokeLinecap="round" />
      <line x1="20" y1="20" x2="20" y2="35" stroke="#93c5fd" strokeWidth="1.2" strokeLinecap="round" />
      {/* Cross-connections */}
      <line x1="9"  y1="9"  x2="31" y2="9"  stroke="#bfdbfe" strokeWidth="0.8" strokeOpacity="0.5" />
      <line x1="9"  y1="31" x2="31" y2="31" stroke="#bfdbfe" strokeWidth="0.8" strokeOpacity="0.5" />
      <line x1="20" y1="5"  x2="31" y2="9"  stroke="#bfdbfe" strokeWidth="0.8" strokeOpacity="0.5" />
      <line x1="20" y1="5"  x2="9"  y2="9"  stroke="#bfdbfe" strokeWidth="0.8" strokeOpacity="0.5" />
      {/* Outer nodes */}
      <circle cx="9"  cy="9"  r="3.5" fill="url(#structr-outer)" />
      <circle cx="31" cy="9"  r="3.5" fill="url(#structr-outer)" />
      <circle cx="9"  cy="31" r="3.5" fill="url(#structr-outer)" />
      <circle cx="31" cy="31" r="3.5" fill="url(#structr-outer)" />
      <circle cx="20" cy="5"  r="2.5" fill="#67e8f9" />
      <circle cx="20" cy="35" r="2.5" fill="#67e8f9" />
      {/* Center node */}
      <circle cx="20" cy="20" r="6" fill="url(#structr-node)" />
      <circle cx="20" cy="20" r="3" fill="white" fillOpacity="0.9" />
    </svg>
  );
}

/** LEXO·AI — fountain pen + handwriting wave */
export function LexoLogo({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none">
      <defs>
        <linearGradient id="lexo-pen" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#a78bfa" />
          <stop offset="100%" stopColor="#7c3aed" />
        </linearGradient>
        <linearGradient id="lexo-nib" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#c4b5fd" />
          <stop offset="100%" stopColor="#8b5cf6" />
        </linearGradient>
        <radialGradient id="lexo-glow" cx="50%" cy="40%" r="50%">
          <stop offset="0%" stopColor="#a78bfa" stopOpacity="0.25" />
          <stop offset="100%" stopColor="#7c3aed" stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="20" cy="20" r="18" fill="url(#lexo-glow)" />
      {/* Pen barrel */}
      <rect x="24" y="4" width="7" height="14" rx="3.5" transform="rotate(35 27.5 11)" fill="url(#lexo-pen)" />
      {/* Pen nib */}
      <path d="M17 19 L13 27 L20 24 Z" fill="url(#lexo-nib)" />
      <path d="M17 19 L25 13 L20 24 Z" fill="#6d28d9" />
      {/* Nib split */}
      <line x1="17" y1="19" x2="20" y2="24" stroke="#c4b5fd" strokeWidth="0.8" />
      {/* Ink dot */}
      <circle cx="13.5" cy="27" r="1.8" fill="#7c3aed" />
      {/* Handwriting script lines */}
      <path d="M5 31 C8 28 11 34 15 31 C19 28 22 33 27 30 C30 28 32 31 35 29"
        stroke="#c084fc" strokeWidth="1.8" strokeLinecap="round" fill="none" />
      <path d="M5 35 C9 33 13 36 18 34 C22 32 26 35 33 33"
        stroke="#a855f7" strokeWidth="1.2" strokeLinecap="round" fill="none" strokeOpacity="0.6" />
    </svg>
  );
}

/** PULSE·AI — bar chart with EKG heartbeat */
export function PulseLogo({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none">
      <defs>
        <linearGradient id="pulse-bar1" x1="0" y1="1" x2="0" y2="0">
          <stop offset="0%" stopColor="#059669" />
          <stop offset="100%" stopColor="#34d399" />
        </linearGradient>
        <linearGradient id="pulse-bar2" x1="0" y1="1" x2="0" y2="0">
          <stop offset="0%" stopColor="#0d9488" />
          <stop offset="100%" stopColor="#2dd4bf" />
        </linearGradient>
        <linearGradient id="pulse-bar3" x1="0" y1="1" x2="0" y2="0">
          <stop offset="0%" stopColor="#0f766e" />
          <stop offset="100%" stopColor="#5eead4" />
        </linearGradient>
        <radialGradient id="pulse-glow" cx="50%" cy="60%" r="50%">
          <stop offset="0%" stopColor="#10b981" stopOpacity="0.25" />
          <stop offset="100%" stopColor="#0d9488" stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="20" cy="20" r="18" fill="url(#pulse-glow)" />
      {/* Bar chart */}
      <rect x="5"  y="22" width="7" height="12" rx="2" fill="url(#pulse-bar1)" />
      <rect x="15" y="16" width="7" height="18" rx="2" fill="url(#pulse-bar2)" />
      <rect x="25" y="19" width="7" height="15" rx="2" fill="url(#pulse-bar3)" />
      {/* Baseline */}
      <line x1="4" y1="34" x2="36" y2="34" stroke="#6ee7b7" strokeWidth="1" strokeOpacity="0.4" />
      {/* EKG heartbeat line over the bars */}
      <path d="M2 14 L7 14 L10 8 L13 20 L16 14 L20 14 L22 7 L25 21 L27 14 L38 14"
        stroke="#34d399" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      {/* EKG peak dot */}
      <circle cx="22" cy="7" r="2" fill="#6ee7b7" />
    </svg>
  );
}

/** VOCA·AI — microphone with sound waves */
export function VocaLogo({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none">
      <defs>
        <linearGradient id="voca-mic" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#fb7185" />
          <stop offset="100%" stopColor="#be123c" />
        </linearGradient>
        <linearGradient id="voca-stand" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#f97316" />
          <stop offset="100%" stopColor="#c2410c" />
        </linearGradient>
        <radialGradient id="voca-glow" cx="40%" cy="45%" r="50%">
          <stop offset="0%" stopColor="#fb7185" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#be123c" stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="20" cy="20" r="18" fill="url(#voca-glow)" />
      {/* Mic capsule */}
      <rect x="13" y="5" width="10" height="17" rx="5" fill="url(#voca-mic)" />
      {/* Mic grille lines */}
      <line x1="13" y1="11" x2="23" y2="11" stroke="white" strokeWidth="0.8" strokeOpacity="0.4" />
      <line x1="13" y1="14" x2="23" y2="14" stroke="white" strokeWidth="0.8" strokeOpacity="0.4" />
      <line x1="13" y1="17" x2="23" y2="17" stroke="white" strokeWidth="0.8" strokeOpacity="0.4" />
      {/* Stand arc */}
      <path d="M10 19 C10 27 30 27 30 19" stroke="url(#voca-stand)" strokeWidth="2" fill="none" strokeLinecap="round" />
      {/* Stand pole */}
      <line x1="20" y1="26" x2="20" y2="33" stroke="#f97316" strokeWidth="2" strokeLinecap="round" />
      <line x1="14" y1="33" x2="26" y2="33" stroke="#f97316" strokeWidth="2" strokeLinecap="round" />
      {/* Sound waves */}
      <path d="M28 10 C31 13 31 17 28 20" stroke="#fda4af" strokeWidth="1.5" strokeLinecap="round" fill="none" />
      <path d="M31 7  C36 11 36 19 31 23" stroke="#fca5a5" strokeWidth="1.5" strokeLinecap="round" fill="none" strokeOpacity="0.6" />
    </svg>
  );
}

/* Map model → logo component */
export function AILogo({ model, size = 40 }: { model: AIModel; size?: number }) {
  if (model === "structr") return <StructrLogo size={size} />;
  if (model === "lexo")    return <LexoLogo    size={size} />;
  if (model === "pulse")   return <PulseLogo   size={size} />;
  return <VocaLogo size={size} />;
}

/* ─── Inline pill badge — shown in page headers ──────────────────────────── */
export function AIBadgePill({ model }: { model: AIModel }) {
  const id = AI_IDENTITIES[model];
  return (
    <div className="inline-flex items-center gap-2 px-2.5 py-1.5 rounded-lg border border-border bg-card/80">
      <AILogo model={model} size={20} />
      <span className="text-xs font-medium tracking-widest" style={{ letterSpacing: "0.12em" }}>
        {id.name}
      </span>
      <span className="text-[10px] text-muted-foreground border border-border rounded px-1">{id.version}</span>
    </div>
  );
}

/* ─── Page header card — shown at the top of each AI feature page ────────── */
export function AIPageBanner({ model }: { model: AIModel }) {
  const id = AI_IDENTITIES[model];
  return (
    <div className="relative overflow-hidden rounded-2xl border border-border bg-card p-5 flex items-center gap-5">
      {/* Subtle ambient tint using the model's secondary colour */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div
          className="absolute -right-24 -top-32 size-72 rounded-full blur-3xl"
          style={{ backgroundColor: id.c2, opacity: 0.07 }}
        />
      </div>

      {/* Logo mark */}
      <div className="relative shrink-0">
        <div className="size-16 rounded-2xl bg-muted flex items-center justify-center">
          <AILogo model={model} size={36} />
        </div>
        {/* Active pulse ring */}
        <span className="absolute -top-1 -right-1 size-4 rounded-full border-2 border-background flex items-center justify-center">
          <span className="size-2 rounded-full bg-emerald-500 animate-pulse" />
        </span>
      </div>

      {/* Identity text */}
      <div className="relative flex-1 min-w-0">
        <div className="flex items-baseline gap-2">
          <span className="text-xl tracking-tight font-semibold" style={{ fontWeight: 700 }}>
            {id.name}
          </span>
          <span style={{ color: id.c2, fontSize: "1.1rem", fontWeight: 700, letterSpacing: "0.08em" }}>
            {id.dot}
          </span>
          <span className="text-xs text-muted-foreground ml-1 border border-border rounded px-1.5 py-0.5">
            {id.version}
          </span>
        </div>
        <div className="text-sm text-muted-foreground mt-0.5">{id.tagline}</div>
        <div className="text-xs text-muted-foreground/70 mt-0.5">{id.sub}</div>
      </div>

      {/* Status */}
      <div className="relative shrink-0 text-right hidden sm:block">
        <div className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 text-xs font-medium">
          <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
          Model online
        </div>
        <div className="text-muted-foreground/70 text-[10px] mt-1">Ready to process</div>
      </div>
    </div>
  );
}

/* ─── Loading overlay — full-panel AI processing screen ─────────────────── */
export function AILoadingOverlay({
  model,
  progress,
  step,
  visible,
}: {
  model: AIModel;
  progress: number;
  step: number;
  visible: boolean;
}) {
  const id = AI_IDENTITIES[model];
  if (!visible) return null;
  const message = id.loadingMessages[Math.min(step, id.loadingMessages.length - 1)];

  return (
    <div className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-5 rounded-xl overflow-hidden">
      {/* Blurred backdrop */}
      <div className="absolute inset-0 bg-background/90 backdrop-blur-sm" />

      {/* Content */}
      <div className="relative flex flex-col items-center gap-4 px-8 text-center">
        {/* Pulsing logo container */}
        <div className="relative">
          <div className="size-20 rounded-2xl border border-border bg-card flex items-center justify-center shadow-sm">
            <AILogo model={model} size={44} />
          </div>
          {/* Orbit ring animation */}
          <div
            className="absolute inset-0 rounded-2xl border-2 border-dashed opacity-30 animate-spin"
            style={{ borderColor: id.c2, animationDuration: "4s" }}
          />
        </div>

        {/* Name */}
        <div>
          <div className="flex items-baseline gap-1.5 justify-center">
            <span className="text-2xl font-semibold tracking-tight">
              {id.name}
            </span>
            <span style={{ color: id.c2, fontSize: "1.3rem", fontWeight: 700, letterSpacing: "0.12em" }}>
              {id.dot}
            </span>
          </div>
          <div className="text-muted-foreground text-xs mt-1 tracking-wide">{id.tagline}</div>
        </div>

        {/* Step message */}
        <div className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border bg-card">
          <span className="size-2 rounded-full animate-pulse" style={{ backgroundColor: id.c2 }} />
          <span className="text-foreground/80 text-sm">{message}</span>
        </div>

        {/* Progress bar */}
        <div className="w-64 space-y-1.5">
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Processing</span>
            <span>{progress}%</span>
          </div>
          <div className="h-1.5 rounded-full bg-muted overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-300"
              style={{
                width: `${progress}%`,
                background: `linear-gradient(to right, ${id.c1}, ${id.c2})`,
              }}
            />
          </div>
        </div>

        {/* Step indicators */}
        <div className="flex gap-2">
          {id.loadingMessages.map((_, i) => (
            <div
              key={i}
              className="size-1.5 rounded-full transition-all duration-300"
              style={{
                backgroundColor: i <= step ? id.c2 : "var(--border)",
                transform: i === step ? "scale(1.4)" : "scale(1)",
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

/* ─── Mini inline loader — for small "thinking" states ───────────────────── */
export function AIThinkingBadge({ model, label }: { model: AIModel; label?: string }) {
  const id = AI_IDENTITIES[model];
  return (
    <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border bg-card/80">
      <div className="flex gap-0.5">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="size-1.5 rounded-full animate-bounce"
            style={{ backgroundColor: id.c2, animationDelay: `${i * 0.15}s` }}
          />
        ))}
      </div>
      <AILogo model={model} size={16} />
      <span className="text-xs text-foreground/80 font-medium">{id.name}·AI</span>
      {label && <span className="text-xs text-muted-foreground">{label}</span>}
    </div>
  );
}
