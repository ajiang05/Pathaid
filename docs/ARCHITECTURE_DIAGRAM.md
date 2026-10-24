# Pathaid architecture diagrams

Last verified against `feature/reviewed-launch-catalog` on 2026-10-24. These
diagrams describe the implemented application and the prepared single-server
hosted topology. Public provisioning, human catalog approval, and hosted
verification remain release gates.

## Runtime and trust boundaries

```mermaid
flowchart LR
    Student[Student browser]
    Admin[Administrator browser]

    subgraph Public[Public HTTPS boundary]
        Caddy[Caddy TLS edge]
    end

    subgraph App[Private application network]
        Next[Next.js 16 frontend<br/>same-origin /api proxy]
        API[FastAPI API<br/>student and admin sessions]
        Worker[Ingestion worker<br/>leased durable stages]
        Scheduler[Daily scheduler<br/>approved source scopes]
        Migrate[Alembic migration job]
        DB[(PostgreSQL 16<br/>system of record)]
    end

    subgraph External[Approved external services]
        Sources[Official provider websites]
        Gemini[Gemini API]
    end

    Student -->|HTTPS| Caddy
    Admin -->|HTTPS| Caddy
    Caddy -->|private HTTP| Next
    Next -->|same-origin JSON| API
    API -->|SQLAlchemy| DB
    Worker -->|claim and persist| DB
    Scheduler -->|schedule and enqueue| DB
    Migrate -->|ordered schema upgrades| DB
    Worker -->|bounded HTTP acquisition| Sources
    Worker -->|structured extraction| Gemini
    API -.->|consented explanation only| Gemini
```

Security boundaries:

- Caddy is the only public container in the prepared production overlay.
- PostgreSQL, the API, worker, scheduler, and migration job have no public
  production port.
- Student and administrator sessions use separate opaque HttpOnly cookies and
  CSRF tokens.
- Forwarded client addresses affect authentication throttling only when the
  socket peer belongs to `PATHAID_TRUSTED_PROXY_CIDRS`.
- Gemini never receives credentials or identity data and has no publication
  authority.

## Automated acquisition and human publication

```mermaid
flowchart TD
    Due[Approved source becomes due]
    Claim[Scheduler claims source window]
    Acquire[Worker acquires bounded public content]
    Hash{Normalized content changed?}
    Fresh[Record unchanged freshness]
    Extract[Gemini proposes structured draft]
    Validate[Deterministic schema, rule,<br/>evidence, URL, and deadline validation]
    Review[Private administrator review<br/>source beside editable proposal]
    Decision{Human decision}
    Correct[Correct and revalidate]
    Reject[Reject and retain audit history]
    Publish[Atomically publish revision<br/>and append approval event]
    PublicCatalog[(Current published catalog)]

    Due --> Claim --> Acquire --> Hash
    Hash -->|No| Fresh
    Hash -->|Yes| Extract --> Validate
    Validate -->|Invalid| Correct
    Validate -->|Valid or warned| Review --> Decision
    Decision -->|Edit| Correct --> Validate
    Decision -->|Reject| Reject
    Decision -->|Approve with attestations| Publish --> PublicCatalog
```

The scheduler, worker, and model stop before publication. Only an authenticated
administrator can attest to source accuracy and publish a valid revision.

## Student matching and explanations

```mermaid
sequenceDiagram
    actor Student
    participant Web as Next.js
    participant API as FastAPI
    participant DB as PostgreSQL
    participant Engine as Eligibility and ranking
    participant AI as Gemini (optional)

    Student->>Web: Sign in and save profile
    Web->>API: Same-origin authenticated request + CSRF
    API->>DB: Store optional typed answers and consent
    Student->>Web: Discover support
    Web->>API: POST /api/evaluate
    API->>DB: Load current published revisions only
    API->>Engine: Evaluate three-valued rules and stable ranking
    Engine-->>API: Labels, reasons, missing fields, and ranking factors
    API-->>Web: Source-backed deterministic results
    opt Student opted into AI explanations
        Web->>API: Request explanation for one published revision
        API->>AI: Minimum relevant fields + reviewed facts
        AI-->>API: Structured selection of supplied reasons
        API-->>Web: Validated explanation or deterministic fallback
    end
    Web-->>Student: Eligibility, availability, checklist, and official link
```

Eligibility, application availability, and award selection remain separate.
The model cannot change candidates, labels, ranking, deadlines, or amounts.

## Deployment units

| Unit | Implementation | Public exposure | Durable state |
|---|---|---|---|
| TLS edge | Caddy 2.11.4 | Ports 80/443 | Certificate volumes |
| Web | Next.js 16.4.2 standalone server | Through Caddy | None |
| API | FastAPI on Python 3.14 | Through Next.js `/api` proxy | PostgreSQL |
| Worker | Python ingestion process | None | PostgreSQL stages and leases |
| Scheduler | Python scheduling process | None | PostgreSQL schedules and scans |
| Migration | Alembic one-shot job | None | PostgreSQL schema history |
| Database | PostgreSQL 16 | None | Named volume and encrypted backup |

See [Architecture](ARCHITECTURE.md) for component details and
[Deployment](deployment.md) for configuration, migrations, backup, and the
prepared production Compose overlay.
