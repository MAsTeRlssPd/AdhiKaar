<div align="center">

# अधिKaar

### An Offline-First, Verified, Multilingual AI Legal Assistant for Every Indian Citizen

**Your Rights, Your Language**

Built with **Gemma** · Runs **100% on-device** · **11 Indian languages** · Nothing leaves your computer

</div>

---

## About the Project

**अधिKaar** ("Adhikaar" — meaning *"rights"*) helps ordinary Indian citizens understand their legal rights, decode legal documents, and take concrete next steps — in 11 Indian languages, by voice or text, and **entirely on their own device**.

Unlike cloud chatbots, every component runs locally: the language model, the legal knowledge base, speech recognition, speech synthesis, and document OCR. A user's questions, documents, and transcripts **never leave their machine** — you can disable Wi-Fi and it still works.

Answers are powered by Google's **Gemma** running locally through Ollama, **grounded** on 6,845 reviewed chunks of official Indian law (RAG), and **verified** claim-by-claim against real statute text so citations are backed by law rather than model memory.

> ⚖️ अधिKaar provides **legal information, not legal advice**. For complex matters, consult a qualified lawyer or call NALSA on **15100**.

---

## Why It Matters

- A billion+ Indians face everyday legal problems — unpaid wages, stuck deposits, FIRs, domestic violence, consumer disputes — but lawyers are unaffordable and official information is English-first and dense.
- India's criminal laws were overhauled on **1 July 2024** (IPC → **BNS**, CrPC → **BNSS**), so even existing guidance is outdated.
- Legal matters are deeply personal → cloud AI raises real privacy fears. अधिKaar is **private by design**.

---

## Features

| Feature | What it does |
|---|---|
| **Talk to Legal Helper** | Conversational, RAG-grounded legal guidance with dynamic response depth, power-imbalance detection, and multilingual voice in/out. |
| **Law & Next Steps** | One **verified** analysis in six panels: situation & applicable law, per-claim verification, official sources with links, both-sides stress test, a shareable rights card, and a plain "explain to someone you trust" summary. |
| **Section Converter** | Instant **IPC↔BNS** and **CrPC↔BNSS** conversion (216 + 80 curated mappings) with subsection-insensitive matching and offence-name search. |
| **Translate Legal Document** | Upload a photo/PDF of a notice or FIR → on-device OCR extracts the text → the model explains it in plain words → ask questions answered **strictly from that document**. |
| **Draft a Document** | 45+ ready-to-file citizen documents (FIR requests, RTI appeals, legal notices, rent agreements, wills, POAs, complaints) generated in your language. |
| **Find Legal Aid** | PAN-India directory: State Legal Services Authorities for all 28 states + 8 UTs, Delhi district DLSAs, and national helplines (NALSA 15100, Tele-Law 14454, Women 181, Cyber 1930…). |
| **Evidence Checklists** | 20 situation-specific checklists of documents, steps, and statutory deadlines, matched to your case. |
| **Rights Card / Elder Mode / Consequence Simulator / Devil's Advocate** | Shareable sourced rights card, an intermediary-friendly explanation, a "what if you do nothing" view, and an adversarial stress test. |
| **Voice** | On-device speech-to-text (faster-whisper) and text-to-speech (MMS-TTS) in all 11 languages, with word-by-word **karaoke** read-aloud. |

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Vanilla HTML/CSS/JavaScript SPA — **zero build step**. Vendored offline assets (Lucide, Marked, pdf.js, Tesseract.js, Noto fonts). |
| **Backend** | Python 3 · Flask · Flask-CORS — loopback-only (127.0.0.1). |
| **LLM runtime** | **Ollama** serving **Gemma** locally (`gemma4:e4b` primary, `gemma3:4b` fallback). |
| **RAG / Vector store** | **ChromaDB** (persistent) with sentence-transformers embeddings (all-MiniLM-L6-v2); **EmbeddingGemma** available. |
| **Speech-to-text** | **faster-whisper** (small, int8, CPU) with VAD + hallucination guards. |
| **Text-to-speech** | **Facebook MMS-TTS** (per-language VITS via `transformers`), browser Web Speech API fallback. |
| **Document OCR** | **PaddleOCR** (PP-OCRv6 / PP-OCRv5, Devanagari + Latin) server-side; pdf.js + Tesseract.js in-browser fallback. |
| **PDF handling** | `pypdf` (text layer) · `pypdfium2` (rasterisation, no poppler). |

---

## Architecture

```
Browser (vanilla-JS SPA)  ──HTTP──►  Flask service (127.0.0.1:5000)
                                        │
        ┌───────────────────────────────┼───────────────────────────────┐
        ▼                               ▼                               ▼
   Ollama (Gemma)              ChromaDB (RAG)                 faster-whisper / MMS-TTS
   local generation      6,845 official-law chunks +          on-device voice in/out
                          curated datasets                     PaddleOCR document text
```

