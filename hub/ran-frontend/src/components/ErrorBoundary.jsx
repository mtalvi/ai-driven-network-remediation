import { Component } from "react";

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error("RAN dashboard render error:", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <h2>Dashboard error</h2>
          <p>
            Something went wrong rendering the dashboard. Polling will continue
            in the background — the view should recover on the next successful
            response.
          </p>
          <pre>{this.state.error?.message}</pre>
          <button onClick={() => this.setState({ hasError: false, error: null })}>
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
