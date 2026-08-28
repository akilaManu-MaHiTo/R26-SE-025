import React from "react";
import { Card } from "./ui/card";
import { Loader2, Check } from "lucide-react";

export interface LoadStep {
  label: string;
}

interface ProgressLoaderProps {
  steps: LoadStep[];
  currentStep: number;
  className?: string;
}

export function ProgressLoader({ steps, currentStep, className }: ProgressLoaderProps) {
  const progress = steps.length > 0 ? ((currentStep + 1) / steps.length) * 100 : 0;

  return (
    <div className={`flex items-center justify-center ${className ?? ""}`}>
      <Card className="w-full max-w-md p-8 border-border bg-card/50 backdrop-blur-sm">
        <div className="space-y-6">
          {/* Steps */}
          <div className="space-y-3">
            {steps.map((step, i) => {
              const isCompleted = i < currentStep;
              const isCurrent = i === currentStep;
              const isPending = i > currentStep;

              return (
                <div key={i} className="flex items-center gap-3">
                  {/* Icon */}
                  <div className="flex-shrink-0">
                    {isCompleted ? (
                      <div className="size-6 rounded-full bg-primary flex items-center justify-center">
                        <Check className="size-3.5 text-primary-foreground" strokeWidth={3} />
                      </div>
                    ) : isCurrent ? (
                      <Loader2 className="size-6 text-primary animate-spin" />
                    ) : (
                      <div className="size-6 rounded-full bg-muted border border-border" />
                    )}
                  </div>
                  {/* Label */}
                  <span
                    className={`text-sm ${
                      isCompleted
                        ? "text-muted-foreground"
                        : isCurrent
                        ? "text-foreground font-medium"
                        : "text-muted-foreground/50"
                    }`}
                  >
                    {step.label}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Progress bar */}
          <div className="space-y-2">
            <div className="h-1.5 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-all duration-500 ease-out"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground text-right">
              {Math.round(progress)}% complete
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
