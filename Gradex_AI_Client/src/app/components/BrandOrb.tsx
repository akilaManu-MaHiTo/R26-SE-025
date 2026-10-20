import { useTheme } from "next-themes";
import { ThinkingOrb, type ThinkingOrbProps } from "thinking-orbs";

/** Brand ink on light backgrounds. */
export const ORB_COLOR_LIGHT = "#345842";
/** The same brand green, lifted for dark backgrounds. */
export const ORB_COLOR_DARK = "#7fae90";

/**
 * ThinkingOrb tinted with the GradeX brand green, picking a light or dark
 * variant to keep the dots legible on either background.
 */
export function BrandOrb({ color, ...props }: ThinkingOrbProps) {
  const { resolvedTheme } = useTheme();
  const tint = color ?? (resolvedTheme === "dark" ? ORB_COLOR_DARK : ORB_COLOR_LIGHT);
  return <ThinkingOrb color={tint} {...props} />;
}
