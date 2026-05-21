import React from "react";

const ERROR_STYLES = {
  container: {
    minHeight: "200px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  card: {
    maxWidth: "480px",
    padding: "24px",
    background: "#fff",
    borderRadius: "12px",
    border: "1px solid #fecaca",
    boxShadow: "0 4px 6px -1px rgba(0,0,0,0.1)",
    textAlign: "center",
  },
  title: {
    fontSize: "16px",
    fontWeight: 600,
    color: "#991b1b",
    marginBottom: "8px",
  },
  message: {
    fontSize: "13px",
    color: "#7f1d1d",
    marginBottom: "16px",
    lineHeight: 1.5,
  },
  button: {
    padding: "8px 20px",
    fontSize: "13px",
    fontWeight: 500,
    background: "#dc2626",
    color: "#fff",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
  },
};

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("[ErrorBoundary]", error, errorInfo);
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div style={ERROR_STYLES.container}>
          <div style={ERROR_STYLES.card}>
            <div style={ERROR_STYLES.title}>Something went wrong</div>
            <div style={ERROR_STYLES.message}>
              {this.state.error?.message || "An unexpected error occurred."}
              <br />
              Try refreshing the page or resetting the component.
            </div>
            <button style={ERROR_STYLES.button} onClick={this.handleReset}>
              Reset
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
