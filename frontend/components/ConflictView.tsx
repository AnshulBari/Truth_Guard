import type { Conflict, ConflictStatement, QueryResult } from "@/lib/types";
import {
  cn,
  DocTypeBadge,
  EmptyState,
  formatDate,
  HighlightedText,
  IconAlert,
  IconArrow,
  IconCheck,
  IconScale,
  KindBadge,
  SeverityBadge,
  SourceBadge,
} from "./common";

export function ConflictView({ result }: { result: QueryResult }) {
  if (!result.conflicts.length) {
    return (
      <div className="rise space-y-4">
        <div className="card p-6">
          <div className="eyebrow">Conflict inspector</div>
          <h2 className="font-display mt-1 text-[24px]">No conflicts found</h2>
          <p className="mt-2 max-w-2xl text-[12.5px] leading-relaxed text-muted">
            Retrieval and deterministic checks did not find incompatible statements within the
            relevant scope. This is not proof of semantic correctness: the verifier only establishes
            that citations resolve to real passages and that claims are lexically grounded.
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <Metric label="Conflicts" value="0" />
          <Metric label="Retrieved passages" value={String(result.retrieved_passages.length)} />
          <Metric label="Final status" value={result.status.replaceAll("_", " ")} />
        </div>
      </div>
    );
  }

  const unresolved = result.conflicts.filter((conflict) => conflict.resolution === "unresolved").length;
  return (
    <div className="rise space-y-4">
      <div className="card px-5 py-4 sm:px-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="eyebrow">Conflict inspector</div>
            <h2 className="font-display mt-1 text-[25px] leading-tight">
              {result.conflicts.length} conflict{result.conflicts.length === 1 ? "" : "s"} under review
            </h2>
            <p className="mt-1 max-w-2xl text-[12px] leading-relaxed text-muted">
              Quotes are retrieved evidence. Classifications, precedence decisions and abstentions
              are TruthGuard&apos;s inferences from document metadata and explicit rules.
            </p>
          </div>
          <div className="flex gap-2">
            <span className="rounded-full border border-line bg-[#f3f0e8] px-2.5 py-1 text-[10.5px] text-muted">
              {result.conflicts.length - unresolved} resolved
            </span>
            <span
              className={cn(
                "rounded-full border px-2.5 py-1 text-[10.5px]",
                unresolved
                  ? "border-[#e3c9a3] bg-[#f8eddc] text-[#7c4710]"
                  : "border-[#b7cdbf] bg-[#eaf1eb] text-[#2f5d50]",
              )}
            >
              {unresolved} unresolved
            </span>
          </div>
        </div>
      </div>

      {result.conflicts.map((conflict, index) => (
        <ConflictCard key={conflict.id} conflict={conflict} index={index} />
      ))}
    </div>
  );
}

