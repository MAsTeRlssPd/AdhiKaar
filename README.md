# अधिKaar (AdhiKaar) — AI Legal Assistant

**अधिKaar** is a locally-deployed, multilingual AI legal assistant for Indian citizens. It empowers ordinary people to understand their legal rights and options in plain, simple language using the power of Gemma 4 (via Ollama).

## Features Implemented

| Feature | How It Works |
|---------|-------------|
| **Multilingual Voice & Text** | 11 languages supported via Web Speech API + language-specific Gemma prompts |
| **Confirmation Loop** | Ensures the AI restates the user's situation before advising |
| **Power-Imbalance Detector** | Keyword analysis injects protective advisories for vulnerable parties |
| **BNS ↔ IPC Converter** | 75+ mapping rules + RAG search + AI explanation for the July 2024 law changes |
| **Devil's Advocate Mode** | Second AI call with adversarial system prompt to stress-test your case |
| **Consequence Simulator** | Models a timeline of what happens if you take no action |
| **Panchayat Bridge / Elder Mode** | Simplified explanations formatted for community intermediaries |
| **Rights Card Generator** | Generates a "Know Your Rights" card image (html2canvas) for downloading/sharing |
| **Document Translator** | In-browser OCR (Tesseract.js) + AI translation of legal documents |
| **Legal Aid Finder** | Search 20 states, 100+ districts, and national helplines |
| **Rights Checklist** | AI generates a situation-specific actionable checklist |

## Architecture

- **Backend:** Flask (Python) exposing 9 REST API endpoints.
- **AI Model:** Gemma 4 (run locally via Ollama).
- **RAG Database:** ChromaDB stores and retrieves legal knowledge (Rights knowledge, IPC/BNS mappings, Legal Aid directories).
- **Frontend:** Vanilla HTML/CSS/JS (Single Page Application, Light Theme, Mobile-Friendly, Zero Build Steps).
- **Client-side ML:** Tesseract.js for in-browser OCR (documents never leave the device).

## How to Run

### Prerequisites
1. **Ollama** installed and running
2. **Python 3.8+** installed

### Steps

1. **Install Ollama and pull Gemma 4**
   ```bash
   ollama pull gemma4
   ```

2. **Clone the repository**
   ```bash
   git clone https://github.com/MAsTeRlssPd/AdhiKaar.git
   cd AdhiKaar
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up RAG knowledge base (one-time)**
   ```bash
   python rag_setup.py
   ```

5. **Start the server**
   ```bash
   python app.py
   ```

6. **Open in browser**
   Navigate to `http://localhost:5000`

## Project Structure

```
├── app.py                          # Flask server (API endpoints)
├── rag_setup.py                    # RAG ingestion script
├── requirements.txt                # Python dependencies
├── data/                           # Knowledge base JSON files
│   ├── ipc_bns_mapping.json        # 75+ IPC↔BNS mappings
│   ├── legal_aid_directory.json    # States, districts, helplines
│   └── rights_knowledge.json       # Case types, legal terms
└── static/                         # Frontend assets
    ├── index.html                  # Single Page Application HTML
    ├── style.css                   # Responsive, accessible stylesheet
    └── app.js                      # Application logic
```

## Key Design Decisions
- **Village-Friendly UX:** 18px+ fonts, large touch targets, clear icons, voice-first input, and warm colors for high accessibility.
- **Privacy First:** OCR happens in the browser via Tesseract.js. The AI runs locally via Ollama. No user data goes to external servers.
- **Robust Prompt Engineering:** Core features like the power-imbalance detector and Devil's Advocate mode rely on complex, specifically-tuned system prompts instead of brittle code logic.