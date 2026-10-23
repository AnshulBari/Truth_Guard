"use client";

import type { DemoScenario } from "@/lib/types";
import { cn, IconArrow, IconLoader, IconSearch, StatusBadge } from "./common";

interface Props {
  question: string;
  setQuestion: (value: string) => void;
  asOf: string;
  setAsOf: (value: string) => void;
  loading: boolean;
  healthNote?: string;
  scenarios: DemoScenario[];
  onScenario: (scenario: DemoScenario) => void;
  onSubmit: () => void;
}

export function QuestionComposer({
  question,
  setQuestion,
  asOf,
  setAsOf,
  loading,
  healthNote,
  scenarios,
  onScenario,
  onSubmit,
}: Props) {
  return (
    <section className="card overflow-hidden">
      <div className="border-b border-line px-5 py-4 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="eyebrow">Query workspace</div>
            <h2 className="font-display mt-1 text-[25px] leading-tight sm:text-[28px]">
              Ask the corpus
            </h2>
          </div>
          <div className="flex items-end gap-2">
            <label className="block">
              <span className="eyebrow block pb-1">As-of date</span>
              <input
                type="date"
                value={asOf}
                onChange={(event) => setAsOf(event.target.value)}
                className="input w-[138px] py-1.5 text-[11.5px]"
                aria-label="Applicability date"
              />
            </label>
          </div>
        </div>
      </div>

      <div className="px-5 py-4 sm:px-6 sm:py-5">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (!loading && question.trim().length >= 3) onSubmit();
          }}
        >
          <div className="relative">
            <IconSearch size={17} className="pointer-events-none absolute left-3.5 top-3.5 text-muted" />
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                  event.preventDefault();
                  if (!loading && question.trim().length >= 3) onSubmit();
                }
              }}
              rows={3}
              placeholder="e.g. What is the current expense reimbursement limit for client entertainment in India?"
              className="w-full resize-none rounded-xl border border-line bg-[#fffdf8] py-3 pl-10 pr-3.5 text-[14px] leading-relaxed outline-none transition-colors placeholder:text-[#a49c8c] focus:border-[#8aa596] focus:ring-2 focus:ring-[#2f5d50]/10"
              aria-label="Question for the corpus"
            />
          </div>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <p className="text-[10.5px] text-muted">
              {asOf
                ? `Applicability is evaluated as of ${asOf}.`
                : "Defaults to today's date for effective-date checks."}
              <span className="mx-2 text-line">·</span>
              <span className="font-mono">⌘/Ctrl + Enter</span>
            </p>
            <button
              type="submit"
              disabled={loading || question.trim().length < 3}
              className="inline-flex items-center gap-2 rounded-lg bg-ink px-4 py-2.5 text-[12.5px] font-medium text-[#fbf9f2] transition-colors hover:bg-[#333027] disabled:cursor-not-allowed disabled:opacity-45"
            >
              {loading ? <IconLoader size={15} /> : <span className="h-1.5 w-1.5 rounded-full bg-[#9ec4b1]" />}
              {loading ? "Running verification…" : "Run verification"}
              {!loading ? <IconArrow size={14} /> : null}
            </button>
          </div>
        </form>

        <div className="mt-5 border-t border-line pt-4">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <div className="eyebrow">Demonstration scenarios</div>
            <p className="text-[10px] text-muted">
              Runs the real pipeline. Outcomes are not scripted.
            </p>
          </div>
          <div className="mt-2.5 grid gap-2 sm:grid-cols-3">
            {scenarios.map((scenario, index) => (
              <button
                key={scenario.id}
                type="button"
                disabled={loading}
                onClick={() => onScenario(scenario)}
                title={scenario.expected_outcome}
                className={cn(
                  "group rounded-lg border border-line bg-[#faf8f2] px-3 py-2.5 text-left transition-all",
                  "hover:-translate-y-0.5 hover:border-[#bdb4a1] hover:bg-[#f6f2e8] hover:shadow-sm",
                  "disabled:cursor-not-allowed disabled:opacity-60",
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[9.5px] text-muted">0{index + 1}</span>
                  <StatusBadge status={scenario.expected_status} size="sm" />
                </div>
                <div className="mt-1.5 line-clamp-2 text-[11.5px] font-medium leading-snug text-ink">
                  {scenario.label}
                </div>
                <div className="mt-1 text-[10px] text-muted">{scenario.hint}</div>
              </button>
            ))}
          </div>
          {healthNote ? (
            <p className="mt-3 text-[10px] leading-relaxed text-muted">{healthNote}</p>
          ) : null}
        </div>
      </div>
    </section>
  );
}
