import type { Citation, QueryResult } from "@/lib/types";
import {
  cn,
  DocTypeBadge,
  formatDateRange,
  HighlightedText,
  IconAlert,
  IconArrow,
  IconCheck,
  IconScale,
  IconTrace,
  IconX,
  StatusBadge,
} from "./common";

const RULE_LABELS: Record<string, string> = {
  scope: "Question scope",
  supersession: "Explicit supersession",
  authority: "Documented authority",
  effective_date: "Effective date",
  revalidation: "Evidence revalidation",
  abstain_no_precedence: "Abstain: no precedence",
  evidence_grounding: "Evidence grounding",
  no_evidence: "No evidence",
  llm_review: "Model review",
};

interface Props {
  result: QueryResult;
  onInspectConflicts: () => void;
  onInspectTrace: () => void;
}

export function AnswerView({ result, onInspectConflicts, onInspectTrace }: Props) {
  const citationMap = new Map<string, Citation>(
    result.citations.map((citation) => [citation.passage_id, citation]),
  );
  const preferred = result.conflicts.find(
    (conflict) => conflict.resolution === "resolved" && conflict.preferred_document_title,
  );
  const passed = result.validation.checks.filter((check) => check.passed).length;
  const unresolved = result.status === "conflict_unresolved";

  return (
    <div className="rise space-y-4">
      <article className="card overflow-hidden">
        <div className="border-b border-line bg-[#faf8f2] px-5 py-4 sm:px-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="eyebrow">Final response</span>
              <StatusBadge status={result.status} />
              {preferred ? (
                <span className="inline-flex items-center gap-1 rounded-full border border-[#b7cdbf] bg-[#eaf1eb] px-2 py-0.5 text-[10px] text-[#2f5d50]">
                  <IconCheck size={10} /> Governing source selected
                </span>
              ) : null}
            </div>
            <div className="flex flex-wrap items-center gap-2 font-mono text-[9.5px] text-muted">
              <span>{result.as_of}</span>
              <span className="h-2.5 w-px bg-line" />
              <span>{result.mode === "llm_assisted" ? "LLM-assisted" : "Deterministic mode"}</span>
              <span className="h-2.5 w-px bg-line" />
              <span>{result.query_id}</span>
            </div>
          </div>
        </div>

        <div className="px-5 py-5 sm:px-6 sm:py-6">
          {unresolved ? (
            <div className="mb-5 flex items-start gap-3 rounded-xl border border-[#e3c9a3] bg-[#fbf2e3] px-4 py-3">
              <IconAlert size={18} className="mt-0.5 shrink-0 text-[#8a4f12]" />
              <div className="min-w-0">
                <p className="text-[12px] font-semibold text-[#71440f]">
                  No winner selected. This is not a verified answer.
                </p>
                <p className="mt-0.5 text-[11.5px] leading-relaxed text-[#7a5a2b]">
                  TruthGuard found conflicting evidence it cannot reliably resolve. Both positions
                  are presented below; inspect the conflict rather than treating either as current.
                </p>
                <button
                  type="button"
                  onClick={onInspectConflicts}
                  className="mt-2 inline-flex items-center gap-1 text-[11px] font-medium text-[#71440f] underline decoration-[#c8a56b] underline-offset-4"
                >
                  Inspect the unresolved conflict <IconArrow size={12} />
                </button>
              </div>
            </div>
          ) : null}

          {result.status === "insufficient_evidence" || result.status === "no_relevant_evidence" ? (
            <div className="mb-5 flex items-start gap-3 rounded-xl border border-line bg-[#f4f1e8] px-4 py-3">
              <IconAlert size={17} className="mt-0.5 shrink-0 text-muted" />
              <p className="text-[11.5px] leading-relaxed text-muted">
                The corpus did not supply enough relevant evidence for a reliable answer. This is an
                explicit evidence-gap response, not a generated guess.
              </p>
            </div>
          ) : null}

          <div className="space-y-3 text-[17px] leading-[1.7] text-ink sm:text-[18.5px]">
            {result.answer.split(/\n\n+/).map((paragraph, index) => (
              <p key={index} className="whitespace-pre-line">
                <HighlightedText text={paragraph} />
              </p>
            ))}
          </div>
        </div>

        <div className="grid border-t border-line sm:grid-cols-[1.15fr_0.85fr]">
          <div className="border-b border-line px-5 py-4 sm:border-b-0 sm:border-r sm:px-6">
            <div className="eyebrow">Why this resolution</div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {result.resolution_rules.map((rule) => (
                <span
                  key={rule}
                  className="rounded border border-[#c9d8ce] bg-[#edf3ef] px-2 py-0.5 font-mono text-[9.5px] text-[#2f5d50]"
                >
                  {RULE_LABELS[rule] || rule}
                </span>
              ))}
            </div>
            <p className="mt-2.5 text-[12px] leading-relaxed text-muted">{result.resolution_reason}</p>
          </div>
          <div className="px-5 py-4 sm:px-6">
            <div className="eyebrow">Verification</div>
            <div className="mt-2 flex items-center gap-2">
              <span
                className={cn(
                  "flex h-7 w-7 items-center justify-center rounded-full border",
                  result.validation.valid
                    ? "border-[#b7cdbf] bg-[#e8f0ea] text-[#2f5d50]"
                    : "border-[#e5bcb5] bg-[#f8e9e6] text-[#8c2f2f]",
                )}
              >
                {result.validation.valid ? <IconCheck size={14} /> : <IconX size={14} />}
              </span>
              <div>
                <p className="text-[12px] font-medium">
                  {result.validation.valid ? "Structural checks passed" : "Validation flagged issues"}
                </p>
                <p className="text-[10.5px] text-muted">
                  {passed} of {result.validation.checks.length} checks · citation provenance only
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={onInspectTrace}
              className="mt-3 inline-flex items-center gap-1.5 text-[11px] font-medium text-[#3f5c50] hover:underline"
            >
              <IconTrace size={13} /> View verification trace
            </button>
          </div>
        </div>
      </article>

      <div className="grid gap-4 xl:grid-cols-[1fr_0.9fr]">
        <section className="card p-5 sm:p-6">
          <div className="flex items-baseline justify-between gap-3">
            <div>
              <div className="eyebrow">Atomic claims</div>
              <h3 className="font-display mt-0.5 text-[20px]">What the answer asserts</h3>
            </div>
            <span className="font-mono text-[10px] text-muted">{result.claims.length} claims</span>
          </div>
          {result.claims.length ? (
            <ol className="mt-4 space-y-3">
              {result.claims.map((claim, index) => (
                <li key={claim.id} className="flex gap-3">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-line bg-[#f2efe7] font-mono text-[9.5px] text-muted">
                    {index + 1}
                  </span>
                  <div className="min-w-0">
                    <p className="text-[12.5px] leading-relaxed text-ink">
                      <HighlightedText text={claim.text} />
                    </p>
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {claim.support_ids
                        .map((passageId) => ({ passageId, citation: citationMap.get(passageId) }))
                        .filter(
                          (item, index, items) =>
                            items.findIndex(
                              (candidate) =>
                                candidate.citation?.title === item.citation?.title &&
                                candidate.citation?.page === item.citation?.page,
                            ) === index,
                        )
                        .map(({ passageId, citation }) => (
                          <span
                            key={passageId}
                            className="inline-flex max-w-full items-center gap-1 rounded border border-line bg-[#f7f4ed] px-1.5 py-0.5 font-mono text-[9px] text-muted"
                            title={citation?.excerpt}
                          >
                            {citation ? `${citation.title} · p. ${citation.page}` : passageId}
                          </span>
                        ))}
                      {claim.supported ? (
                        <span className="inline-flex items-center gap-1 text-[9.5px] text-[#3f6b5a]">
                          <IconCheck size={10} /> grounded
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[9.5px] text-[#8c2f2f]">
                          <IconX size={10} /> unsupported
                        </span>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <p className="mt-4 text-[12px] text-muted">
              No supported factual claim survived verification. The answer reports an evidence gap.
            </p>
          )}
        </section>

        <section className="card p-5 sm:p-6">
          <div className="flex items-baseline justify-between gap-3">
            <div>
              <div className="eyebrow">Evidence validation</div>
              <h3 className="font-display mt-0.5 text-[20px]">Checks performed</h3>
            </div>
            <span className="font-mono text-[10px] text-muted">
              {passed}/{result.validation.checks.length}
            </span>
          </div>
          <ul className="mt-4 space-y-2">
            {result.validation.checks.map((check) => (
              <li key={check.id} className="flex items-start gap-2">
                <span
                  className={cn(
                    "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full",
                    check.passed ? "bg-[#e5efe8] text-[#2f5d50]" : "bg-[#f8e9e6] text-[#8c2f2f]",
                  )}
                >
                  {check.passed ? <IconCheck size={10} /> : <IconX size={10} />}
                </span>
                <div className="min-w-0">
                  <p className="text-[11px] font-medium leading-snug">{check.name}</p>
                  <p className="mt-0.5 text-[10px] leading-relaxed text-muted">{check.detail}</p>
                </div>
              </li>
            ))}
          </ul>
          <p className="mt-4 border-t border-line pt-3 text-[10px] leading-relaxed text-muted">
            {result.validation.semantic_caveat}
          </p>
        </section>
      </div>

      <section className="card p-5 sm:p-6">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <div className="eyebrow">Provenance</div>
            <h3 className="font-display mt-0.5 text-[20px]">Supporting citations</h3>
          </div>
          <span className="text-[10px] text-muted">
            Every excerpt below was retrieved from the corpus and resolved to a stored passage.
          </span>
        </div>
        {result.citations.length ? (
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {result.citations.map((citation) => (
              <CitationCard key={citation.passage_id} citation={citation} />
            ))}
          </div>
        ) : (
          <p className="mt-3 text-[12px] text-muted">No citations were returned for this response.</p>
        )}
      </section>

      <div className="flex items-start gap-2 px-1 text-[10.5px] leading-relaxed text-muted">
        <IconScale size={13} className="mt-0.5 shrink-0" />
        <p>
          {result.mode_note}
          {result.validation.notes.length ? (
            <span className="mt-1 block">Validation notes: {result.validation.notes.join(" ")}</span>
          ) : null}
        </p>
      </div>
    </div>
  );
}

function CitationCard({ citation }: { citation: Citation }) {
  return (
    <div className="rounded-xl border border-line bg-[#faf8f1] p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[12.5px] font-semibold leading-snug">{citation.title}</p>
          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[9.5px] text-muted">
            <DocTypeBadge type={citation.doc_type} />
            <span className="font-mono">v{citation.version}</span>
            <span>p. {citation.page}</span>
            <span>·</span>
            <span>{formatDateRange(citation.published_date, citation.effective_date)}</span>
          </div>
        </div>
        <span className="shrink-0 rounded border border-line bg-surface px-1.5 py-0.5 font-mono text-[8.5px] uppercase tracking-[0.08em] text-muted">
          source
        </span>
      </div>
      <blockquote className="quote mt-3 border-l-2 border-[#b9c9bd] pl-3 text-[13.5px] text-[#3d3a33]">
        “<HighlightedText text={citation.excerpt} />”
      </blockquote>
      <p className="mt-2 font-mono text-[9px] text-muted">
        {citation.authority_label || "authority not recorded"}
      </p>
    </div>
  );
}
