"use client";

import { useEffect, useRef, useState } from "react";
import {
  ApiError,
  askQuestion,
  getDocuments,
  getHealth,
  getScenarios,
  loadSampleCorpus,
} from "@/lib/api";
import type {
  CorpusStats,
  DemoScenario,
  DocumentSummary,
  Health,
  QueryResult,
} from "@/lib/types";
import { AnswerView } from "@/components/AnswerView";
import { ConflictView } from "@/components/ConflictView";
import { CorpusPanel } from "@/components/CorpusPanel";
import { QuestionComposer } from "@/components/QuestionComposer";
import { TraceView } from "@/components/TraceView";
import { UploadModal } from "@/components/UploadModal";
import {
  cn,
  IconAlert,
  IconCheck,
  IconFile,
  IconLoader,
  IconRefresh,
  IconScale,
  IconSearch,
  IconTrace,
  IconX,
  LogoMark,
} from "@/components/common";

type Tab = "answer" | "conflicts" | "trace";

const TAB_LABELS: Array<{ id: Tab; label: string }> = [
  { id: "answer", label: "Answer" },
  { id: "conflicts", label: "Conflict inspector" },
  { id: "trace", label: "Verification trace" },
];

export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [stats, setStats] = useState<CorpusStats | null>(null);
  const [scenarios, setScenarios] = useState<DemoScenario[]>([]);
  const [docsLoading, setDocsLoading] = useState(true);
  const [sampleBusy, setSampleBusy] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [corpusError, setCorpusError] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [asOf, setAsOf] = useState("");
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [queryError, setQueryError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("answer");
  const [toast, setToast] = useState<string | null>(null);
  const booted = useRef(false);
  const autoRan = useRef(false);
  const resultsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const now = new Date();
    setAsOf(
      new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10),
    );
  }, []);

  useEffect(() => {
    if (booted.current) return;
    booted.current = true;
    let cancelled = false;
    async function boot() {
      setDocsLoading(true);
      try {
        const [healthResponse, documentsResponse, scenariosResponse] = await Promise.all([
          getHealth(),
          getDocuments(),
          getScenarios(),
        ]);
        if (cancelled) return;
        setHealth(healthResponse);
        setScenarios(scenariosResponse.scenarios);
        if (documentsResponse.documents.length === 0) {
          setSampleBusy(true);
          const sample = await loadSampleCorpus();
          if (cancelled) return;
          setDocuments(sample.documents);
          setStats(sample.stats);
          setToast(`Loaded ${sample.loaded} fictional demonstration documents.`);
        } else {
          setDocuments(documentsResponse.documents);
          setStats(documentsResponse.stats);
        }
        setCorpusError(null);
      } catch (error) {
        if (cancelled) return;
        setCorpusError(
          error instanceof ApiError ? error.message : "Could not initialize the workspace.",
        );
      } finally {
        if (!cancelled) {
          setDocsLoading(false);
          setSampleBusy(false);
        }
      }
    }
    boot();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 5200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    if (!loading) return;
    const started = performance.now();
    setElapsed(0);
    const timer = window.setInterval(() => setElapsed(performance.now() - started), 100);
    return () => window.clearInterval(timer);
  }, [loading]);

  // Deep links make the demonstrations reproducible and screenshot-friendly:
  // /?scenario=expense-amendment&tab=conflicts
  useEffect(() => {
    if (autoRan.current || !scenarios.length || docsLoading) return;
    const params = new URLSearchParams(window.location.search);
    const scenarioId = params.get("scenario");
    if (!scenarioId) return;
    const scenario = scenarios.find((item) => item.id === scenarioId);
    if (!scenario) return;
    autoRan.current = true;
    void runQuery(scenario.question);
    // runQuery reads the current question/as-of state and only runs once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenarios, docsLoading]);

  async function refreshCorpus() {
    try {
      const response = await getDocuments();
      setDocuments(response.documents);
      setStats(response.stats);
    } catch (error) {
      setCorpusError(
        error instanceof ApiError ? error.message : "Could not refresh the corpus.",
      );
    }
  }

  async function runQuery(nextQuestion?: string) {
    const target = (nextQuestion ?? question).trim();
    if (target.length < 3 || loading) return;
    setQuestion(target);
    setLoading(true);
    setQueryError(null);
    setToast(null);
    try {
      const response = await askQuestion(target, asOf || undefined);
      setResult(response);
      const requestedTab = new URLSearchParams(window.location.search).get("tab");
      setTab(
        requestedTab === "conflicts" || requestedTab === "trace"
          ? requestedTab
          : "answer",
      );
      if (window.innerWidth < 1024) {
        window.setTimeout(() => {
          resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 80);
      }
    } catch (error) {
      setQueryError(
        error instanceof ApiError ? error.message : "The query could not be completed.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleLoadSample() {
    if (sampleBusy) return;
    setSampleBusy(true);
    setCorpusError(null);
    try {
      const sample = await loadSampleCorpus();
      setDocuments(sample.documents);
      setStats(sample.stats);
      setResult(null);
      setTab("answer");
      setToast(`Reloaded ${sample.loaded} fictional sample documents. Existing uploads were kept.`);
    } catch (error) {
      setCorpusError(
        error instanceof ApiError ? error.message : "Could not load the sample corpus.",
      );
    } finally {
      setSampleBusy(false);
    }
  }

  async function handleUploaded(message: string) {
    setUploadOpen(false);
    setToast(message);
    await refreshCorpus();
  }

  const conflictCount = result?.conflicts.length ?? 0;
  const unresolvedCount = result?.conflicts.filter((c) => c.resolution === "unresolved").length ?? 0;
  const modeLabel = health?.llm_configured ? "LLM-assisted" : "Deterministic demo";
  const modeNote = health?.mode_note.replace(/^(Deterministic demo mode|LLM-assisted mode)\s*[—-]\s*/, "") ?? "";

  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-[#f6f3eb]/90">
        <div className="mx-auto flex max-w-[1440px] items-center justify-between gap-4 px-5 py-3.5 sm:px-8">
          <div className="flex min-w-0 items-center gap-2.5">
            <LogoMark size={32} />
            <div className="min-w-0">
              <div className="flex items-baseline gap-2">
                <span className="font-display text-[21px] font-semibold leading-none tracking-tight">
                  TruthGuard
                </span>
                <span className="rounded border border-line bg-[#f1ede3] px-1.5 py-0.5 font-mono text-[8.5px] uppercase tracking-[0.1em] text-muted">
                  demo
                </span>
              </div>
              <p className="mt-0.5 hidden text-[10px] text-muted sm:block">
                Adversarial verification for document Q&amp;A
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2.5">
            <span className="hidden items-center gap-1.5 rounded-full border border-line bg-[#f8f5ed] px-2.5 py-1 text-[10px] text-muted sm:inline-flex">
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  health?.llm_configured ? "bg-[#2f5d50]" : "bg-[#a4611c]",
                )}
              />
              {health ? modeLabel : "Connecting…"}
            </span>
            <span className="rounded-full border border-[#ded3bd] bg-[#f5ead5] px-2.5 py-1 font-mono text-[8.5px] uppercase tracking-[0.1em] text-[#7c5a1c]">
              Fictional corpus
            </span>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1440px] px-5 pb-16 pt-8 sm:px-8 sm:pt-10">
        <section className="grid items-end gap-6 border-b border-line pb-8 lg:grid-cols-[1fr_auto]">
          <div className="max-w-3xl">
            <div className="eyebrow">Research workspace · provenance first</div>
            <h1 className="font-display mt-2 text-[37px] leading-[1.06] tracking-tight sm:text-[50px]">
              Answers that show their work —
              <br className="hidden sm:block" /> and their disagreements.
            </h1>
            <p className="mt-4 max-w-2xl text-[13.5px] leading-relaxed text-muted sm:text-[14.5px]">
              TruthGuard retrieves competing evidence, forces a separate adversarial critique, and
              resolves conflicts only when a precedence rule can be demonstrated. When precedence
              is unclear, it abstains instead of inventing a winner.
            </p>
          </div>
          <div className="hidden min-w-[330px] lg:block">
            <div className="rounded-xl border border-line bg-[#f8f5ed] px-4 py-3">
              <div className="eyebrow mb-2.5">Verification pipeline</div>
              <div className="flex items-center gap-1 text-[9.5px] text-muted">
                {["Retrieve", "Synthesize", "Critique", "Resolve", "Validate"].map((step, index) => (
                  <span key={step} className="flex items-center gap-1">
                    <span
                      className={cn(
                        "rounded border px-1.5 py-0.5 font-mono",
                        index === 3
                          ? "border-[#c9d8ce] bg-[#eaf1eb] text-[#2f5d50]"
                          : "border-line bg-surface",
                      )}
                    >
                      {step}
                    </span>
                    {index < 4 ? <span className="text-[#b6ae9e]">→</span> : null}
                  </span>
                ))}
              </div>
              <div className="mt-2.5 flex items-center justify-between border-t border-line pt-2 text-[9.5px] text-muted">
                <span>BM25 retrieval</span>
                <span>·</span>
                <span>rule-ordered resolution</span>
              </div>
            </div>
          </div>
        </section>

        <div className="mt-6 grid items-start gap-5 lg:grid-cols-[320px_minmax(0,1fr)] xl:grid-cols-[342px_minmax(0,1fr)]">
          <div className="order-2 lg:order-1 lg:sticky lg:top-5">
            <CorpusPanel
              documents={documents}
              stats={stats}
              loading={docsLoading}
              sampleBusy={sampleBusy}
              onLoadSample={handleLoadSample}
              onUpload={() => setUploadOpen(true)}
            />
            {corpusError ? (
              <div className="mt-3 rounded-xl border border-[#e5bcb5] bg-[#f8e9e6] p-3">
                <p className="flex items-start gap-1.5 text-[11px] leading-relaxed text-[#8c2f2f]">
                  <IconAlert size={13} className="mt-0.5 shrink-0" />
                  {corpusError}
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setCorpusError(null);
                    setDocsLoading(true);
                    refreshCorpus().finally(() => setDocsLoading(false));
                  }}
                  className="mt-2 inline-flex items-center gap-1 text-[10.5px] font-medium text-[#8c2f2f] underline underline-offset-2"
                >
                  <IconRefresh size={11} /> Retry
                </button>
              </div>
            ) : null}
          </div>

          <div className="order-1 min-w-0 space-y-4 lg:order-2">
            <div
              className={cn(
                "flex items-start gap-2 rounded-xl border px-3.5 py-2.5 text-[10.5px] leading-relaxed",
                health?.llm_configured
                  ? "border-[#c9d8ce] bg-[#edf3ef] text-[#3f5c50]"
                  : "border-[#e3d9c5] bg-[#f8f2e5] text-[#6b5328]",
              )}
            >
              <span
                className={cn(
                  "mt-1 h-1.5 w-1.5 shrink-0 rounded-full",
                  health?.llm_configured ? "bg-[#2f5d50]" : "bg-[#a4611c]",
                )}
              />
              <p>
                <span className="font-medium">
                  {health
                    ? health.llm_configured
                      ? `LLM-assisted mode · ${health.model}`
                      : "Deterministic demo mode"
                    : "Connecting to backend"}
                </span>
                {health ? ` — ${modeNote}` : " — checking model configuration and corpus."}
              </p>
            </div>

            <QuestionComposer
              question={question}
              setQuestion={setQuestion}
              asOf={asOf}
              setAsOf={setAsOf}
              loading={loading}
              healthNote={
                scenarios.length
                  ? "All sample documents are fictional. Scenario outcomes are computed live from the seeded corpus."
                  : undefined
              }
              scenarios={scenarios}
              onScenario={(scenario) => runQuery(scenario.question)}
              onSubmit={() => runQuery()}
            />

            {queryError ? (
              <div className="flex items-start gap-2.5 rounded-xl border border-[#e5bcb5] bg-[#f8e9e6] px-4 py-3">
                <IconAlert size={16} className="mt-0.5 shrink-0 text-[#8c2f2f]" />
                <div className="flex-1">
                  <p className="text-[12px] font-medium text-[#8c2f2f]">Query failed</p>
                  <p className="mt-0.5 text-[11px] leading-relaxed text-[#7d4444]">{queryError}</p>
                </div>
                <button
                  type="button"
                  onClick={() => setQueryError(null)}
                  className="rounded p-1 text-[#8c2f2f] hover:bg-[#f2d9d5]"
                  aria-label="Dismiss error"
                >
                  <IconX size={14} />
                </button>
              </div>
            ) : null}

            {loading ? <LoadingPanel elapsed={elapsed} /> : null}

            {!result && !loading ? (
              <StartPanel onScenario={(scenario) => runQuery(scenario.question)} scenarios={scenarios} />
            ) : null}

            {result && !loading ? (
              <div ref={resultsRef} className="rise space-y-3 scroll-mt-4">
                <div className="flex flex-wrap items-end justify-between gap-3 pt-1">
                  <div className="min-w-0">
                    <div className="eyebrow">Query result</div>
                    <p className="font-display mt-1 max-w-2xl text-[20px] leading-snug">
                      {result.question}
                    </p>
                  </div>
                  <p className="font-mono text-[9.5px] text-muted">
                    {result.claims.length} claims · {result.citations.length} citations ·{" "}
                    {result.conflicts.length} conflict{result.conflicts.length === 1 ? "" : "s"}
                  </p>
                </div>

                <div
                  role="tablist"
                  aria-label="Result views"
                  className="flex gap-1 overflow-x-auto border-b border-line pb-px"
                >
                  {TAB_LABELS.map((item) => {
                    const active = tab === item.id;
                    const count =
                      item.id === "conflicts"
                        ? conflictCount
                        : item.id === "trace"
                          ? result.pipeline_trace.length
                          : result.claims.length;
                    return (
                      <button
                        key={item.id}
                        type="button"
                        role="tab"
                        aria-selected={active}
                        aria-label={`${item.label} (${count})`}
                        onClick={() => setTab(item.id)}
                        className={cn(
                          "relative shrink-0 rounded-t-md px-3 py-2 text-[11.5px] font-medium transition-colors",
                          active
                            ? "text-ink after:absolute after:inset-x-2 after:-bottom-px after:h-[2px] after:bg-ink"
                            : "text-muted hover:bg-[#f0ece2] hover:text-ink",
                        )}
                      >
                        {item.label}
                        <span
                          className={cn(
                            "ml-1.5 rounded-full px-1.5 py-0.5 font-mono text-[8.5px]",
                            item.id === "conflicts" && unresolvedCount > 0
                              ? "bg-[#f8eddc] text-[#7c4710]"
                              : "bg-[#f0ece2] text-muted",
                          )}
                        >
                          {count}
                        </span>
                      </button>
                    );
                  })}
                </div>

                <div role="tabpanel">
                  {tab === "answer" ? (
                    <AnswerView
                      result={result}
                      onInspectConflicts={() => setTab("conflicts")}
                      onInspectTrace={() => setTab("trace")}
                    />
                  ) : null}
                  {tab === "conflicts" ? <ConflictView result={result} /> : null}
                  {tab === "trace" ? <TraceView result={result} /> : null}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </main>

      <footer className="border-t border-line bg-[#f1ede3]">
        <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-2 px-5 py-4 sm:px-8">
          <p className="text-[10px] text-muted">
            TruthGuard · citations prove provenance, not semantic truth. Unresolved conflicts are
            never reported as verified.
          </p>
          <p className="font-mono text-[8.5px] uppercase tracking-[0.1em] text-muted">
            BM25 · deterministic verification · FastAPI + Next.js
          </p>
        </div>
      </footer>

      <UploadModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUploaded={handleUploaded}
      />

      {toast ? (
        <div
          role="status"
          className="fixed bottom-5 left-1/2 z-40 flex max-w-[92vw] -translate-x-1/2 items-center gap-2 rounded-lg border border-[#b7cdbf] bg-[#f1f6f1] px-4 py-2.5 text-[11.5px] text-[#2f5d50] shadow-lifted"
        >
          <IconCheck size={14} />
          <span>{toast}</span>
          <button
            type="button"
            onClick={() => setToast(null)}
            className="ml-1 rounded p-0.5 hover:bg-[#dfeae1]"
            aria-label="Dismiss notification"
          >
            <IconX size={12} />
          </button>
        </div>
      ) : null}
    </div>
  );
}

function LoadingPanel({ elapsed }: { elapsed: number }) {
  return (
    <div className="card overflow-hidden">
      <div className="progress-track" />
      <div className="flex items-start gap-3 px-5 py-4">
        <IconLoader size={18} className="mt-0.5 shrink-0 text-[#3f5c50]" />
        <div>
          <p className="text-[12.5px] font-medium">
            Running the verification pipeline…{" "}
            <span className="font-mono text-[10.5px] text-muted">{(elapsed / 1000).toFixed(1)}s</span>
          </p>
          <p className="mt-0.5 text-[11px] leading-relaxed text-muted">
            Retrieval, synthesis, adversarial critique, rule-ordered resolution and evidence
            validation. Actual stage results appear when the query completes.
          </p>
        </div>
      </div>
    </div>
  );
}

function StartPanel({
  scenarios,
  onScenario,
}: {
  scenarios: DemoScenario[];
  onScenario: (scenario: DemoScenario) => void;
}) {
  return (
    <div className="card overflow-hidden">
      <div className="border-b border-line px-5 py-4 sm:px-6">
        <div className="eyebrow">Start here</div>
        <h2 className="font-display mt-1 text-[22px] leading-tight">
          Verify an answer, not just retrieve one
        </h2>
      </div>
      <div className="grid gap-0 sm:grid-cols-3 sm:divide-x sm:divide-line">
        <Step
          number="01"
          icon={<IconSearch size={15} />}
          title="Retrieve competing evidence"
          text="BM25 surfaces relevant passages from multiple documents, capped per source so a verbose document cannot crowd out the conflict."
        />
        <Step
          number="02"
          icon={<IconScale size={15} />}
          title="Challenge the candidate"
          text="A separate critic checks contradictions, staleness, supersession, scope, unsupported claims and missing evidence."
        />
        <Step
          number="03"
          icon={<IconTrace size={15} />}
          title="Resolve or abstain"
          text="A rule-ordered resolver applies scope, supersession, authority and effective dates, then revalidates citations."
        />
      </div>
      <div className="border-t border-line bg-[#f7f4ec] px-5 py-4 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-[11px] text-muted">
            {scenarios.length
              ? "Or run one of the three seeded demonstrations above."
              : "Load the sample corpus, choose a demonstration, and inspect the conflict inspector."}
          </p>
          {scenarios[0] ? (
            <button
              type="button"
              onClick={() => onScenario(scenarios[0])}
              className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-1.5 text-[11px] font-medium hover:bg-[#f1ede3]"
            >
              <IconFile size={13} /> Run scenario 01
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function Step({
  number,
  icon,
  title,
  text,
}: {
  number: string;
  icon: React.ReactNode;
  title: string;
  text: string;
}) {
  return (
    <div className="px-5 py-5 sm:px-5">
      <div className="flex items-center justify-between">
        <span className="flex h-7 w-7 items-center justify-center rounded-full border border-line bg-[#f5f1e8] text-[#4f5b52]">
          {icon}
        </span>
        <span className="font-mono text-[9px] text-muted">{number}</span>
      </div>
      <h3 className="mt-2.5 text-[12px] font-semibold">{title}</h3>
      <p className="mt-1 text-[10.5px] leading-relaxed text-muted">{text}</p>
    </div>
  );
}
