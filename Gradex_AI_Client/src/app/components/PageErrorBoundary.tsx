import { Component, ErrorInfo, ReactNode } from "react";
import { Button } from "./ui/button";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
  componentStack: string;
}

/**
 * Catches a render error in one page so the rest of the app (sidebar, session) stays
 * up. Without it a single bad render unmounts the whole tree and leaves a blank screen.
 * The message and component stack are shown on screen so they can be copied or
 * screenshotted straight into a bug report.
 */
export class PageErrorBoundary extends Component<Props, State> {
  state: State = { error: null, componentStack: "" };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[PageErrorBoundary]", error, info.componentStack);
    this.setState({ componentStack: info.componentStack ?? "" });
  }

  render() {
    const { error, componentStack } = this.state;
    if (!error) return this.props.children;

    const stackLines = componentStack.split("\n").map((line) => line.trim()).filter(Boolean).slice(0, 8);
    return (
      <div className="m-6 max-w-3xl space-y-3 rounded-lg border border-destructive/40 bg-destructive/5 p-5">
        <div className="text-sm font-medium text-destructive">This page hit an unexpected error.</div>
        <p className="break-words text-sm text-foreground">{error.message || String(error)}</p>
        {stackLines.length > 0 && (
          <pre className="max-h-48 overflow-auto rounded bg-muted p-3 text-xs text-muted-foreground">
            {stackLines.join("\n")}
          </pre>
        )}
        <div className="flex gap-2">
          <Button type="button" size="sm" onClick={() => this.setState({ error: null, componentStack: "" })}>
            Try again
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={() => window.location.reload()}>
            Reload page
          </Button>
        </div>
      </div>
    );
  }
}
