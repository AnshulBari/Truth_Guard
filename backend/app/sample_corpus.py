"""Built-in fictional corpus. Every document below is invented for the demo.

The corpus deliberately contains:
* an explicit, effective amendment (resolvable conflict)
* a newer informational FAQ with no authority (questionable source)
* two applicable documents with no precedence relationship (unresolvable)
* supersession links, scope differences and missing metadata.
"""

from __future__ import annotations

from datetime import date, datetime

from .db import Database
from .schemas import DemoScenario, SourceDocument, StoredPassage


def _passage(doc_id: str, suffix: str, page: int, ordinal: int, text: str) -> StoredPassage:
    return StoredPassage(
        id=f"{doc_id}-p{ordinal}",
        document_id=doc_id,
        page=page,
        ordinal=ordinal,
        text=text,
    )


SAMPLE_CREATED_AT = datetime(2026, 1, 1, 9, 0, 0)

SAMPLE_DOCUMENTS: list[tuple[SourceDocument, list[StoredPassage]]] = [
    (
        SourceDocument(
            id="doc-expense-policy",
            title="Finance & Expense Policy",
            doc_type="policy",
            version="2.2",
            published_date=date(2024, 1, 1),
            effective_date=date(2024, 1, 1),
            supersedes=[],
            authority_rank=70,
            authority_label="Standing finance policy",
            scope="All employees and contractors in India",
            source_filename="finance-expense-policy-v2.2.md",
            is_sample=True,
            page_count=2,
            created_at=SAMPLE_CREATED_AT,
        ),
        [
            _passage(
                "doc-expense-policy",
                "scope",
                1,
                1,
                "Policy scope. This Finance and Expense Policy applies to all employees and "
                "contractors in India. It sets out reimbursement, approval and documentation "
                "requirements for business expenses.",
            ),
            _passage(
                "doc-expense-policy",
                "limit",
                2,
                2,
                "Section 4.2 — Expense reimbursement limits. The expense reimbursement limit is "
                "₹5,000 per employee per calendar year for client entertainment. Receipts are "
                "required for claims above ₹500.",
            ),
            _passage(
                "doc-expense-policy",
                "approval",
                2,
                3,
                "Section 4.4 — Approval. Expense claims above the reimbursement limit require "
                "written approval from a department head. Claims without receipts are rejected.",
            ),
        ],
    ),
    (
        SourceDocument(
            id="doc-finance-circular-2025-07",
            title="Finance Circular 2025-07: Expense Limit Amendment",
            doc_type="amendment",
            version="2025-07",
            published_date=date(2025, 3, 20),
            effective_date=date(2025, 4, 1),
            supersedes=["doc-expense-policy"],
            authority_rank=90,
            authority_label="Approved finance amendment",
            scope="All employees and contractors in India",
            source_filename="finance-circular-2025-07.md",
            is_sample=True,
            page_count=1,
            created_at=SAMPLE_CREATED_AT,
        ),
        [
            _passage(
                "doc-finance-circular-2025-07",
                "purpose",
                1,
                1,
                "Purpose. This circular amends Section 4.2 of the Finance & Expense Policy "
                "(version 2.2) for employees and contractors in India. It is effective 1 April "
                "2025 and fully supersedes the earlier expense reimbursement limit in that policy.",
            ),
            _passage(
                "doc-finance-circular-2025-07",
                "amended",
                1,
                2,
                "Section 4.2 (amended). The expense reimbursement limit is increased to ₹8,000 "
                "per employee per calendar year for client entertainment. All other sections of "
                "the Finance & Expense Policy remain in force.",
            ),
            _passage(
                "doc-finance-circular-2025-07",
                "approval",
                1,
                3,
                "Approval. The Chief Financial Officer approved this circular on 12 March 2025. "
                "Questions should be directed to the finance controller.",
            ),
        ],
    ),
    (
        SourceDocument(
            id="doc-employee-handbook-2023",
            title="Employee Handbook 2023",
            doc_type="handbook",
            version="2023.1",
            published_date=date(2023, 1, 15),
            effective_date=date(2023, 1, 15),
            supersedes=[],
            authority_rank=60,
            authority_label="HR handbook",
            scope="All full-time employees in India",
            source_filename="employee-handbook-2023.md",
            is_sample=True,
            page_count=3,
            created_at=SAMPLE_CREATED_AT,
        ),
        [
            _passage(
                "doc-employee-handbook-2023",
                "leave",
                7,
                1,
                "Section 7.1 — Annual leave. Full-time employees are entitled to 12 days of paid "
                "annual leave per calendar year. Leave accrues at one day per month.",
            ),
            _passage(
                "doc-employee-handbook-2023",
                "carry-forward",
                8,
                2,
                "Section 7.2 — Carry-forward. Up to 5 days of unused annual leave may be carried "
                "forward into the next calendar year.",
            ),
            _passage(
                "doc-employee-handbook-2023",
                "sick-leave",
                8,
                3,
                "Section 7.3 — Sick leave. Full-time employees receive 10 days of paid sick leave "
                "per calendar year.",
            ),
        ],
    ),
    (
        SourceDocument(
            id="doc-leave-faq-2026",
            title="People Ops FAQ: Annual Leave",
            doc_type="faq",
            version="2026.02",
            published_date=date(2026, 2, 10),
            effective_date=None,
            supersedes=[],
            authority_rank=None,
            authority_label="Informational FAQ",
            scope="Full-time employees in India",
            source_filename="people-ops-leave-faq-2026.md",
            is_sample=True,
            page_count=1,
            created_at=SAMPLE_CREATED_AT,
        ),
        [
            _passage(
                "doc-leave-faq-2026",
                "entitlement",
                1,
                1,
                "Q: How many days of annual leave do full-time employees receive? A: Full-time "
                "employees now receive 18 days of paid annual leave per calendar year.",
            ),
            _passage(
                "doc-leave-faq-2026",
                "contractors",
                1,
                2,
                "Q: Does the 18-day entitlement apply to contractors? A: No. Contractors are not "
                "eligible for paid annual leave under this FAQ.",
            ),
            _passage(
                "doc-leave-faq-2026",
                "status",
                1,
                3,
                "Q: Is this FAQ a policy document? A: This FAQ summarises People Ops guidance. "
                "It does not amend the Employee Handbook and has not been approved as a policy "
                "change.",
            ),
        ],
    ),
    (
        SourceDocument(
            id="doc-procurement-sop",
            title="Procurement SOP",
            doc_type="sop",
            version="4.0",
            published_date=date(2025, 6, 1),
            effective_date=date(2025, 6, 1),
            supersedes=[],
            authority_rank=70,
            authority_label="Operating procedure",
            scope="All employees and contractors in India",
            source_filename="procurement-sop-v4.md",
            is_sample=True,
            page_count=2,
            created_at=SAMPLE_CREATED_AT,
        ),
        [
            _passage(
                "doc-procurement-sop",
                "contractors",
                3,
                1,
                "Section 3.1 — Contractor purchases. Contractor purchases above ₹50,000 require "
                "written approval from the Chief Financial Officer before the purchase order is "
                "issued.",
            ),
            _passage(
                "doc-procurement-sop",
                "vendors",
                3,
                2,
                "Section 3.2 — Vendor onboarding. All new vendors must complete a compliance "
                "screening before their first purchase order. Compliance screening takes up to "
                "10 business days.",
            ),
            _passage(
                "doc-procurement-sop",
                "orders",
                4,
                3,
                "Section 3.3 — Purchase orders. Every purchase order must reference an approved "
                "budget line and a named budget owner.",
            ),
        ],
    ),
    (
        SourceDocument(
            id="doc-contractor-guidelines",
            title="Contractor Engagement Guidelines",
            doc_type="guideline",
            version="2025 rev 2",
            published_date=date(2025, 8, 10),
            effective_date=date(2025, 9, 1),
            supersedes=[],
            authority_rank=60,
            authority_label="Functional guidance",
            scope="All employees and contractors in India",
            source_filename="contractor-engagement-guidelines-2025.md",
            is_sample=True,
            page_count=2,
            created_at=SAMPLE_CREATED_AT,
        ),
        [
            _passage(
                "doc-contractor-guidelines",
                "threshold",
                5,
                1,
                "Section 5.2 — Approval thresholds. Contractor purchases above ₹1,00,000 require "
                "written approval from the Chief Operating Officer before the engagement begins.",
            ),
            _passage(
                "doc-contractor-guidelines",
                "sow",
                5,
                2,
                "Section 5.3 — Statement of work. Every contractor engagement must have a signed "
                "statement of work before work starts.",
            ),
            _passage(
                "doc-contractor-guidelines",
                "tenure",
                6,
                3,
                "Section 5.4 — Tenure. Contractor engagements longer than 12 months require an "
                "annual business review.",
            ),
        ],
    ),
    (
        SourceDocument(
            id="doc-it-security-standard",
            title="IT Security Standard",
            doc_type="standard",
            version="3.1",
            published_date=date(2025, 2, 1),
            effective_date=date(2025, 2, 1),
            supersedes=[],
            authority_rank=80,
            authority_label="Mandatory security standard",
            scope="All employees and contractors",
            source_filename="it-security-standard-v3.1.md",
            is_sample=True,
            page_count=2,
            created_at=SAMPLE_CREATED_AT,
        ),
        [
            _passage(
                "doc-it-security-standard",
                "passwords",
                2,
                1,
                "Section 2.1 — Passwords. All workforce accounts must rotate their password every "
                "90 days and must use a password manager.",
            ),
            _passage(
                "doc-it-security-standard",
                "mfa",
                2,
                2,
                "Section 2.2 — Multi-factor authentication. Multi-factor authentication is "
                "mandatory for all remote access and for administrative consoles.",
            ),
            _passage(
                "doc-it-security-standard",
                "incidents",
                3,
                3,
                "Section 2.3 — Incident reporting. Suspected security incidents must be reported "
                "to the security team within 24 hours of discovery.",
            ),
        ],
    ),
    (
        SourceDocument(
            id="doc-remote-work-policy",
            title="Remote Work Policy",
            doc_type="policy",
            version="1.4",
            published_date=date(2025, 1, 1),
            effective_date=date(2025, 1, 1),
            supersedes=[],
            authority_rank=70,
            authority_label="Standing policy",
            scope="Full-time employees in India",
            source_filename="remote-work-policy-v1.4.md",
            is_sample=True,
            page_count=1,
            created_at=SAMPLE_CREATED_AT,
        ),
        [
            _passage(
                "doc-remote-work-policy",
                "eligibility",
                1,
                1,
                "Section 1.2 — Eligibility. Full-time employees in India may work remotely up to "
                "3 days per week with manager approval. Contractors are not eligible for remote "
                "work under this policy.",
            ),
            _passage(
                "doc-remote-work-policy",
                "core-hours",
                1,
                2,
                "Section 1.3 — Core hours. Remote employees must be available online during core "
                "hours of 10:00 to 16:00 India Standard Time.",
            ),
            _passage(
                "doc-remote-work-policy",
                "equipment",
                1,
                3,
                "Section 1.4 — Equipment. Remote employees receive a one-time home office "
                "allowance of ₹10,000.",
            ),
        ],
    ),
    (
        SourceDocument(
            id="doc-remote-work-faq",
            title="Remote Work FAQ",
            doc_type="faq",
            version="2024.11",
            published_date=date(2024, 11, 5),
            effective_date=None,
            supersedes=[],
            authority_rank=None,
            authority_label="Informational FAQ",
            scope="All staff",
            source_filename="remote-work-faq-2024.md",
            is_sample=True,
            page_count=1,
            created_at=SAMPLE_CREATED_AT,
        ),
        [
            _passage(
                "doc-remote-work-faq",
                "days",
                1,
                1,
                "Q: How many days can I work remotely? A: All staff may work remotely up to "
                "5 days per week, subject to manager approval.",
            ),
            _passage(
                "doc-remote-work-faq",
                "contractors",
                1,
                2,
                "Q: Are contractors eligible? A: Yes. Contractors may work remotely up to "
                "5 days per week.",
            ),
            _passage(
                "doc-remote-work-faq",
                "status",
                1,
                3,
                "Q: Is this FAQ authoritative? A: This FAQ is for general guidance only and does "
                "not override any policy.",
            ),
        ],
    ),
    (
        SourceDocument(
            id="doc-travel-policy",
            title="Travel Policy",
            doc_type="policy",
            version="2.0",
            published_date=date(2023, 4, 1),
            effective_date=date(2023, 4, 1),
            supersedes=[],
            authority_rank=60,
            authority_label="Standing travel policy",
            scope="All employees in India",
            source_filename="travel-policy-v2.0.md",
            is_sample=True,
            page_count=2,
            created_at=SAMPLE_CREATED_AT,
        ),
        [
            _passage(
                "doc-travel-policy",
                "hotel",
                5,
                1,
                "Section 6.1 — Hotel limits. Hotel accommodation is reimbursed up to ₹4,500 per "
                "night in Tier-1 cities.",
            ),
            _passage(
                "doc-travel-policy",
                "approval",
                5,
                2,
                "Section 6.2 — Travel approval. Domestic travel requires manager approval before "
                "booking. International travel requires director approval.",
            ),
            _passage(
                "doc-travel-policy",
                "meals",
                6,
                3,
                "Section 6.3 — Meals. Meals are reimbursed up to ₹1,200 per day during approved "
                "domestic travel.",
            ),
        ],
    ),
    (
        SourceDocument(
            id="doc-travel-circular-2024-03",
            title="Travel Circular 2024-03: Tier-1 Hotel Limit",
            doc_type="amendment",
            version="2024-03",
            published_date=date(2024, 4, 18),
            effective_date=date(2024, 5, 1),
            supersedes=["doc-travel-policy"],
            authority_rank=90,
            authority_label="Approved travel amendment",
            scope="All employees in India",
            source_filename="travel-circular-2024-03.md",
            is_sample=True,
            page_count=1,
            created_at=SAMPLE_CREATED_AT,
        ),
        [
            _passage(
                "doc-travel-circular-2024-03",
                "purpose",
                1,
                1,
                "Purpose. This circular amends Section 6.1 of the Travel Policy (version 2.0) for "
                "employees in India. It is effective 1 May 2024 and supersedes the previous Tier-1 "
                "hotel limit.",
            ),
            _passage(
                "doc-travel-circular-2024-03",
                "amended",
                1,
                2,
                "Section 6.1 (amended). Hotel accommodation is reimbursed up to ₹6,000 per night "
                "in Tier-1 cities. Tier-2 city limits are unchanged.",
            ),
            _passage(
                "doc-travel-circular-2024-03",
                "approval",
                1,
                3,
                "Approval. The Director of Finance approved this circular on 18 April 2024.",
            ),
        ],
    ),
    (
        SourceDocument(
            id="doc-data-retention-standard",
            title="Data Retention Standard",
            doc_type="standard",
            version="1.2",
            published_date=date(2025, 11, 1),
            effective_date=date(2025, 11, 1),
            supersedes=[],
            authority_rank=80,
            authority_label="Mandatory standard",
            scope="All employees and contractors",
            source_filename="data-retention-standard-v1.2.md",
            is_sample=True,
            page_count=2,
            created_at=SAMPLE_CREATED_AT,
        ),
        [
            _passage(
                "doc-data-retention-standard",
                "financial",
                4,
                1,
                "Section 4.1 — Financial records. Financial records must be retained for 7 years "
                "from the end of the financial year.",
            ),
            _passage(
                "doc-data-retention-standard",
                "hr",
                4,
                2,
                "Section 4.2 — HR records. Personnel records must be retained for 3 years after "
                "the end of employment.",
            ),
            _passage(
                "doc-data-retention-standard",
                "legal-hold",
                5,
                3,
                "Section 4.3 — Legal hold. Records must not be deleted while a legal hold is "
                "active, regardless of the retention period.",
            ),
        ],
    ),
]

