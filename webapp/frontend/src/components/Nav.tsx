import { useActiveSection } from "../hooks";

const LINKS = [
  { id: "arena", label: "Arena" },
  { id: "results", label: "Results" },
  { id: "evidence", label: "Evidence" },
  { id: "impact", label: "Savings" },
  { id: "operations", label: "Ops" },
  { id: "models", label: "Models" },
  { id: "how", label: "How" },
  { id: "api", label: "API" },
] as const;

/** Every section id, in page order — used for scroll-spy. */
export const SECTION_IDS: string[] = LINKS.map((l) => l.id);

interface NavProps {
  theme: "dark" | "light";
  onToggleTheme: () => void;
}

export function Nav({ theme, onToggleTheme }: NavProps) {
  const active = useActiveSection(SECTION_IDS);

  return (
    <header className="nav">
      <div className="container nav-inner">
        <a className="brand" href="#top" aria-label="OptiRoute AI — back to top">
          <span className="brand-mark" aria-hidden="true">
            &#9670;
          </span>
          <span>
            OptiRoute AI
            <br />
            <small>Intelligent LLM Router</small>
          </span>
        </a>

        <nav className="nav-links" aria-label="Sections">
          {LINKS.map((l) => (
            <a
              key={l.id}
              href={`#${l.id}`}
              aria-current={active === l.id ? "true" : undefined}
              style={active === l.id ? { color: "var(--accent)" } : undefined}
            >
              {l.label}
            </a>
          ))}
        </nav>

        <div className="nav-actions">
          <a className="icon-btn" href="/api/docs" title="OpenAPI docs" aria-label="OpenAPI docs">
            &#123;&#125;
          </a>
          <button
            type="button"
            className="icon-btn"
            onClick={onToggleTheme}
            title="Toggle colour scheme"
            aria-label="Toggle colour scheme"
          >
            {theme === "dark" ? "\u2600" : "\u263E"}
          </button>
        </div>
      </div>
    </header>
  );
}
