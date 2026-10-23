"use client";

import { useState } from "react";
import type {
  Claim,
  Conflict,
  CriticFinding,
  PipelineStage,
  QueryResult,
  ValidationCheck,
} from "@/lib/types";
import {
  cn,
  formatDuration,
  HighlightedText,
  IconCheck,
  IconChevron,
  IconTrace,
  IconX,
  KindBadge,
  SeverityBadge,
  SourceBadge,
  StageStatusBadge,
  StatusBadge,
} from "./common";

interface RetrievalDetails {
  query_terms?: string[];
  candidate_count?: number;
  raw_hit_count?: number;
  filtered_out?: number;
  coverage?: number;
  top_score?: number;
  passages?: Array<{
    passage_id: string;
    title: string;
    version: string;
    page: number;
    score: number;
    rank: number;
  }>;
}

interface SynthesisDetails {
  mode?: string;
  candidate_answer?: string;
  claims?: Claim[];
  assumptions?: string[];
  missing_information?: string[];
  note?: string;
  error?: string | null;
}

interface CritiqueDetails {
  semantic_llm_attempted?: boolean;
  semantic_llm_used?: boolean;
  findings?: CriticFinding[];
  note?: string;
}

interface ResolutionDetails {
  status?: string;
  reason?: string;
  rules?: string[];
  conflicts?: Conflict[];
}

interface ValidationDetails {
  valid?: boolean;
  checks?: ValidationCheck[];
  notes?: string[];
  removed_claims?: string[];
  semantic_caveat?: string;
}

const STAGE_LABELS: Record<string, string> = {
  retrieval: "Retrieved evidence",
  synthesis: "Candidate, not final",
  critique: "Adversarial findings",
  resolution: "Inferred decision",
  validation: "Structural verification",
};

export function TraceView({ result }: { result: QueryResult }) {
  const totalMs = result.pipeline_trace.reduce((sum, stage) => sum + stage.duration_ms, 0);
  const candidateStage = result.pipeline_trace.find((stage) => stage.id === "synthesis");
  const candidateDetails = candidateStage?.details as unknown as SynthesisDetails | undefined;
  const candidateClaims = candidateDetails?.claims || [];

  return (
    <div className="rise space-y-4">
      <div className="card px-5 py-4 sm:px-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="eyebrow">Verification trace</div>
            <h2 className="font-display mt-1 text-[25px] leading-tight">
              How this answer was challenged
            </h2>
            <p className="mt-1 max-w-2xl text-[12px] leading-relaxed text-muted">
              Five real stages, in order. Durations and outputs are recorded from this query; no
              progress or agent activity is simulated.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={result.status} />
            <span className="rounded-full border border-line bg-[#f2efe7] px-2.5 py-1 font-mono text-[10px] text-muted">
              {formatDuration(totalMs)} total
            </span>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
          <SmallMetric label="Candidate claims" value={String(candidateClaims.length)} />
          <SmallMetric label="Critic findings" value={String(result.critic_findings.length)} />
          <SmallMetric label="Conflicts" value={String(result.conflicts.length)} />
          <SmallMetric
            label="Claims retained"
            value={`${result.claims.length}/${candidateClaims.length}`}
          />
        </div>
      </div>

      <div className="space-y-3">
        {result.pipeline_trace.map((stage, index) => (
          <StageCard key={stage.id} stage={stage} index={index} result={result} />
        ))}
      </div>

      <p className="flex items-start gap-2 px-1 text-[10.5px] leading-relaxed text-muted">
        <IconTrace size={13} className="mt-0.5 shrink-0" />
        <span>
          Stage results are produced by deterministic code except where explicitly marked
          model-observed. {result.mode_note}
        </span>
      </p>
    </div>
  );
}

