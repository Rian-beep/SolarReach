import { Component, type ReactNode, type ErrorInfo } from "react";

interface State {
  err: Error | null;
}

interface Props {
  children: ReactNode;
  /** Optional label for which subtree this is wrapping (shown to user). */
  scope?: string;
}

/**
 * Standard React error boundary so a crash in MapSlot, LeadDrawer, etc.
 * doesn't black-screen the whole cockpit — we render a Gotham-styled fallback
 * panel with the error and a Reload action.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { err: null };

  static getDerivedStateFromError(err: Error): State {
    return { err };
  }

  componentDidCatch(err: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error("[ErrorBoundary]", this.props.scope ?? "", err, info);
  }

  render() {
    if (!this.state.err) return this.props.children;
    return (
      <div className="grid h-full place-items-center bg-app-void p-8">
        <div className="max-w-lg rounded-[2px] border border-red/40 bg-app-surface p-5 font-mono text-xs">
          <div className="mb-2 text-[10px] uppercase tracking-widest text-red">
            UI ERROR · {this.props.scope ?? "root"}
          </div>
          <div className="mb-2 break-words text-bone">
            {this.state.err.name}: {this.state.err.message}
          </div>
          <pre className="mb-3 max-h-40 overflow-auto whitespace-pre-wrap text-[10px] leading-relaxed text-mute">
            {this.state.err.stack?.split("\n").slice(0, 8).join("\n")}
          </pre>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => this.setState({ err: null })}
              className="rounded-[2px] border border-iron px-3 py-1 uppercase tracking-wide text-bone hover:border-cyan hover:text-cyan"
            >
              [retry]
            </button>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="rounded-[2px] border border-cyan bg-cyan/10 px-3 py-1 uppercase tracking-wide text-cyan hover:bg-cyan/20"
            >
              [reload]
            </button>
          </div>
        </div>
      </div>
    );
  }
}