function ConflictCard({ conflict, index }: { conflict: Conflict; index: number }) {
  const preferredId = conflict.preferred_document_id;
  const statements = conflict.statements.slice(0, 2);
  const supersession = conflict.kind === "supersession" && conflict.superseding_document_title;
  const supersedingStatement = statements.find(
    (statement) => statement.document_id === conflict.superseding_document_id,
  );
  const supersededStatement = statements.find(
    (statement) => statement.document_id === conflict.superseded_document_id,
  );
  const resolved = conflict.resolution === "resolved";

  return (
    <section className="card overflow-hidden" id={`conflict-${conflict.id}`}>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line bg-[#faf8f2] px-5 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-[9.5px] text-muted">C{String(index + 1).padStart(2, "0")}</span>
          <KindBadge kind={conflict.kind} />
          <SeverityBadge severity={conflict.severity} />
          <SourceBadge source={conflict.source} />
        </div>
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10.5px] font-medium",
            resolved
              ? "border-[#b7cdbf] bg-[#e8f0ea] text-[#2f5d50]"
              : "border-[#e3c9a3] bg-[#f8eddc] text-[#7c4710]",
          )}
        >
          {resolved ? <IconCheck size={11} /> : <IconAlert size={11} />}
          {resolved ? "Resolved" : "Unresolved — no winner"}
        </span>
      </div>

      <div className="px-5 py-4 sm:px-6">
        <p className="text-[13px] leading-relaxed text-ink">{conflict.explanation}</p>
      </div>

      {supersession ? (
        <div className="mx-5 mb-4 flex flex-wrap items-center gap-2 rounded-xl border border-[#c9d8ce] bg-[#f0f5f1] px-3 py-2.5 sm:mx-6">
          <span className="eyebrow text-[#426153]">Declared relationship</span>
          <span className="text-[11px] text-muted">
            {conflict.superseded_document_title}
            {supersededStatement ? ` v${supersededStatement.version}` : ""}
          </span>
          <span className="inline-flex items-center gap-1 rounded-full border border-[#b7cdbf] bg-surface px-2 py-0.5 font-mono text-[9px] text-[#2f5d50]">
            superseded by <IconArrow size={10} />
          </span>
          <span className="text-[11px] font-medium text-ink">
            {conflict.superseding_document_title}
            {supersedingStatement ? ` v${supersedingStatement.version}` : ""}
          </span>
          {supersedingStatement?.effective_date ? (
            <span className="font-mono text-[9.5px] text-muted">
              effective {formatDate(supersedingStatement.effective_date)}
            </span>
          ) : null}
        </div>
      ) : null}

      {statements.length >= 2 ? (
        <div className="grid gap-3 px-5 pb-4 sm:px-6 md:grid-cols-2">
          {statements.map((statement, statementIndex) => (
            <StatementCard
              key={`${statement.passage_id}-${statementIndex}`}
              statement={statement}
              preferred={resolved && statement.document_id === preferredId}
              resolved={resolved}
              label={statementIndex === 0 ? "Position A" : "Position B"}
            />
          ))}
        </div>
      ) : (
        <div className="px-5 pb-4 sm:px-6">
          <div className="rounded-xl border border-dashed border-line bg-[#f7f4ec] px-4 py-4 text-[12px] text-muted">
            {conflict.source === "llm"
              ? "This concern was raised by the semantic model critic. The model is not trusted as an oracle, so no deterministic precedence claim is made."
              : "The critic did not provide two comparable statements for this finding."}
          </div>
        </div>
      )}

      <div className="border-t border-line bg-[#f7f4ec] px-5 py-4 sm:px-6">
        <div className="flex items-start gap-2">
          <IconScale size={15} className="mt-0.5 shrink-0 text-[#4f6a5e]" />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="eyebrow text-[#426153]">Inferred resolution</span>
              {resolved && preferredId ? (
                <span className="rounded border border-[#b7cdbf] bg-[#eaf1eb] px-1.5 py-0.5 font-mono text-[9px] text-[#2f5d50]">
                  preferred · {conflict.preferred_document_title}
                </span>
              ) : (
                <span className="rounded border border-[#e3c9a3] bg-[#f8eddc] px-1.5 py-0.5 font-mono text-[9px] text-[#7c4710]">
                  no preferred source
                </span>
              )}
            </div>
            <p className="mt-1.5 text-[12px] leading-relaxed text-[#4e4a40]">{conflict.resolution_note}</p>
            <p className="mt-2 text-[10px] leading-relaxed text-muted">
              <span className="font-medium">Suggested next action:</span> {conflict.suggested_action}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

function StatementCard({
  statement,
  preferred,
  resolved,
  label,
}: {
  statement: ConflictStatement;
  preferred: boolean;
  resolved: boolean;
  label: string;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border p-4",
        preferred
          ? "border-[#a9c1b1] bg-[#f4f8f4]"
          : "border-line bg-[#fcfaf5]",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-muted">{label}</span>
        {preferred ? (
          <span className="inline-flex items-center gap-1 rounded-full border border-[#b7cdbf] bg-[#e8f0ea] px-2 py-0.5 text-[9px] font-medium text-[#2f5d50]">
            <IconCheck size={9} /> Governs under rule
          </span>
        ) : resolved ? (
          <span className="rounded-full border border-line bg-[#f2efe7] px-2 py-0.5 text-[9px] text-muted">
            Not applied
          </span>
        ) : (
          <span className="rounded-full border border-[#e3c9a3] bg-[#f8eddc] px-2 py-0.5 text-[9px] text-[#7c4710]">
            Not verified
          </span>
        )}
      </div>

      <div className="mt-2">
        <p className="text-[12.5px] font-semibold leading-snug">{statement.title}</p>
        <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[9.5px] text-muted">
          <DocTypeBadge type={statement.doc_type} />
          <span className="font-mono">v{statement.version}</span>
          <span>p. {statement.page}</span>
        </div>
        <div className="mt-1.5 grid grid-cols-2 gap-x-2 gap-y-0.5 font-mono text-[9px] text-muted">
          <span>pub {formatDate(statement.published_date)}</span>
          <span>eff {formatDate(statement.effective_date)}</span>
        </div>
      </div>

      <blockquote className="quote mt-3 rounded-lg border border-[#e7dcc7] bg-[#fbf5e8] px-3 py-2.5 text-[13px] leading-relaxed text-[#443f33]">
        “<HighlightedText text={statement.statement} />”
      </blockquote>
      <p className="mt-2 font-mono text-[8.5px] uppercase tracking-[0.08em] text-muted">
        {statement.authority_label || "Authority not recorded"}
      </p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="card px-4 py-3">
      <div className="eyebrow">{label}</div>
      <div className="mt-1 font-display text-[22px] capitalize">{value}</div>
    </div>
  );
}