**Request flow:** user input → multilingual query expansion → ChromaDB retrieval (metadata + source URLs preserved) → prompt assembly with official-law context → local Gemma generation → (for verified answers) **draft → guard → verify → repair** → rendered in the SPA.

**Verified answer pipeline** (Law & Next Steps): the model drafts claims citing chunk IDs → a deterministic regex **guard** rejects any claim naming a section absent from its sources → surviving claims are **verified** against their excerpts → unsupported claims are dropped, and only URLs of verified sources are shown.

---

## Setup Guide

### 0. Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11 / 3.12 | 3.13 works too |
| [Ollama](https://ollama.com/download) | latest | runs the local Gemma model |
| Git | any | to clone |

### 1. Clone & enter

```bash
git clone https://github.com/MAsTeRlssPd/AdhiKaar.git
cd AdhiKaar
```

### 2. Create a virtual environment & install dependencies

```bash
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

> The heavy extras (`faster-whisper`, `paddleocr`, `torch`) download models on first use. Voice/OCR are optional — the text app runs without those models.

### 3. Pull the Gemma models

```bash
ollama pull gemma4:e4b        # answering model
ollama pull embeddinggemma    # optional: semantic retrieval
```

Keep `ollama serve` running (the Ollama app starts it automatically on Windows/macOS).

### 4. Build the RAG knowledge base (one-time)

```bash
python rag_setup.py
```

This builds four ChromaDB collections. The **official-law corpus (~6,845 chunks) is the slow, one-time step**. Rebuild a single collection without redoing the corpus:

```bash
python rag_setup.py --only rights        # curated datasets only
python rag_setup.py --only official_law  # statute corpus only
```

### 5. Run

```bash
python app.py
```

Open **http://localhost:5000**. Disable Wi-Fi — it still works.

### 6. (Optional) verify

```bash
python test_convert_match.py
python test_corpus_ingest.py
python test_checklist_match.py
python test_lawsteps_verify.py
python test_doc_rag.py
```

---

## Voice & Remote Access (HTTPS)

Browsers only allow the **microphone** on a **secure context** — `http://localhost` or **HTTPS**. Over a plain `http://<LAN-IP>` the mic is blocked by the browser (not a bug).

- **On the server machine:** just open `http://localhost:5000` — mic works.
- **Remote, with a working mic:** expose an HTTPS URL with a free tunnel while keeping all inference local:

```bash
cloudflared tunnel --url http://localhost:5000
```

Open the printed `https://….trycloudflare.com` URL — the model and data still run on your machine; the tunnel only relays traffic.

- **First voice use** downloads the Whisper model (~460 MB, once). **First TTS** per language downloads its MMS-TTS model. Then fully offline.

---

## Optional Data

Skipped cleanly if absent:

- **RTI Act corpus** — place the official PDF at `data/raw/rti_act_2005.pdf`, then `python scripts/rti_to_jsonl.py` → `python rag_setup.py --only official_law`.
- **IndicLegalQA** — place the Kaggle file at `data/raw/indic_legal_qa.json`, then `python rag_setup.py --only rights`.

---

## Project Structure

```
AdhiKaar/
├── app.py                  # Flask backend + all REST endpoints
├── rag_setup.py            # builds the ChromaDB collections
├── lawsteps_pipeline.py    # verified draft->guard->verify->repair pipeline
├── requirements.txt
├── data/                   # curated datasets + corpus + legal-aid directory
│   ├── ipc_bns_mapping.json, bnss_crpc_mapping.json
│   ├── document_templates.json, evidence_checklists.json, case_studies.json
│   ├── legal_aid_directory.json, rights_knowledge.json
│   └── corpus/             # 6,845-chunk official-law JSONL
├── static/                 # SPA (index.html, app.js, style.css) + vendored assets + fonts
├── scripts/                # rti_to_jsonl.py, gen_documentation.py
├── docs/                   # AdhiKaar_Documentation.docx (full technical writeup)
└── test_*.py               # test suites
```

---

## Privacy & Safety

- **100% on-device** — LLM, embeddings, RAG, OCR and speech all run locally; works offline.
- **Loopback-only API** (127.0.0.1) — not exposed to the network by default.
- Uploaded documents and transcripts are processed **per-session** and not persisted by default.
- Official sources and effective dates **outrank** model memory; unsupported legal claims are removed or marked **unverified**.

---

## Limitations

- OCR of handwritten / low-quality bilingual scans is imperfect; PP-OCRv6 has no Devanagari model yet, so Hindi text uses PP-OCRv5.
- Corpus focuses on high-impact central acts; more acts/state laws can be added via the same ingestion pipeline.
- Content is auto-generated from official sources and curated mappings — a **human legal-accuracy review is recommended** before production use.

---

## Documentation

Full technical & product documentation: **[`docs/AdhiKaar_Documentation.docx`](docs/AdhiKaar_Documentation.docx)** (regenerate with `python scripts/gen_documentation.py`).

---

<div align="center">

**अधिKaar — Your Rights, Your Language.**
Justice that fits in your pocket, and never leaves it.

</div>
