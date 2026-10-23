"use client";

import { useState } from "react";
import type { CorpusStats, DocumentSummary } from "@/lib/types";
import {
  cn,
  DocTypeBadge,
  formatDate,
  IconBook,
  IconChevron,
  IconRefresh,
  IconUpload,
} from "./common";

interface Props {
  documents: DocumentSummary[];
  stats: CorpusStats | null;
  loading: boolean;
  sampleBusy: boolean;
  onLoadSample: () => void;
  onUpload: () => void;
}

export function CorpusPanel({
  documents,
  stats,
  loading,
  sampleBusy,
  onLoadSample,
  onUpload,
}: Props) {
  return (
    <aside className="card overflow-hidden">
      <div className="flex items-start justify-between gap-3 border-b border-line px-4 py-4">
        <div>
          <div className="eyebrow">Evidence base</div>
          <h2 className="font-display mt-1 text-[22px] leading-none">Corpus</h2>
        </div>
        <span className="rounded-full border border-line bg-[#f2efe6] px-2 py-0.5 font-mono text-[10px] text-muted">
          {documents.length} docs
        </span>
      </div>

      <div className="grid grid-cols-3 divide-x divide-line border-b border-line bg-[#f7f4ec]">
        <Stat label="Documents" value={stats?.documents ?? documents.length} />
        <Stat label="Passages" value={stats?.passages ?? 0} />
        <Stat label="Supersessions" value={stats?.supersession_links ?? 0} />
      </div>

      <div className="flex gap-2 px-4 py-3">
        <button
          type="button"
          onClick={onUpload}
          className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-ink px-3 py-2 text-[12px] font-medium text-[#fbf9f2] transition-colors hover:bg-[#333027]"
        >
          <IconUpload size={14} />
          Upload
        </button>
        <button
          type="button"
          onClick={onLoadSample}
          disabled={sampleBusy}
          className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-2 text-[12px] font-medium text-ink transition-colors hover:bg-[#f3f0e8] disabled:opacity-60"
        >
          <IconRefresh size={14} className={sampleBusy ? "animate-spin" : ""} />
          {sampleBusy ? "Loading…" : "Sample corpus"}
        </button>
      </div>

      <div className="max-h-[520px] overflow-y-auto scroll-thin border-t border-line">
        {loading ? (
          <div className="space-y-3 px-4 py-5" aria-label="Loading corpus">
            {[0, 1, 2, 3].map((item) => (
              <div key={item} className="animate-pulse space-y-2">
                <div className="h-3 w-3/4 rounded bg-[#e7e2d5]" />
                <div className="h-2.5 w-2/5 rounded bg-[#ede8dc]" />
              </div>
            ))}
          </div>
        ) : documents.length === 0 ? (
          <div className="px-5 py-8 text-center">
            <IconBook size={22} className="mx-auto text-muted" />
            <p className="mt-3 text-[13px] font-medium">The corpus is empty</p>
            <p className="mt-1 text-[12px] leading-relaxed text-muted">
              Load the fictional sample corpus or upload a policy document to begin.
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-line/80">
            {documents.map((document) => (
              <DocumentRow key={document.id} document={document} documents={documents} />
            ))}
          </ul>
        )}
      </div>

      <div className="border-t border-line bg-[#f7f4ec] px-4 py-3">
        <p className="text-[11px] leading-relaxed text-muted">
          <span className="font-medium text-ink">Fictional demo corpus.</span> Sample policies,
          amendments and FAQs are invented. Metadata such as effective dates and authority rank
          drives resolution; missing metadata is shown as missing.
        </p>
      </div>
    </aside>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="px-3 py-2.5 text-center">
      <div className="font-mono text-[15px] leading-none text-ink">{value}</div>
      <div className="mt-1 text-[9.5px] uppercase tracking-[0.08em] text-muted">{label}</div>
    </div>
  );
}

function DocumentRow({
  document,
  documents,
}: {
  document: DocumentSummary;
  documents: DocumentSummary[];
}) {
  const [open, setOpen] = useState(false);
  const supersedesTitles = document.supersedes.map((ref) => resolveRef(ref, documents));
  const missing = document.missing_metadata;

  return (
    <li className={cn("transition-colors", open ? "bg-[#f8f5ed]" : "hover:bg-[#f8f6f0]")}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-start gap-2.5 px-4 py-3 text-left"
        aria-expanded={open}
      >
        <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded border border-line bg-[#f1ede3]">
          <IconBook size={12} className="text-[#5f5a4e]" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <p className="text-[12.5px] font-medium leading-snug text-ink">{document.title}</p>
            <IconChevron
              size={14}
              className={cn(
                "mt-0.5 shrink-0 text-muted transition-transform",
                open && "rotate-180",
              )}
            />
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-1">
            <DocTypeBadge type={document.doc_type} />
            <span className="font-mono text-[10px] text-muted">v{document.version}</span>
            <span className="text-[10px] text-muted">
              {document.effective_date
                ? `eff. ${formatDate(document.effective_date)}`
                : document.published_date
                  ? `pub. ${formatDate(document.published_date)}`
                  : "no date"}
            </span>
          </div>
          {document.superseded_by.length > 0 ? (
            <p className="mt-1 text-[10px] text-[#7c4710]">
              Superseded by {document.superseded_by.map((ref) => ref.title).join(", ")}
            </p>
          ) : null}
        </div>
      </button>

      {open ? (
        <div className="space-y-3 px-4 pb-4 pl-[46px]">
          <div className="grid grid-cols-2 gap-x-3 gap-y-2 rounded-lg border border-line bg-surface px-3 py-2.5">
            <Meta label="Published" value={formatDate(document.published_date)} />
            <Meta label="Effective" value={formatDate(document.effective_date)} />
            <Meta label="Authority" value={document.authority_label || "Not recorded"} />
            <Meta
              label="Rank"
              value={document.authority_rank !== null ? String(document.authority_rank) : "—"}
            />
            <Meta label="Pages" value={String(document.page_count)} />
            <Meta label="Passages" value={String(document.passage_count)} />
          </div>
          <div>
            <div className="eyebrow">Scope</div>
            <p className="mt-1 text-[11.5px] leading-relaxed text-ink">
              {document.scope || "Scope not recorded"}
            </p>
          </div>
          <div>
            <div className="eyebrow">Supersedes</div>
            <p className="mt-1 text-[11.5px] leading-relaxed text-ink">
              {supersedesTitles.length ? supersedesTitles.join(", ") : "None declared"}
            </p>
          </div>
          {document.superseded_by.length ? (
            <div>
              <div className="eyebrow">Superseded by</div>
              <p className="mt-1 text-[11.5px] leading-relaxed text-ink">
                {document.superseded_by.map((ref) => `${ref.title} v${ref.version}`).join(", ")}
              </p>
            </div>
          ) : null}
          {missing.length ? (
            <div>
              <div className="eyebrow">Missing metadata</div>
              <div className="mt-1 flex flex-wrap gap-1">
                {missing.map((field) => (
                  <span
                    key={field}
                    className="rounded border border-[#e0d3b9] bg-[#f6edda] px-1.5 py-0.5 font-mono text-[9.5px] text-[#7c5a1c]"
                  >
                    {field}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
          {document.source_filename ? (
            <p className="break-all font-mono text-[9.5px] text-muted">{document.source_filename}</p>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[9px] uppercase tracking-[0.08em] text-muted">{label}</div>
      <div className="mt-0.5 text-[11px] text-ink">{value}</div>
    </div>
  );
}

function resolveRef(ref: string, documents: DocumentSummary[]): string {
  const found = documents.find(
    (document) =>
      document.id.toLowerCase() === ref.toLowerCase() ||
      document.title.toLowerCase() === ref.toLowerCase(),
  );
  return found ? `${found.title} v${found.version}` : ref;
}
