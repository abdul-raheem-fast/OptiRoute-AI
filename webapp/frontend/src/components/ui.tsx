import type { CSSProperties, ReactNode } from "react";
import { useReveal } from "../hooks";

/* ------------------------------------------------------------------ Section */
interface SectionProps {
  id: string;
  index: string;
  eyebrow: string;
  title: ReactNode;
  lead?: ReactNode;
  children: ReactNode;
}

/** A numbered page section with a scroll-reveal wrapper. */
export function Section({ id, index, eyebrow, title, lead, children }: SectionProps) {
  const ref = useReveal<HTMLElement>();
  return (
    <section id={id} ref={ref} className="section reveal">
      <div className="container">
        <header className="section-head">
          <span className="eyebrow">
            <span className="idx">{index}</span>
            {eyebrow}
          </span>
          <h2>{title}</h2>
          {lead ? <p>{lead}</p> : null}
        </header>
        {children}
      </div>
    </section>
  );
}

/* --------------------------------------------------------------------- Card */
type CardVariant = "base" | "elevated" | "hero" | "hover";

const CARD_CLASS: Record<CardVariant, string> = {
  base: "card",
  elevated: "card card--elevated",
  hero: "card card--hero",
  hover: "card card--hover",
};

interface CardProps {
  variant?: CardVariant;
  className?: string;
  style?: CSSProperties;
  children: ReactNode;
  as?: "div" | "article" | "aside";
}

export function Card({ variant = "base", className = "", style, children, as = "div" }: CardProps) {
  const Tag = as;
  return (
    <Tag className={`${CARD_CLASS[variant]} ${className}`.trim()} style={style}>
      {children}
    </Tag>
  );
}

interface CardTitleProps {
  children: ReactNode;
  hint?: ReactNode;
}

export function CardTitle({ children, hint }: CardTitleProps) {
  return (
    <div className="card-title">
      <span>{children}</span>
      {hint ? <span className="hint">{hint}</span> : null}
    </div>
  );
}

/* ---------------------------------------------------------------- StatTile */
interface StatTileProps {
  value: ReactNode;
  unit?: string;
  label: ReactNode;
  accent?: boolean;
}

export function StatTile({ value, unit, label, accent = false }: StatTileProps) {
  return (
    <div className={`stat-tile ${accent ? "stat-tile--accent" : ""}`.trim()}>
      <span className="stat-value">
        {value}
        {unit ? <span className="unit">{unit}</span> : null}
      </span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

/* --------------------------------------------------------------------- Pill */
type PillTone = "ok" | "bad" | "warn" | "info";

export function Pill({ tone = "info", children }: { tone?: PillTone; children: ReactNode }) {
  return <span className={`pill pill--${tone}`}>{children}</span>;
}

/* --------------------------------------------------------------- BlockLabel */
export function BlockLabel({ children, tag }: { children: ReactNode; tag?: ReactNode }) {
  return (
    <div className="block-label">
      <span>{children}</span>
      {tag ? <span className="tag">{tag}</span> : null}
    </div>
  );
}

export function Note({ children }: { children: ReactNode }) {
  return <p className="note">{children}</p>;
}

/* --------------------------------------------------------------- Segmented */
interface SegmentedOption<T extends string> {
  value: T;
  label: string;
  title?: string;
}

interface SegmentedProps<T extends string> {
  options: SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  ariaLabel: string;
}

/** Pill-style segmented control used for the routing-mode policy switch. */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  ariaLabel,
}: SegmentedProps<T>) {
  return (
    <div className="segmented" role="group" aria-label={ariaLabel}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          className={o.value === value ? "is-active" : ""}
          aria-pressed={o.value === value}
          title={o.title}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------- Collapsible */
interface CollapsibleProps {
  id?: string;
  title: ReactNode;
  hint?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
}

/** Progressive-disclosure panel. Keeps deep detail (methodology, secondary
 *  tables) one click away so the default demo view stays clean. Native
 *  <details>/<summary>, so it works without JavaScript. */
export function Collapsible({ id, title, hint, defaultOpen = false, children }: CollapsibleProps) {
  return (
    <details id={id} className="collapsible" open={defaultOpen || undefined}>
      <summary>
        <span className="collapsible-title">{title}</span>
        {hint ? <span className="hint">{hint}</span> : null}
        <span className="collapsible-chev" aria-hidden="true">
          &#9656;
        </span>
      </summary>
      <div className="collapsible-body">{children}</div>
    </details>
  );
}

/* ------------------------------------------------------------- Empty states */
export function EmptyState({ glyph = "◎", title, body }: { glyph?: string; title: string; body?: ReactNode }) {
  return (
    <div className="empty-state">
      <span className="glyph" aria-hidden="true">
        {glyph}
      </span>
      <strong>{title}</strong>
      {body ? <p>{body}</p> : null}
    </div>
  );
}

export function Skeleton({ label = "loading router" }: { label?: string }) {
  return (
    <div className="skeleton">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}