function StageCard({
  stage,
  index,
  result,
}: {
  stage: PipelineStage;
  index: number;
  result: QueryResult;
}) {
  const alwaysOpen = stage.id === "synthesis" || stage.id === "critique";
  const [open, setOpen] = useState(alwaysOpen);

  return (
    <section className="card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-start gap-3 px-5 py-4 text-left sm:px-6"
        aria-expanded={open}
      >
        <span
          className={cn(
            "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border font-mono text-[10px]",
            stage.status === "fallback"
              ? "border-[#e3c9a3] bg-[#f8eddc] text-[#7c4710]"
              : stage.status === "skipped"
                ? "border-line bg-[#f2efe7] text-muted"
                : "border-[#b7cdbf] bg-[#eaf1eb] text-[#2f5d50]",
          )}
        >
          {String(index + 1).padStart(2, "0")}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="font-display text-[18px] leading-none">{stage.name}</span>
            <StageStatusBadge status={stage.status} />
            <span className="font-mono text-[9.5px] text-muted">{formatDuration(stage.duration_ms)}</span>
            <span className="rounded border border-line bg-[#f5f1e8] px-1.5 py-0.5 font-mono text-[8.5px] uppercase tracking-[0.08em] text-muted">
              {STAGE_LABELS[stage.id] || "stage"}
            </span>
          </span>
          <span className="mt-1.5 block text-[12px] leading-relaxed text-muted">{stage.summary}</span>
        </span>
        <IconChevron
          size={15}
          className={cn("mt-1 shrink-0 text-muted transition-transform", open && "rotate-180")}
        />
      </button>

      {open ? (
        <div className="border-t border-line bg-[#faf8f2] px-5 py-4 sm:px-6">
          {stage.id === "retrieval" ? (
            <RetrievalDetail details={stage.details as unknown as RetrievalDetails} />
          ) : null}
          {stage.id === "synthesis" ? (
            <SynthesisDetail details={stage.details as unknown as SynthesisDetails} />
          ) : null}
          {stage.id === "critique" ? (
            <CritiqueDetail
              details={stage.details as unknown as CritiqueDetails}
              findings={result.critic_findings}
            />
          ) : null}
          {stage.id === "resolution" ? (
            <ResolutionDetail details={stage.details as unknown as ResolutionDetails} />
          ) : null}
          {stage.id === "validation" ? (
            <ValidationDetail details={stage.details as unknown as ValidationDetails} />
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function RetrievalDetail({ details }: { details: RetrievalDetails }) {
  const passages = details.passages || [];
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[9.5px] text-muted">
        <span>coverage {Math.round((details.coverage || 0) * 100)}%</span>
        <span>candidates {details.candidate_count ?? 0}</span>
        <span>off-topic filtered {details.filtered_out ?? 0}</span>
        <span>top BM25 {Number(details.top_score || 0).toFixed(2)}</span>
      </div>
      {details.query_terms?.length ? (
        <div className="flex flex-wrap items-center gap-1">
          <span className="eyebrow mr-1">Query terms</span>
          {details.query_terms.map((term) => (
            <span
              key={term}
              className="rounded border border-line bg-surface px-1.5 py-0.5 font-mono text-[9px] text-[#555044]"
            >
              {term}
            </span>
          ))}
        </div>
      ) : null}
      <div className="overflow-hidden rounded-lg border border-line bg-surface">
        {passages.length ? (
          passages.map((passage, index) => (
            <div
              key={passage.passage_id}
              className={cn(
                "flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-[11px]",
                index > 0 && "border-t border-line/80",
              )}
            >
              <div className="flex min-w-0 items-center gap-2">
                <span className="font-mono text-[9px] text-muted">#{passage.rank}</span>
                <span className="truncate font-medium">{passage.title}</span>
                <span className="font-mono text-[9px] text-muted">
                  v{passage.version} · p. {passage.page}
                </span>
              </div>
              <span className="font-mono text-[9px] text-muted">
                BM25 {Number(passage.score).toFixed(2)}
              </span>
            </div>
          ))
        ) : (
          <p className="px-3 py-3 text-[11px] text-muted">No passages passed the relevance gate.</p>
        )}
      </div>
    </div>
  );
}

function SynthesisDetail({ details }: { details: SynthesisDetails }) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="eyebrow">Candidate answer</span>
        <span className="rounded border border-[#e3c9a3] bg-[#f8eddc] px-1.5 py-0.5 font-mono text-[8.5px] uppercase tracking-[0.08em] text-[#7c4710]">
          not final · {details.mode === "llm" ? "model-generated" : "rule-composed"}
        </span>
      </div>
      <div className="rounded-lg border border-[#e5d9c3] bg-[#fbf6ea] p-3">
        <p className="whitespace-pre-wrap text-[11.5px] leading-relaxed text-[#4f4838]">
          {details.candidate_answer || "No candidate answer was produced."}
        </p>
      </div>
      {details.note ? <p className="text-[10.5px] leading-relaxed text-muted">{details.note}</p> : null}
      {details.error ? (
        <p className="rounded border border-[#e5bcb5] bg-[#f8e9e6] px-2.5 py-2 text-[10.5px] text-[#8c2f2f]">
          Model path failed: {details.error}
        </p>
      ) : null}
      <div>
        <div className="eyebrow">Candidate atomic claims</div>
        <ul className="mt-2 space-y-2">
          {(details.claims || []).map((claim, index) => (
            <li key={claim.id} className="flex gap-2">
              <span className="mt-0.5 font-mono text-[9px] text-muted">c{index + 1}</span>
              <div>
                <p className="text-[11.5px] leading-relaxed">
                  <HighlightedText text={claim.text} />
                </p>
                <p className="mt-0.5 font-mono text-[8.5px] text-muted">
                  support · {claim.support_ids.join(", ") || "none"}
                </p>
              </div>
            </li>
          ))}
          {!details.claims?.length ? (
            <li className="text-[11px] text-muted">No claims were generated.</li>
          ) : null}
        </ul>
      </div>
      {details.assumptions?.length ? (
        <InfoList title="Assumptions" items={details.assumptions} />
      ) : null}
      {details.missing_information?.length ? (
        <InfoList title="Missing information" items={details.missing_information} />
      ) : null}
    </div>
  );
}

function CritiqueDetail({
  details,
  findings,
}: {
  details: CritiqueDetails;
  findings: CriticFinding[];
}) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[9.5px] text-muted">
        <span>semantic model attempted {details.semantic_llm_attempted ? "yes" : "no"}</span>
        <span>used {details.semantic_llm_used ? "yes" : "no"}</span>
        <span>{findings.length} finding(s)</span>
      </div>
      {details.note ? <p className="text-[10.5px] leading-relaxed text-muted">{details.note}</p> : null}
      {findings.length ? (
        <ul className="space-y-2">
          {findings.map((finding) => (
            <li key={finding.id} className="rounded-lg border border-line bg-surface p-3">
              <div className="flex flex-wrap items-center gap-1.5">
                <KindBadge kind={finding.kind} />
                <SeverityBadge severity={finding.severity} />
                <SourceBadge source={finding.source} />
                <span className="font-mono text-[8.5px] text-muted">{finding.id}</span>
              </div>
              <p className="mt-2 text-[11.5px] leading-relaxed">{finding.explanation}</p>
              <p className="mt-1 text-[10px] leading-relaxed text-muted">
                <span className="font-medium">Suggested action:</span> {finding.suggested_action}
              </p>
              {finding.passage_ids.length ? (
                <p className="mt-1 break-all font-mono text-[8.5px] text-muted">
                  passages · {finding.passage_ids.join(", ")}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="rounded-lg border border-dashed border-line bg-surface px-3 py-4 text-[11px] text-muted">
          The critic produced no findings. This is not a guarantee of correctness.
        </p>
      )}
    </div>
  );
}

function ResolutionDetail({ details }: { details: ResolutionDetails }) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge status={(details.status as QueryResult["status"]) || "insufficient_evidence"} />
        {details.rules?.map((rule) => (
          <span
            key={rule}
            className="rounded border border-line bg-surface px-1.5 py-0.5 font-mono text-[9px] text-muted"
          >
            {rule}
          </span>
        ))}
      </div>
      <p className="text-[11.5px] leading-relaxed text-muted">{details.reason}</p>
      {details.conflicts?.length ? (
        <ul className="space-y-1.5">
          {details.conflicts.map((conflict) => (
            <li
              key={conflict.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded border border-line bg-surface px-2.5 py-2 text-[10.5px]"
            >
              <span className="flex flex-wrap items-center gap-1.5">
                <KindBadge kind={conflict.kind} />
                <span>{conflict.resolution === "resolved" ? "Resolved" : "Unresolved"}</span>
              </span>
              <span className="text-muted">
                {conflict.preferred_document_title || "No preferred source"}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function ValidationDetail({ details }: { details: ValidationDetails }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "flex h-6 w-6 items-center justify-center rounded-full",
            details.valid ? "bg-[#e5efe8] text-[#2f5d50]" : "bg-[#f8e9e6] text-[#8c2f2f]",
          )}
        >
          {details.valid ? <IconCheck size={12} /> : <IconX size={12} />}
        </span>
        <span className="text-[11.5px] font-medium">
          {details.valid ? "All structural checks passed" : "One or more structural checks failed"}
        </span>
      </div>
      <ul className="space-y-1.5">
        {(details.checks || []).map((check) => (
          <li key={check.id} className="flex items-start gap-2">
            <span
              className={cn(
                "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full",
                check.passed ? "bg-[#e5efe8] text-[#2f5d50]" : "bg-[#f8e9e6] text-[#8c2f2f]",
              )}
            >
              {check.passed ? <IconCheck size={9} /> : <IconX size={9} />}
            </span>
            <div>
              <p className="text-[10.5px] font-medium">{check.name}</p>
              <p className="text-[9.5px] leading-relaxed text-muted">{check.detail}</p>
            </div>
          </li>
        ))}
      </ul>
      {details.removed_claims?.length ? (
        <div className="rounded border border-[#e5bcb5] bg-[#f8e9e6] px-2.5 py-2">
          <p className="text-[10px] font-medium text-[#8c2f2f]">Claims removed</p>
          {details.removed_claims.map((claim, index) => (
            <p key={index} className="mt-0.5 text-[10px] leading-relaxed text-[#7d4444]">
              {claim}
            </p>
          ))}
        </div>
      ) : null}
      <p className="border-t border-line pt-2 text-[9.5px] leading-relaxed text-muted">
        {details.semantic_caveat}
      </p>
    </div>
  );
}

function InfoList({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <div className="eyebrow">{title}</div>
      <ul className="mt-1 space-y-0.5">
        {items.map((item, index) => (
          <li key={index} className="text-[10.5px] leading-relaxed text-muted">
            — {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

function SmallMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-line bg-[#f7f4ec] px-3 py-2">
      <div className="font-mono text-[14px] leading-none">{value}</div>
      <div className="mt-1 text-[9px] uppercase tracking-[0.08em] text-muted">{label}</div>
    </div>
  );
}
