# अधिKaar - Architecture

Every diagram below reflects the actual code. Nothing in the runtime path leaves the user's machine.

---

## 1. System Overview

The whole product is one local process plus a browser. There is no server, no account, no outbound call at runtime.

```mermaid
graph TB
    subgraph BROWSER["Browser - vanilla JS SPA, zero build"]
        UI["index.html / app.js / style.css"]
        VEND["vendor: pdf.js, Tesseract.js,<br/>marked, lucide (pinned local copies)"]
        LS[("localStorage<br/>cases, drafts, deadlines")]
    end

    subgraph HOST["Your computer - nothing leaves this box"]
        subgraph FLASK["Flask service - 127.0.0.1:5000"]
            API["REST API - 19 endpoints"]
            SESS[("sessions dict<br/>in-memory, per session")]
            PIPE["lawsteps_pipeline.py<br/>draft - guard - verify - repair"]
        end

        OLLAMA["Ollama<br/>gemma4:e4b -> gemma3:4b fallback"]
        CHROMA[("ChromaDB<br/>4 persistent collections")]
        WHISPER["faster-whisper<br/>speech to text"]
        TTS["MMS-TTS<br/>text to speech, 11 langs"]
        PADDLE["PaddleOCR<br/>PP-OCRv6 / v5 Devanagari"]
        UP[("data/uploads<br/>per-session doc text")]
    end

    UI -->|"HTTP JSON"| API
    UI --- VEND
    UI --- LS

    API --> OLLAMA
    API --> CHROMA
    API --> WHISPER
    API --> TTS
    API --> PADDLE
    API --- SESS
    API --- UP
    API --> PIPE
    PIPE --> OLLAMA

    style HOST fill:#EEF2FF,stroke:#4338CA,stroke-width:2px
    style BROWSER fill:#FAF9F6,stroke:#57534E
    style OLLAMA fill:#C7D2FE,stroke:#4338CA
    style CHROMA fill:#C7D2FE,stroke:#4338CA
```

---

## 2. Knowledge Base and Retrieval Layer

`rag_setup.py` builds four ChromaDB collections from curated JSON plus the official-law corpus. Each corpus chunk keeps its act, section and official source URL, which is what lets citations resolve to real government pages.

```mermaid
graph LR
    subgraph SRC["data/ - source of truth"]
        A1["ipc_bns_mapping.json<br/>216 mappings"]
        A2["bnss_crpc_mapping.json<br/>80 mappings"]
        A3["rights_knowledge.json"]
        A4["evidence_checklists.json - 20"]
        A5["case_studies.json - 22"]
        A6["document_templates.json - 45+"]
        A7["legal_aid_directory.json<br/>36 states/UTs + helplines"]
        A8["corpus/ - 27 JSONL<br/>6,845 official-law chunks"]
        A9["raw/ - RTI Act PDF,<br/>IndicLegalQA (optional drops)"]
    end

    RS["rag_setup.py<br/>--only to rebuild one"]

    subgraph COLS["ChromaDB collections"]
        C1[("ipc_bns")]
        C2[("rights_knowledge<br/>rights + checklists +<br/>cases + templates + QA")]
        C3[("legal_aid")]
        C4[("official_law<br/>act, section, official_url")]
    end

    A1 --> RS
    A2 --> RS
    A3 --> RS
    A4 --> RS
    A5 --> RS
    A6 --> RS
    A7 --> RS
    A8 --> RS
    A9 -->|"rti_to_jsonl.py"| A8

    RS --> C1
    RS --> C2
    RS --> C3
    RS --> C4

    style COLS fill:#EEF2FF,stroke:#4338CA
    style SRC fill:#FAF9F6,stroke:#57534E
```

---

## 3. Chat Request Flow

