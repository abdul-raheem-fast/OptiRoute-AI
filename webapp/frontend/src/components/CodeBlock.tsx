import { Fragment, useState, type ReactNode } from "react";

/**
 * Minimal JSON syntax highlighter.
 *
 * Tokenises the serialised string and maps each token to one of the tk-* colour
 * classes defined in components.css. No external highlighter dependency.
 */
const TOKEN =
  /("(?:\\.|[^"\\])*"\s*:)|("(?:\\.|[^"\\])*")|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)|\b(true|false)\b|\b(null)\b/g;

export function highlightJson(source: string): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let key = 0;
  TOKEN.lastIndex = 0;

  for (let m = TOKEN.exec(source); m !== null; m = TOKEN.exec(source)) {
    if (m.index > last) out.push(source.slice(last, m.index));
    const cls = m[1]
      ? "tk-key"
      : m[2]
        ? "tk-str"
        : m[3]
          ? "tk-num"
          : m[4]
            ? "tk-bool"
            : "tk-null";
    // A key token includes the trailing colon and whitespace — colour just the key.
    if (cls === "tk-key") {
      const raw = m[0];
      const nameEnd = raw.lastIndexOf(":");
      out.push(
        <span key={key++} className="tk-key">
          {raw.slice(0, nameEnd)}
        </span>
      );
      out.push(raw.slice(nameEnd));
    } else {
      out.push(
        <span key={key++} className={cls}>
          {m[0]}
        </span>
      );
    }
    last = m.index + m[0].length;
  }
  if (last < source.length) out.push(source.slice(last));
  return out.map((node, i) =>
    typeof node === "string" ? <Fragment key={`s${i}`}>{node}</Fragment> : node
  );
}

interface CodeBlockProps {
  title: string;
  language?: string;
  body: string;
  /** When true the body is JSON and gets token colours. */
  json?: boolean;
  action?: ReactNode;
}

export function CodeBlock({ title, language = "json", body, json = false, action }: CodeBlockProps) {
  return (
    <div className="code-block">
      <div className="code-head">
        <span className="t">
          {title} &middot; {language}
        </span>
        {action}
      </div>
      <div className="code-body">{json ? highlightJson(body) : body}</div>
    </div>
  );
}

/** Copy-to-clipboard button with a transient "copied" confirmation. */
export function CopyButton({ text, label = "copy" }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);

  return (
    <button
      type="button"
      className="btn btn--ghost btn--sm"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setDone(true);
          window.setTimeout(() => setDone(false), 1200);
        } catch {
          /* clipboard blocked — nothing to copy into */
        }
      }}
    >
      {done ? "copied ✓" : label}
    </button>
  );
}
