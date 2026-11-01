# PathAid architecture diagrams

These diagrams describe the approved local-first target, not every component in
the current legacy implementation.

## System context

```mermaid
flowchart LR
    User[Student on macOS]
    Web[Local PathAid web app]
    Ext[Chrome application copilot]
    API[Loopback FastAPI service]
    DB[(SQLite)]
    Vault[Encrypted local document vault]
    Keychain[macOS Keychain]
    Public[Approved public scholarship sources]
    Portal[Official application portals]
    Gemini[Google Gemini]

    User --> Web
    User --> Ext
    Web <--> API
    Ext <--> API
    API <--> DB
    API <--> Vault
    Vault -. key .-> Keychain
    API -. API key .-> Keychain
    API --> Public
    API --> Gemini
    Ext --> Portal
    User --> Portal
```

## Discovery and matching

```mermaid
flowchart TD
    Due[Daily due scan or launch catch-up] --> Scope{Approved scope and policy?}
    Scope -- No --> Stop[Do not automate]
    Scope -- Yes --> Fetch[Bounded public fetch]
    Fetch --> Changed{Normalized content changed?}
    Changed -- No --> Fresh[Update scan freshness]
    Changed -- Yes --> Extract[Gemini extracts structured requirements]
    Extract --> Validate{Deterministic validation passes?}
    Validate -- No --> Invalid[Keep prior valid version and record failure]
    Validate -- Yes --> Version[Store active scholarship version]
    Version --> Match[Compare with local profile]
    Match --> Fail{Any hard failure?}
    Fail -- Yes --> NotMatch[Not a match]
    Fail -- No --> Unknown{Any hard unknown?}
    Unknown -- Yes --> Possible[Possible match]
    Unknown -- No --> Strong[Strong match]
```

## Lead verification

```mermaid
sequenceDiagram
    actor U as User
    participant P as PathAid
    participant L as Lead listing
    participant S as Official sponsor

    U->>P: Save individual lead URL/title
    P->>L: Resolve sponsor/application reference
    P->>S: Acquire current official page
    alt official evidence is valid
        S-->>P: Current rules and application URL
        P-->>U: Show verified scholarship match
    else absent, stale, or unverifiable
        P-->>U: Keep lead history; hide from current matches
    end
```

## Application copilot

```mermaid
sequenceDiagram
    actor U as Student
    participant W as PathAid web app
    participant P as Official portal
    participant E as Chrome side panel
    participant A as Local FastAPI

    U->>W: Click Apply
    W->>A: Mark In progress
    W->>P: Open official application
    U->>E: Activate PathAid
    E->>P: Inspect supported visible fields
    E->>A: Request mapped local values
    A-->>E: Values, sensitivity labels, document metadata
    E-->>U: Preview proposed and skipped fields
    U->>E: Fill application
    E->>P: Fill supported fields only
    U->>E: Attach selected file
    E->>P: Attach that file
    U->>P: Review, certify, and submit personally
```

## Local security boundaries

```mermaid
flowchart TB
    subgraph Browser[Chrome]
      UI[Local web UI]
      Side[Extension side panel]
      Tab[Active application tab]
    end
    subgraph Mac[Local PathAid processes]
      API[127.0.0.1 FastAPI]
      Worker[Scheduler and worker]
      DB[(SQLite)]
      Files[Encrypted documents]
    end
    KC[macOS Keychain]
    Net[Approved public sources / Gemini]

    UI --> API
    Side -->|exact origin + install token| API
    Side -->|user activation only| Tab
    API --> DB
    Worker --> DB
    API --> Files
    API -. secrets .-> KC
    Worker --> Net
```

## Target data ownership

| Data | Location | Sent externally? |
| --- | --- | --- |
| Student profile and match results | SQLite | No for eligibility |
| Public scholarship source text | Snapshots/SQLite | Yes, to Gemini extraction |
| Gemini key and document key | macOS Keychain | Gemini key only to Gemini |
| Résumé/transcript | Encrypted local vault | Only to user-selected portal attachment |
| Essays | SQLite/encrypted backup | Optional Gemini analysis when allowed |
| Portal credentials/cookies | Browser only | Never stored by PathAid |
