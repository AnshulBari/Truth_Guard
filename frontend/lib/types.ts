export type ResolutionStatus =
  | "resolved"
  | "conflict_unresolved"
  | "insufficient_evidence"
  | "no_relevant_evidence";

export type Severity = "info" | "low" | "medium" | "high";
export type FindingKind =
  | "contradiction"
  | "staleness"
  | "supersession"
  | "unsupported_claim"
  | "scope_mismatch"
  | "evidence_gap"
  | "citation_error";
export type DocType =
  | "policy"
  | "amendment"
  | "handbook"
  | "faq"
  | "sop"
  | "guideline"
  | "standard"
  | "circular"
  | "document";
export type StageStatus = "completed" | "fallback" | "skipped" | "failed";

export interface DocumentRef {
  document_id: string;
  title: string;
  version: string;
}

export interface DocumentSummary {
  id: string;
  title: string;
  doc_type: DocType;
  version: string;
  published_date: string | null;
  effective_date: string | null;
  supersedes: string[];
  authority_rank: number | null;
  authority_label: string | null;
  scope: string | null;
  source_filename: string | null;
  is_sample: boolean;
  page_count: number;
  passage_count: number;
  created_at: string;
  superseded_by: DocumentRef[];
  missing_metadata: string[];
}

export interface CorpusStats {
  documents: number;
  passages: number;
  sample_documents: number;
  uploaded_documents: number;
  supersession_links: number;
}

export interface DocumentsResponse {
  documents: DocumentSummary[];
  stats: CorpusStats;
}

export interface DemoScenario {
  id: string;
  label: string;
  question: string;
  hint: string;
  expected_status: ResolutionStatus;
  expected_outcome: string;
}

export interface ScenariosResponse {
  scenarios: DemoScenario[];
  corpus_note: string;
}

export interface Health {
  status: string;
  mode: "deterministic" | "llm_assisted";
  mode_note: string;
  llm_configured: boolean;
  model: string;
  provider: string;
  document_count: number;
  version: string;
}

export interface PassageHit {
  passage_id: string;
  document_id: string;
  title: string;
  doc_type: DocType;
  version: string;
  page: number;
  published_date: string | null;
  effective_date: string | null;
  authority_rank: number | null;
  authority_label: string | null;
  scope: string | null;
  text: string;
  score: number;
  rank: number;
}

export interface Claim {
  id: string;
  text: string;
  support_ids: string[];
  supported: boolean;
  note: string | null;
}

export interface ConflictStatement {
  passage_id: string;
  document_id: string;
  title: string;
  doc_type: DocType;
  version: string;
  published_date: string | null;
  effective_date: string | null;
  authority_label: string | null;
  page: number;
  statement: string;
}

export interface CriticFinding {
  id: string;
  kind: FindingKind;
  severity: Severity;
  passage_ids: string[];
  statements: ConflictStatement[];
  explanation: string;
  suggested_action: string;
  source: "deterministic" | "llm";
}

export interface Conflict extends CriticFinding {
  resolution: "resolved" | "unresolved";
  preferred_document_id: string | null;
  preferred_document_title: string | null;
  resolution_note: string;
  superseding_document_id: string | null;
  superseding_document_title: string | null;
  superseded_document_id: string | null;
  superseded_document_title: string | null;
}

export interface Citation {
  passage_id: string;
  document_id: string;
  title: string;
  doc_type: DocType;
  version: string;
  page: number;
  published_date: string | null;
  effective_date: string | null;
  authority_label: string | null;
  excerpt: string;
}

export interface ValidationCheck {
  id: string;
  name: string;
  passed: boolean;
  detail: string;
}

export interface ValidationReport {
  valid: boolean;
  checks: ValidationCheck[];
  notes: string[];
  removed_claims: string[];
  semantic_caveat: string;
}

export interface PipelineStage {
  id: string;
  name: string;
  status: StageStatus;
  summary: string;
  duration_ms: number;
  details: Record<string, unknown>;
}

export interface QueryResult {
  query_id: string;
  question: string;
  as_of: string;
  mode: "deterministic" | "llm_assisted";
  mode_note: string;
  answer: string;
  status: ResolutionStatus;
  claims: Claim[];
  citations: Citation[];
  conflicts: Conflict[];
  critic_findings: CriticFinding[];
  resolution_reason: string;
  resolution_rules: string[];
  validation: ValidationReport;
  pipeline_trace: PipelineStage[];
  retrieved_passages: PassageHit[];
  created_at: string;
}

export interface SampleLoadResponse {
  message: string;
  loaded: number;
  documents: DocumentSummary[];
  stats: CorpusStats;
}

export type DocumentDetail = DocumentSummary & {
  passages: {
    id: string;
    document_id: string;
    page: number;
    ordinal: number;
    text: string;
  }[];
};
