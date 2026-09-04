export function Footer() {
  return (
    <footer className="footer">
      <div className="container footer-inner">
        <span>
          <strong>OptiRoute AI</strong> — intelligent LLM routing &amp; benchmark suite.
        </span>
        <nav className="footer-links" aria-label="Footer">
          <a href="#results">Measured results</a>
          <a href="#evidence">Evidence lab</a>
          <a href="/api/docs">API docs</a>
          <a href="https://github.com/abdul-raheem-fast/OptiRoute-AI" rel="noreferrer">
            Source
          </a>
        </nav>
        <span>No live model calls are made by this dashboard.</span>
      </div>
    </footer>
  );
}
