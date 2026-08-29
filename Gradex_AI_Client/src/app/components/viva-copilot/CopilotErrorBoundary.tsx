import { Component, ReactNode } from "react";
import { Button } from "../ui/button";

interface Props {
  children: ReactNode;
}

interface State {
  message: string;
}

export class CopilotErrorBoundary extends Component<Props, State> {
  state: State = { message: "" };

  static getDerivedStateFromError(error: Error): State {
    return { message: error?.message || "The copilot page hit an unexpected error." };
  }

  render() {
    if (this.state.message) {
      return (
        <div className="p-6 space-y-3">
          <p className="text-sm text-destructive">{this.state.message}</p>
          <Button type="button" onClick={() => this.setState({ message: "" })}>
            Try again
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