The multilingual expansion is why a Hinglish phrase like "mera malik ne salary nahi di" still reaches English-indexed unpaid-wages knowledge.

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant SPA as Browser SPA
    participant API as /api/chat
    participant EXP as Query expansion<br/>(KEYWORD_MAPPINGS)
    participant DB as ChromaDB
    participant G as Gemma via Ollama

    U->>SPA: types or speaks a question
    SPA->>API: {message, language, session_id, history}
    Note over API: rehydrates session from<br/>client history if server restarted
    API->>EXP: expand + translate to keywords
    EXP-->>API: expanded query
    API->>DB: retrieve (rights, ipc_bns)
    DB-->>API: grounding context
    opt document attached to session
        API->>DB: retrieve from doc_<session>
        DB-->>API: document chunks
    end
    Note over API: power-imbalance detection<br/>injects protective advisories
    API->>G: system prompt + RAG context + history
    Note over G: num_ctx 8192, num_predict -1<br/>(no truncation)
    G-->>API: answer
    API-->>SPA: {response}
    SPA-->>U: renders + optional read-aloud
```

---

## 4. Verified "Law and Next Steps" Pipeline

The core anti-hallucination design. A claim naming a section that its own cited sources do not contain is rejected deterministically, before any model is trusted to grade itself.

```mermaid
flowchart TD
    S["Situation"] --> R["retrieve_chunks<br/>official_law + rights<br/>(keeps metadata + official_url)"]
    R --> D["DRAFT - LLM call 1<br/>temp 0.2, format=json<br/>six panels + claims citing chunk ids"]

    D --> G{"GUARD - free, no model<br/>uncited_section_references()<br/>does the claim name a section<br/>absent from its cited excerpts?"}

    G -->|"fabricated section"| X["status = unverified"]
    G -->|"clean"| V["VERIFY - LLM call 2, batched, temp 0<br/>each claim vs ONLY its cited excerpts"]

    V -->|"supported"| OK["status = supported"]
    V -->|"not supported"| X

    OK --> ASM["ASSEMBLE in Python"]
    X --> ASM

    ASM --> P1["a. Situation and the law"]
    ASM --> P2["b. How each statement was checked"]
    ASM --> P3["c. Official sources<br/>ONLY urls of chunks cited<br/>by supported claims"]
    ASM --> P4["d. Stress test - both sides"]
    ASM --> P5["e. Rights card"]
    ASM --> P6["f. Explain to someone you trust"]

    style G fill:#FEF3C7,stroke:#F59E0B,stroke-width:2px
    style X fill:#FEE2E2,stroke:#EF4444
    style OK fill:#D1FAE5,stroke:#10B981
    style P3 fill:#D1FAE5,stroke:#10B981
```

Typical cost: 2 LLM calls (draft + verify). The guard is free and runs first, so the cheapest check kills the most dangerous error.

---

## 5. Document Flow - Upload, Explain, Ask

OCR picks its model from the document's script, not the UI language, because Indian legal papers are routinely Hindi plus English on one page.

```mermaid
flowchart TD
    U["User uploads PDF / image"] --> T{"/api/extract-document<br/>server OCR available?"}

    T -->|yes| P["PaddleOCR<br/>Devanagari model reads<br/>Devanagari + Latin"]
    T -->|"fails / unavailable"| F["Browser fallback<br/>pdf.js text layer"]
    F --> F2{"text layer found?"}
    F2 -->|no, scanned| F3["render pages to canvas<br/>-> Tesseract.js OCR"]
    F2 -->|yes| TXT
    F3 --> TXT
    P --> TXT["extracted text"]

    TXT --> IDX["index_session_document()<br/>chunk -> doc_&lt;session&gt; collection<br/>+ save data/uploads/&lt;session&gt;.txt"]
    TXT --> EXP["/api/translate-document<br/>plain-language explanation<br/>num_ctx 8192"]

    IDX --> ASK["/api/ask-document"]
    EXP --> UI2["shown to user"]

    UI2 --> Q["User asks about the document"]
    Q --> ASK
    ASK --> WHOLE["Sends the WHOLE document text<br/>inline with the question<br/>(no semantic top-k, no session<br/>dependency - survives restarts)"]
    WHOLE --> G2["Gemma - answer strictly<br/>from this document"]
    G2 --> ANS["grounded answer rendered inline"]

    style WHOLE fill:#D1FAE5,stroke:#10B981
    style T fill:#FEF3C7,stroke:#F59E0B