DEMO_SCENARIOS: list[DemoScenario] = [
    DemoScenario(
        id="expense-amendment",
        label="Expense limit after an amendment",
        question="What is the current expense reimbursement limit for client entertainment in India?",
        hint="Supersession + effective date",
        expected_status="resolved",
        expected_outcome=(
            "Selects ₹8,000 from Finance Circular 2025-07, which explicitly supersedes the "
            "₹5,000 limit, and cites both documents."
        ),
    ),
    DemoScenario(
        id="leave-authority",
        label="Handbook vs newer FAQ",
        question="How many days of paid annual leave do full-time employees in India receive?",
        hint="Newer source without authority",
        expected_status="conflict_unresolved",
        expected_outcome=(
            "Flags 12 days vs 18 days, observes that the newer FAQ does not amend the handbook, "
            "and reports that the current entitlement is not established."
        ),
    ),
    DemoScenario(
        id="contractor-threshold",
        label="Conflicting contractor approvals",
        question="What approval threshold applies to contractor purchases in India?",
        hint="No precedence relationship",
        expected_status="conflict_unresolved",
        expected_outcome=(
            "Presents the ₹50,000 CFO threshold and the ₹1,00,000 COO threshold, cites both, and "
            "abstains from choosing a winner."
        ),
    ),
]

CORPUS_NOTE = (
    "All twelve documents in the sample corpus are fictional and were written for this "
    "demonstration. Dates, policy numbers and authority labels are illustrative."
)


def load_sample_corpus(db: Database) -> int:
    """Replace the sample documents while preserving uploaded documents."""
    db.delete_sample_documents()
    for document, passages in SAMPLE_DOCUMENTS:
        db.add_document(document, passages)
    return len(SAMPLE_DOCUMENTS)
