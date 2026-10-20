import { motion } from "framer-motion";
import { BrandOrb } from "./BrandOrb";
import { type LoadStep } from "./ProgressLoader";

export function PremiumExamLoader({ steps, currentStep }: { steps: LoadStep[]; currentStep: number }) {
  return (
    <div className="flex flex-col items-center justify-center gap-5 rounded-2xl border border-dashed border-border bg-card/60 py-16">
      <BrandOrb state="searching" size={64} aria-label="Loading exams" />
      <div className="space-y-3 text-center" role="status">
        <motion.p key={currentStep} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="text-sm font-medium">
          {steps[currentStep]?.label || "Loading..."}
        </motion.p>
        <div className="flex justify-center gap-1.5">
          {steps.map((_, i) => (
            <motion.div
              key={i}
              className={`h-1.5 rounded-full ${i === currentStep ? "w-6 bg-primary" : i < currentStep ? "w-1.5 bg-primary/50" : "w-1.5 bg-muted"}`}
              animate={{ scale: i === currentStep ? 1.15 : 1 }}
              transition={{ duration: 0.3 }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

