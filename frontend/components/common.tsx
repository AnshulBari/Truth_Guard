import type { ReactNode, SVGProps } from "react";
import type {
  CriticFinding,
  DocType,
  FindingKind,
  ResolutionStatus,
  Severity,
  StageStatus,
} from "@/lib/types";

export function cn(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function Svg({ size = 16, children, ...props }: IconProps & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  );
}

export function LogoMark({ size = 34 }: { size?: number }) {
  return (
    <span
      className="inline-flex items-center justify-center rounded-[10px] border border-[#2f5d50] bg-[#2f5d50] text-[#f7f4ea]"
      style={{ width: size, height: size }}
    >
      <svg width={size * 0.58} height={size * 0.58} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M12 2.8 20 6v5.4c0 5-3.4 8.4-8 10-4.6-1.6-8-5-8-10V6l8-3.2Z"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        <path d="m8.2 12 2.6 2.5 5-5.2" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  );
}

export const IconSearch = (props: IconProps) => (
  <Svg {...props}>
    <circle cx="11" cy="11" r="7" />
    <path d="m16.5 16.5 4 4" />
  </Svg>
);

export const IconCheck = (props: IconProps) => (
  <Svg {...props}>
    <path d="m5 12.5 4.2 4.2L19 6.8" />
  </Svg>
);

export const IconX = (props: IconProps) => (
  <Svg {...props}>
    <path d="M6 6l12 12M18 6 6 18" />
  </Svg>
);

export const IconAlert = (props: IconProps) => (
  <Svg {...props}>
    <path d="M12 3 2.8 20h18.4L12 3Z" />
    <path d="M12 9v5M12 17.2v.1" />
  </Svg>
);

export const IconScale = (props: IconProps) => (
  <Svg {...props}>
    <path d="M12 3v18M7 21h10M5 7h14M5 7 2.5 13h5L5 7Zm14 0-2.5 6h5L19 7Z" />
  </Svg>
);

export const IconUpload = (props: IconProps) => (
  <Svg {...props}>
    <path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5M4 15v4h16v-4" />
  </Svg>
);

export const IconFile = (props: IconProps) => (
  <Svg {...props}>
    <path d="M6 3h8l4 4v14H6V3Z" />
    <path d="M14 3v4h4M9 12h6M9 16h6" />
  </Svg>
);

export const IconTrace = (props: IconProps) => (
  <Svg {...props}>
    <path d="M4 4v4M4 8h6M10 8v4M10 12h6M16 12v4M16 16h4" />
    <circle cx="4" cy="4" r="1.4" />
    <circle cx="20" cy="20" r="1.4" />
  </Svg>
);

export const IconChevron = (props: IconProps) => (
  <Svg {...props}>
    <path d="m6 9 6 6 6-6" />
  </Svg>
);

export const IconArrow = (props: IconProps) => (
  <Svg {...props}>
    <path d="M4 12h16m0 0-6-6m6 6-6 6" />
  </Svg>
);

export const IconLoader = (props: IconProps) => (
  <Svg {...props} className={cn("animate-spin", props.className)}>
    <path d="M21 12a9 9 0 1 1-6-8.5" />
  </Svg>
);

export const IconRefresh = (props: IconProps) => (
  <Svg {...props}>
    <path d="M20 7v5h-5M4 17v-5h5" />
    <path d="M6.1 8a7 7 0 0 1 11.6-2.2L20 8M4 16l2.3 2.2A7 7 0 0 0 18 16" />
  </Svg>
);

export const IconPlus = (props: IconProps) => (
  <Svg {...props}>
    <path d="M12 5v14M5 12h14" />
  </Svg>
);

export const IconBook = (props: IconProps) => (
  <Svg {...props}>
    <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21.5v-16Z" />
    <path d="M4 18.5A2.5 2.5 0 0 1 6.5 16H20" />
  </Svg>
);

export function StatusBadge({ status, size = "md" }: { status: ResolutionStatus; size?: "sm" | "md" }) {
  const map: Record<ResolutionStatus, { label: string; className: string; dot: string }> = {
    resolved: {
      label: "Resolved",
      className: "border-[#b7cdbf] bg-[#e8f0ea] text-[#2b594b]",
      dot: "bg-[#2f5d50]",
    },
    conflict_unresolved: {
      label: "Conflict unresolved",
      className: "border-[#e3c9a3] bg-[#f8eddc] text-[#7c4710]",
      dot: "bg-[#a4611c]",
    },
    insufficient_evidence: {
      label: "Insufficient evidence",
      className: "border-[#d7d2c4] bg-[#f0ede4] text-[#5e5a50]",
      dot: "bg-[#7a7466]",
    },
    no_relevant_evidence: {
      label: "No relevant evidence",
      className: "border-[#d7d2c4] bg-[#f0ede4] text-[#5e5a50]",
      dot: "bg-[#7a7466]",
    },
  };
  const item = map[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-medium",
        item.className,
        size === "sm" ? "px-2 py-0.5 text-[10.5px]" : "px-2.5 py-1 text-[11.5px]",
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", item.dot)} />
      {item.label}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  const map: Record<Severity, string> = {
    high: "border-[#e5bcb5] bg-[#f8e9e6] text-[#8c2f2f]",
    medium: "border-[#e3c9a3] bg-[#f8eddc] text-[#7c4710]",
    low: "border-[#d7d2c4] bg-[#f1eee6] text-[#5e5a50]",
    info: "border-[#cfd9d1] bg-[#eef2ee] text-[#426153]",
  };
  return (
    <span className={cn("rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.1em]", map[severity])}>
      {severity}
    </span>
  );
}

export const KIND_LABELS: Record<FindingKind, string> = {
  contradiction: "Direct contradiction",
  staleness: "Stale / questionable source",
  supersession: "Supersession",
  unsupported_claim: "Unsupported claim",
  scope_mismatch: "Scope mismatch",
  evidence_gap: "Evidence gap",
  citation_error: "Citation error",
};

export function KindBadge({ kind }: { kind: FindingKind }) {
  return (
    <span className="rounded-full border border-line bg-[#f3f0e8] px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.1em] text-muted">
      {KIND_LABELS[kind]}
    </span>
  );
}

export function SourceBadge({ source }: { source: CriticFinding["source"] }) {
  return (
    <span
      className={cn(
        "rounded-full border px-2 py-0.5 text-[10px] font-medium",
        source === "llm"
          ? "border-[#c9d3dc] bg-[#eef2f6] text-[#43596b]"
          : "border-line bg-[#f4f1e8] text-muted",
      )}
    >
      {source === "llm" ? "Model-observed" : "Deterministic check"}
    </span>
  );
}

export function DocTypeBadge({ type }: { type: DocType }) {
  const accent =
    type === "amendment" || type === "circular"
      ? "border-[#c3d3c7] bg-[#eaf1eb] text-[#2f5d50]"
      : type === "faq"
        ? "border-[#d9cfba] bg-[#f5efe2] text-[#6c5730]"
        : "border-line bg-[#f3f0e8] text-muted";
  return (
    <span className={cn("rounded border px-1.5 py-0.5 font-mono text-[9.5px] uppercase tracking-[0.09em]", accent)}>
      {type}
    </span>
  );
}

export function StageStatusBadge({ status }: { status: StageStatus }) {
  const map: Record<StageStatus, { label: string; className: string }> = {
    completed: { label: "Completed", className: "text-[#2f5d50] border-[#b7cdbf] bg-[#eaf1eb]" },
    fallback: { label: "Fallback", className: "text-[#7c4710] border-[#e3c9a3] bg-[#f8eddc]" },
    skipped: { label: "Skipped", className: "text-[#6d685d] border-line bg-[#f1eee6]" },
    failed: { label: "Failed", className: "text-[#8c2f2f] border-[#e5bcb5] bg-[#f8e9e6]" },
  };
  return (
    <span className={cn("rounded-full border px-2 py-0.5 text-[10px] font-medium", map[status].className)}>
      {map[status].label}
    </span>
  );
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(`${value.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

export function formatDateRange(published?: string | null, effective?: string | null): string {
  const parts: string[] = [];
  if (published) parts.push(`pub. ${formatDate(published)}`);
  if (effective) parts.push(`eff. ${formatDate(effective)}`);
  return parts.join(" · ") || "No dates recorded";
}

export function HighlightedText({ text }: { text: string }) {
  const pattern = /(₹[\d,]+|\b\d+(?:\.\d+)?\s*(?:days?|hours?|weeks?|years?|%))/g;
  const parts = text.split(pattern);
  return (
    <>
      {parts.map((part, index) => {
        if (!part) return null;
        const isValue = index % 2 === 1;
        return isValue ? (
          <mark key={`${part}-${index}`} className="mark-value">
            {part}
          </mark>
        ) : (
          <span key={`${part}-${index}`}>{part}</span>
        );
      })}
    </>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-line bg-[#f8f6f0] px-6 py-10 text-center">
      <p className="font-display text-lg">{title}</p>
      {children ? <div className="mx-auto mt-2 max-w-md text-[13px] text-muted">{children}</div> : null}
    </div>
  );
}