```

---

## 6. Voice Flow

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant SPA as Browser
    participant STT as /api/transcribe
    participant W as faster-whisper
    participant CH as /api/chat
    participant TTS as /api/tts
    participant M as MMS-TTS

    Note over SPA: mic needs a secure context<br/>localhost or HTTPS
    U->>SPA: taps mic, speaks
    SPA->>SPA: MediaRecorder captures audio
    SPA->>STT: audio blob + language
    STT->>W: transcribe (VAD, beam 5)
    Note over W: silence + hallucination guards<br/>drop phantom "Thank you"
    W-->>STT: text
    STT-->>SPA: {text}
    SPA->>CH: send as a normal question
    CH-->>SPA: answer
    U->>SPA: taps Listen
    SPA->>TTS: {text, language}
    TTS->>M: synthesize (lazy-loaded per language)
    M-->>TTS: WAV
    TTS-->>SPA: audio/wav
    SPA-->>U: plays audio + karaoke word highlight
    Note over SPA: falls back to browser<br/>speechSynthesis if server TTS fails
```

---

## 7. Model Call Path and Safety Rails

```mermaid
flowchart LR
    C["caller"] --> CG["call_gemma()"]
    CG --> RES{"model resolved?"}
    RES -->|no| PICK["get_working_model()<br/>gemma4:e4b -> gemma3:4b -> gemma3:latest"]
    PICK --> CG
    RES -->|yes| OPT["options:<br/>num_ctx 8192<br/>num_predict -1 (uncapped)<br/>format=json when structured"]
    OPT --> OL["ollama.chat"]
    OL --> ERR{"GPU crash?<br/>CUDA / exit status"}
    ERR -->|yes| CPU["retry with num_gpu=0<br/>(CPU fallback)"]
    ERR -->|no| OUT["response"]
    CPU --> OUT

    style OPT fill:#D1FAE5,stroke:#10B981
    style CPU fill:#FEF3C7,stroke:#F59E0B
```

Notes that matter:
- `OLLAMA_HOST` is normalised to loopback before importing ollama - a host bound to `0.0.0.0` is not a valid connect target and silently broke every model call.
- `num_predict = -1` because a fixed cap was chopping detailed answers mid-sentence while the prompt was asking for detail.

---

## 8. Privacy Boundary

```mermaid
flowchart TB
    subgraph DEV["User's device - the entire product"]
        direction TB
        B["Browser SPA"]
        F["Flask + Gemma + ChromaDB<br/>Whisper + MMS-TTS + PaddleOCR"]
        D[("Cases in localStorage<br/>Docs per-session, not persisted")]
        B <--> F
        B --- D
    end

    SETUP(["Internet - setup only"])
    BLOCKED["NEVER crosses this line at runtime:<br/>questions, documents, transcripts,<br/>voice, telemetry"]

    DEV -. "one time: install deps,<br/>pull Gemma / Whisper / TTS / OCR models" .-> SETUP
    DEV --- BLOCKED

    style DEV fill:#D1FAE5,stroke:#10B981,stroke-width:3px
    style SETUP fill:#FEF3C7,stroke:#F59E0B
    style BLOCKED fill:#FEE2E2,stroke:#EF4444,stroke-width:2px
```

---

## Request Map

| Surface | Endpoint | Grounding |
|---|---|---|
| Talk to Legal Helper | `/api/chat` | rights + ipc_bns + attached doc |
| Law and Next Steps | `/api/law-and-steps` | official_law + rights, verified pipeline |
| Ask about a document | `/api/ask-document` | whole document text sent inline |
| Document upload | `/api/extract-document`, `/api/upload-document`, `/api/clear-document` | PaddleOCR / pdf.js + Tesseract |
| Explain a document | `/api/translate-document` | ipc_bns section lookup |
| Section converters | `/api/bns-convert`, `/api/crpc-convert` | curated mappings, deterministic |
| Draft a document | `/api/draft-document`, `/api/document-templates` | 45+ templates |
| Legal aid | `/api/legal-aid` | legal_aid directory |
| Checklists | `/api/evidence-checklists`, `/api/rights-checklist` | 20 reviewed templates |
| Extras | `/api/rights-card`, `/api/consequence-simulator`, `/api/panchayat-bridge`, `/api/devil-advocate` | rights + situation |
| Voice | `/api/transcribe`, `/api/tts` | faster-whisper, MMS-TTS |
