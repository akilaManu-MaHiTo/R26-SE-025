import { useLayoutEffect, useRef, useState, type ComponentProps } from "react";
import { Textarea } from "./ui/textarea";

type Props = Omit<ComponentProps<typeof Textarea>, "value"> & { value: string; questionId?: string };

export function QuestionTextInput({ value, questionId, onFocus, onBlur, ...props }: Props) {
  const previousId = useRef(questionId);
  const focused = useRef(false);
  const typingTimer = useRef<number | undefined>(undefined);
  const [visibleText, setVisibleText] = useState<string | null>(null);

  useLayoutEffect(() => {
    const generated = questionId?.startsWith("generated") && questionId !== previousId.current;
    previousId.current = questionId;
    if (!generated || !value || focused.current || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setVisibleText(null);
      return;
    }
    const characters = Array.from(value);
    const duration = Math.min(characters.length * 14, 1800);
    const started = Date.now();
    setVisibleText("");
    const timer = window.setInterval(() => {
      const progress = Math.min((Date.now() - started) / duration, 1);
      if (progress >= 1) {
        setVisibleText(null);
        window.clearInterval(timer);
      } else {
        setVisibleText(characters.slice(0, Math.floor(characters.length * progress)).join(""));
      }
    }, 20);
    typingTimer.current = timer;
    return () => window.clearInterval(timer);
  }, [value, questionId]);

  return <Textarea {...props} value={visibleText ?? value} aria-busy={visibleText !== null}
    onFocus={event => {
      focused.current = true;
      window.clearInterval(typingTimer.current);
      setVisibleText(null);
      onFocus?.(event);
    }}
    onBlur={event => { focused.current = false; onBlur?.(event); }} />;
}
