import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  /** Shown in the fallback so a broken panel is identifiable at a glance. */
  label: string;
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Keeps a single failing panel from unmounting the whole page.
 *
 * React 18 unmounts the entire root on an uncaught render error, which during a
 * live demo means a blank screen. Each section is wrapped so the worst case is
 * one visibly broken card and a working page everywhere else.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Surfaced in the console for debugging; never swallowed silently.
    console.error(`[OptiRoute] "${this.props.label}" failed to render:`, error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="card" style={{ borderColor: "var(--danger)" }}>
          <div className="card-title">
            <span>{this.props.label}</span>
            <span className="hint">render error</span>
          </div>
          <p className="note">
            This panel hit an error and was skipped so the rest of the dashboard keeps
            working.
            <br />
            <code className="mono" style={{ color: "var(--danger)" }}>
              {this.state.error.message}
            </code>
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}
