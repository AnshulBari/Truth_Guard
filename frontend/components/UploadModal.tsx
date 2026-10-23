"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, uploadDocument } from "@/lib/api";
import { cn, IconLoader, IconUpload, IconX } from "./common";

interface Props {
  open: boolean;
  onClose: () => void;
  onUploaded: (message: string) => void;
}

const DOC_TYPES = [
  ["", "Auto-detect from filename"],
  ["policy", "Policy"],
  ["amendment", "Amendment"],
  ["circular", "Circular"],
  ["handbook", "Handbook"],
  ["faq", "FAQ"],
  ["sop", "SOP"],
  ["guideline", "Guideline"],
  ["standard", "Standard"],
  ["document", "Other document"],
] as const;

export function UploadModal({ open, onClose, onUploaded }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [docType, setDocType] = useState("");
  const [version, setVersion] = useState("");
  const [publishedDate, setPublishedDate] = useState("");
  const [effectiveDate, setEffectiveDate] = useState("");
  const [scope, setScope] = useState("");
  const [authorityRank, setAuthorityRank] = useState("");
  const [authorityLabel, setAuthorityLabel] = useState("");
  const [supersedes, setSupersedes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const firstFieldRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) onClose();
    };
    document.addEventListener("keydown", onKey);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    firstFieldRef.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, busy, onClose]);

  if (!open) return null;

  const reset = () => {
    setFile(null);
    setTitle("");
    setDocType("");
    setVersion("");
    setPublishedDate("");
    setEffectiveDate("");
    setScope("");
    setAuthorityRank("");
    setAuthorityLabel("");
    setSupersedes("");
    setError(null);
    setBusy(false);
  };

  const close = () => {
    if (busy) return;
    reset();
    onClose();
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!file) {
      setError("Choose a PDF, TXT or Markdown file first.");
      return;
    }
    setError(null);
    setBusy(true);
    const form = new FormData();
    form.append("file", file);
    if (title.trim()) form.append("title", title.trim());
    if (docType) form.append("doc_type", docType);
    if (version.trim()) form.append("version", version.trim());
    if (publishedDate) form.append("published_date", publishedDate);
    if (effectiveDate) form.append("effective_date", effectiveDate);
    if (scope.trim()) form.append("scope", scope.trim());
    if (authorityRank.trim()) form.append("authority_rank", authorityRank.trim());
    if (authorityLabel.trim()) form.append("authority_label", authorityLabel.trim());
    if (supersedes.trim()) form.append("supersedes", supersedes.trim());
    try {
      const result = await uploadDocument(form);
      const message = result.message;
      reset();
      onUploaded(message);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed. Try again.");
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-[#1c1a16]/45 px-4 py-[6vh]"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) close();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="upload-title"
        className="rise w-full max-w-[600px] rounded-2xl border border-line bg-surface shadow-lifted"
      >
        <div className="flex items-start justify-between border-b border-line px-6 py-5">
          <div>
            <div className="eyebrow">Add to corpus</div>
            <h2 id="upload-title" className="font-display mt-1 text-[25px] leading-tight">
              Upload a document
            </h2>
            <p className="mt-1 text-[12px] text-muted">
              PDF, TXT or Markdown. Metadata is indexed with the passages.
            </p>
          </div>
          <button
            ref={firstFieldRef}
            type="button"
            onClick={close}
            className="rounded-md border border-line p-1.5 text-muted hover:bg-[#f1eee5] hover:text-ink"
            aria-label="Close upload dialog"
          >
            <IconX size={16} />
          </button>
        </div>

        <form onSubmit={submit} className="space-y-4 px-6 py-5">
          <div>
            <div className="eyebrow mb-1.5">Source file</div>
            <label
              htmlFor="file-input"
              className={cn(
                "flex cursor-pointer items-center gap-3 rounded-xl border border-dashed px-4 py-4 transition-colors",
                file
                  ? "border-[#9fbaa9] bg-[#eef3ee]"
                  : "border-[#cfc7b6] bg-[#f8f5ed] hover:border-[#b3a992]",
              )}
            >
              <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-surface">
                <IconUpload size={17} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-medium">
                  {file ? file.name : "Choose a file"}
                </span>
                <span className="block text-[11px] text-muted">
                  {file
                    ? `${(file.size / 1024).toFixed(0)} KB · ${file.name.split(".").pop()?.toUpperCase()}`
                    : "Up to 20 MB · PDF, TXT or MD"}
                </span>
              </span>
              <input
                ref={inputRef}
                id="file-input"
                type="file"
                accept=".pdf,.txt,.md,.markdown,application/pdf,text/plain,text/markdown"
                className="sr-only"
                onChange={(event) => setFile(event.target.files?.[0] || null)}
              />
            </label>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field label="Title" hint="Optional; inferred from filename">
              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="e.g. Travel Policy 2026"
                className="input"
              />
            </Field>
            <Field label="Document type">
              <select value={docType} onChange={(event) => setDocType(event.target.value)} className="input">
                {DOC_TYPES.map(([value, label]) => (
                  <option key={value || "auto"} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Version">
              <input
                value={version}
                onChange={(event) => setVersion(event.target.value)}
                placeholder="1.0"
                className="input"
              />
            </Field>
            <Field label="Scope" hint="Employees, region, conditions">
              <input
                value={scope}
                onChange={(event) => setScope(event.target.value)}
                placeholder="All employees in India"
                className="input"
              />
            </Field>
            <Field label="Published date">
              <input
                type="date"
                value={publishedDate}
                onChange={(event) => setPublishedDate(event.target.value)}
                className="input"
              />
            </Field>
            <Field label="Effective date">
              <input
                type="date"
                value={effectiveDate}
                onChange={(event) => setEffectiveDate(event.target.value)}
                className="input"
              />
            </Field>
          </div>

          <details className="rounded-lg border border-line bg-[#f7f4ec] px-3 py-2.5">
            <summary className="cursor-pointer text-[12px] font-medium text-ink">
              Authority and supersession metadata
            </summary>
            <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Authority label">
                <input
                  value={authorityLabel}
                  onChange={(event) => setAuthorityLabel(event.target.value)}
                  placeholder="Standing policy"
                  className="input"
                />
              </Field>
              <Field label="Authority rank" hint="0–100; used only when decisive">
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={authorityRank}
                  onChange={(event) => setAuthorityRank(event.target.value)}
                  placeholder="e.g. 70"
                  className="input"
                />
              </Field>
              <div className="sm:col-span-2">
                <Field label="Supersedes" hint="Comma-separated document titles or IDs">
                  <input
                    value={supersedes}
                    onChange={(event) => setSupersedes(event.target.value)}
                    placeholder="Travel Policy"
                    className="input"
                  />
                </Field>
              </div>
            </div>
          </details>

          <p className="rounded-lg border border-[#e3d9c5] bg-[#f8f2e5] px-3 py-2 text-[11px] leading-relaxed text-[#6b5328]">
            Effective dates, scope and explicit supersession drive resolution. Missing values are
            reported as missing and are never inferred.
          </p>

          {error ? (
            <p role="alert" className="rounded-lg border border-[#e5bcb5] bg-[#f8e9e6] px-3 py-2 text-[12px] text-[#8c2f2f]">
              {error}
            </p>
          ) : null}

          <div className="flex items-center justify-end gap-2 border-t border-line pt-4">
            <button
              type="button"
              onClick={close}
              disabled={busy}
              className="rounded-lg border border-line px-4 py-2 text-[12px] font-medium hover:bg-[#f1eee5] disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={busy}
              className="inline-flex items-center gap-2 rounded-lg bg-ink px-4 py-2 text-[12px] font-medium text-[#fbf9f2] hover:bg-[#333027] disabled:opacity-60"
            >
              {busy ? <IconLoader size={14} /> : <IconUpload size={14} />}
              {busy ? "Indexing…" : "Upload and index"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="flex items-baseline justify-between gap-2">
        <span className="text-[11px] font-medium text-ink">{label}</span>
        {hint ? <span className="text-[9.5px] text-muted">{hint}</span> : null}
      </span>
      <span className="mt-1 block">{children}</span>
    </label>
  );
}
