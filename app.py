"""
अधिKaar — AI Legal Assistant for Every Indian Citizen
Flask Backend with Gemma 4 via Ollama + ChromaDB RAG
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os

# The ollama Python client reads OLLAMA_HOST to decide where to CONNECT, and
# builds its default client at import time. A server may bind 0.0.0.0, but
# 0.0.0.0 is not a valid *connect* target on Windows — normalise it (and
# blanks) to loopback BEFORE importing ollama so the client can reach it.
_oh = os.environ.get('OLLAMA_HOST', '').strip()
if _oh in ('', '0.0.0.0') or _oh.startswith('0.0.0.0:'):
    os.environ['OLLAMA_HOST'] = '127.0.0.1:' + (_oh.split(':', 1)[1] if ':' in _oh else '11434')

import ollama
import chromadb
from chromadb.utils import embedding_functions
from lawsteps_pipeline import run_pipeline as run_law_steps
import json
import sys
import uuid
import traceback
import re
from urllib.parse import urlparse

# Fix Windows console encoding for emoji/Unicode in print() statements
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ══════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)
# Never let the browser cache static files during development —
# stale cached JS/CSS causes "ghost" bugs after edits
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

GEMMA_MODEL_PREFERRED = os.environ.get('GEMMA_MODEL_PREFERRED', 'gemma4:e4b')
CHROMA_DIR = os.path.join(os.path.dirname(__file__), 'chroma_db')
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

# Resolved at first request to avoid blocking the dev-server watchdog reloader
_resolved_model = None

def get_working_model():
    """Lazy model resolver: try preferred model first, fall back to gemma3:4b on GGML crashes."""
    global _resolved_model
    if _resolved_model:
        return _resolved_model
    candidates = [GEMMA_MODEL_PREFERRED, 'gemma3:4b', 'gemma3:latest']
    for model in candidates:
        try:
            ollama.chat(
                model=model,
                messages=[{'role': 'user', 'content': 'hi'}],
                options={'temperature': 0, 'num_ctx': 512}
            )
            print(f"✅ Model verified and selected: {model}")
            _resolved_model = model
            return model
        except Exception as e:
            err = str(e)
            if any(k in err for k in ('GGML_ASSERT', 'stack-based buffer', 'process has terminated')):
                print(f"⚠️  {model} crashes on this hardware — trying next model")
            elif 'not found' in err.lower() or 'pull' in err.lower():
                print(f"⚠️  {model} not available locally — trying next model")
            else:
                print(f"⚠️  {model} error: {err[:150]} — trying next model")
    print("❌ No working model found. Please run: ollama pull gemma3:4b")
    _resolved_model = GEMMA_MODEL_PREFERRED
    return _resolved_model

# In-memory session storage
sessions = {}

# ══════════════════════════════════════════════════════════════
# Load Static Data
# ══════════════════════════════════════════════════════════════

def load_json(filename, fallback):
    path = os.path.join(DATA_DIR, filename)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"⚠️ Could not load {filename}: {e} — using empty fallback")
        return fallback

IPC_BNS_DATA = load_json('ipc_bns_mapping.json', [])
BNSS_CRPC_DATA = load_json('bnss_crpc_mapping.json', [])
LEGAL_AID_DATA = load_json('legal_aid_directory.json', {'helplines': [], 'states': []})
RIGHTS_DATA = load_json('rights_knowledge.json', {})
EVIDENCE_CHECKLISTS = load_json('evidence_checklists.json', {'templates': []}).get('templates', [])
DOCUMENT_TEMPLATES = load_json('document_templates.json', {'templates': []}).get('templates', [])


def _get_template(template_id):
    return next((t for t in DOCUMENT_TEMPLATES if t.get('id') == template_id), None)


def _template_placeholders(template_id):
    """Extract the ordered, de-duplicated list of [PLACEHOLDER] tokens from a
    template's sample_text — the fields a user must supply for a complete document."""
    tpl = _get_template(template_id)
    if not tpl:
        return []
    found = re.findall(r'\[([A-Z][^\]]{0,80})\]', tpl.get('sample_text', ''))
    seen, ordered = set(), []
    for raw in found:
        key = raw.strip()
        norm = key.upper()
        if norm not in seen:
            seen.add(norm)
            ordered.append(key)
    return ordered


def _template_instruction(template_id):
    """Build a drafting instruction from a document template so /api/draft-document
    can produce any of the ~45 templates, not just the hardcoded handful."""
    tpl = _get_template(template_id)
    if not tpl:
        return None
    structure = "; ".join(tpl.get('structure', []))
    return (
        f"Draft a {tpl['title']}. Purpose: {tpl.get('when_to_use', '')} "
        f"Follow this structure: {structure}. "
        f"Use this standard format, and substitute EVERY [PLACEHOLDER] with the exact "
        f"value the user provided — this is a final document, so it must contain no "
        f"square-bracket placeholders:\n{tpl.get('sample_text', '')}\n"
        f"After the document, note where to submit it: {tpl.get('where_to_submit', '')}"
    )


def match_checklist(situation):
    """Pick the evidence-checklist template that best fits a situation.

    Deterministic keyword scoring — the documents and statutory deadlines in the
    templates are human-reviewed, so grounding the model in a real template beats
    letting it invent a document list.
    """
    if not situation:
        return None
    # Expand through the same multilingual synonym map chat/RAG already uses, so
    # "salary not paid" reaches the "unpaid_wages" template and Hindi/Hinglish
    # phrasing works too.
    raw = situation.lower()
    expanded = expand_query_multilingual(situation).lower()

    def score_against(text, tpl):
        def hit(term):
            # Prefix match so "refusal" catches "refused", "eviction" catches "evicted".
            return term in text or (len(term) >= 5 and term[:5] in text)

        # The id names the case type — weight it double so "police refused to file
        # my FIR" lands on fir_refusal, not the merely police-flavoured template.
        id_terms = [t for t in tpl['id'].split('_') if len(t) >= 3]
        other = set(tpl.get('category', '').lower().split()) | set(tpl.get('title', '').lower().split())
        return (2 * sum(1 for t in id_terms if hit(t))
                + sum(1 for t in other if len(t) > 3 and t not in id_terms and hit(t)))

    # Rank on the expanded text (so Hinglish/synonyms match), but tie-break on the
    # user's raw words. Expansion is deliberately broad and can drag in a sibling
    # case type — e.g. expanding "police" injects "FIR", which ties a custodial
    # complaint with fir_refusal. The raw text settles it.
    ranked = sorted(
        ((score_against(expanded, t), score_against(raw, t), t) for t in EVIDENCE_CHECKLISTS),
        key=lambda r: (r[0], r[1]),
        reverse=True,
    )
    if not ranked or ranked[0][0] < 3:
        return None
    # Still tied after the raw tie-break => genuinely ambiguous. Assert nothing
    # rather than hand back a confidently wrong document list and deadlines.
    if len(ranked) > 1 and (ranked[0][0], ranked[0][1]) == (ranked[1][0], ranked[1][1]):
        return None
    return ranked[0][2]


def checklist_to_text(tpl):
    """Flatten a checklist template into prompt/RAG-friendly text."""
    lines = [f"Checklist: {tpl['title']} — {tpl.get('description', '')}"]
    for d in tpl.get('documents', []):
        lines.append(f"Document: {d['name']} — {d.get('why', '')} How to get: {d.get('how_to_get', '')}")
    for i, s in enumerate(tpl.get('steps', []), 1):
        lines.append(f"Step {i}: {s}")
    for dl in tpl.get('deadlines', []):
        lines.append(f"Deadline: {dl.get('what', '')} — {dl.get('timeframe', '')}")
    for tip in tpl.get('tips', []):
        lines.append(f"Tip: {tip}")
    if tpl.get('helpline'):
        lines.append(f"Helpline: {tpl['helpline']}")
    return "\n".join(lines)

# ══════════════════════════════════════════════════════════════
# Initialize RAG (ChromaDB)
# ══════════════════════════════════════════════════════════════

ef = embedding_functions.DefaultEmbeddingFunction()
chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)

def load_collection(name):
    """Load one ChromaDB collection; failure of one doesn't disable the others."""
    try:
        col = chroma_client.get_collection(name, embedding_function=ef)
        print(f"✅ ChromaDB collection '{name}' loaded")
        return col
    except Exception as e:
        print(f"⚠️ ChromaDB collection '{name}' not available. Run rag_setup.py. Error: {e}")
        return None

ipc_bns_collection = load_collection("ipc_bns")
rights_collection = load_collection("rights_knowledge")
legal_aid_collection = load_collection("legal_aid")
official_law_collection = load_collection("official_law")

# ══════════════════════════════════════════════════════════════
# RAG Helper
# ══════════════════════════════════════════════════════════════

def retrieve_context(query, collection, n_results=3, max_chars=1200, threshold=1.4):
    """Retrieve relevant documents from ChromaDB, filtered by a distance threshold."""
    if collection is None:
        return ""
    try:
        results = collection.query(query_texts=[query], n_results=n_results)
        docs = results.get('documents', [[]])[0]
        distances = results.get('distances', [[]])[0]
        
        filtered_docs = []
        for doc, dist in zip(docs, distances):
            if dist <= threshold:
                filtered_docs.append(doc)
        
        return "\n".join(filtered_docs)[:max_chars]
    except Exception as e:
        print(f"RAG retrieval error: {e}")
        return ""


def retrieve_chunks(query, collection, n_results=4):
    """Like retrieve_context, but keeps each chunk's metadata (act, section, URL).

    The verified law-and-steps pipeline needs the source URL of each statute
    excerpt — retrieve_context throws that away, which is why sources used to
    collapse to a bare domain."""
    if collection is None:
        return []
    try:
        res = collection.query(
            query_texts=[query], n_results=n_results,
            include=['documents', 'metadatas'],
        )
        docs = res.get('documents', [[]])[0]
        metas = res.get('metadatas', [[]])[0]
        ids = res.get('ids', [[]])[0]
        out = []
        for i, doc in enumerate(docs):
            m = metas[i] or {}
            out.append({
                "chunk_id": ids[i] if i < len(ids) else f"chunk_{i}",
                "text": doc or "",
                "act": m.get('act') or m.get('case_type_name') or m.get('title') or "",
                "section": m.get('section_id') or m.get('heading') or "",
                "official_url": m.get('official_url') or m.get('official_landing_url') or "",
            })
        return out
    except Exception as e:
        print(f"RAG chunk retrieval error: {e}")
        return []


# ── Per-session uploaded document (chat RAG) ──
UPLOADS_DIR = os.path.join(DATA_DIR, 'uploads')

def doc_collection_name(session_id):
    """A ChromaDB-safe, per-session collection name for the user's uploaded doc."""
    safe = re.sub(r'[^a-zA-Z0-9]', '', session_id) or 'default'
    return f"doc_{safe}"[:63]

def chunk_text(text, size=700):
    """Split text into ~700-char chunks for embedding."""
    text = text.strip()
    return [text[i:i + size] for i in range(0, len(text), size)] or [""]

def load_doc_collection(session_id):
    try:
        return chroma_client.get_collection(doc_collection_name(session_id), embedding_function=ef)
    except Exception:
        return None

KEYWORD_MAPPINGS = {
    # Labor
    "salary": "salary wages labor employment pay unpaid contract job PF ESI work seth malik office",
    "wages": "salary wages labor employment pay unpaid contract job PF ESI work seth malik office",
    "employer": "salary wages labor employment pay unpaid contract job PF ESI work seth malik office",
    "vetan": "salary wages labor employment pay unpaid contract job PF ESI work seth malik office",
    "kam": "salary wages labor employment pay unpaid contract job PF ESI work seth malik office",
    "naukri": "salary wages labor employment pay unpaid contract job PF ESI work seth malik office",
    "malik": "salary wages labor employment pay unpaid contract job PF ESI work seth malik office",
    "fired": "salary wages labor employment pay unpaid contract job PF ESI work seth malik office wrongful termination notice",
    
    # Tenancy
    "rent": "landlord tenant rent deposit security lease agreement makan malik kiraya kirayedar",
    "landlord": "landlord tenant rent deposit security lease agreement makan malik kiraya kirayedar",
    "tenant": "landlord tenant rent deposit security lease agreement makan malik kiraya kirayedar",
    "kiraya": "landlord tenant rent deposit security lease agreement makan malik kiraya kirayedar",
    "kirayedar": "landlord tenant rent deposit security lease agreement makan malik kiraya kirayedar",
    "makan": "landlord tenant rent deposit security lease agreement makan malik kiraya kirayedar",
    "makaan": "landlord tenant rent deposit security lease agreement makan malik kiraya kirayedar",
    "deposit": "landlord tenant rent deposit security lease agreement makan malik kiraya kirayedar",
    "security": "landlord tenant rent deposit security lease agreement makan malik kiraya kirayedar",
    
    # Domestic Violence
    "violence": "domestic violence abuse husband wife cruelty dowry beating maar torture pati patni hinsa",
    "domestic": "domestic violence abuse husband wife cruelty dowry beating maar torture pati patni hinsa",
    "marpeet": "domestic violence abuse husband wife cruelty dowry beating maar torture pati patni hinsa",
    "maar": "domestic violence abuse husband wife cruelty dowry beating maar torture pati patni hinsa",
    "pati": "domestic violence abuse husband wife cruelty dowry beating maar torture pati patni hinsa",
    "patni": "domestic violence abuse husband wife cruelty dowry beating maar torture pati patni hinsa",
    "hinsa": "domestic violence abuse husband wife cruelty dowry beating maar torture pati patni hinsa",
    "husband": "domestic violence abuse husband wife cruelty dowry beating maar torture pati patni hinsa",
    "wife": "domestic violence abuse husband wife cruelty dowry beating maar torture pati patni hinsa",
    "beats": "domestic violence abuse husband wife cruelty dowry beating maar torture pati patni hinsa",
    "beaten": "domestic violence abuse husband wife cruelty dowry beating maar torture pati patni hinsa",
    "beating": "domestic violence abuse husband wife cruelty dowry beating maar torture pati patni hinsa",

    # Workplace sexual harassment (POSH Act)
    "harassment": "workplace sexual harassment POSH Act internal complaints committee ICC boss colleague office",
    "harass": "workplace sexual harassment POSH Act internal complaints committee ICC boss colleague office",
    "molest": "workplace sexual harassment POSH Act internal complaints committee ICC boss colleague office",
    "touched": "workplace sexual harassment POSH Act internal complaints committee ICC boss colleague office",
    "inappropriately": "workplace sexual harassment POSH Act internal complaints committee ICC boss colleague office",
    "boss": "workplace sexual harassment POSH Act internal complaints committee ICC boss colleague office",

    # Medical negligence
    "doctor": "medical negligence hospital doctor surgery operation treatment consumer commission deficiency service",
    "hospital": "medical negligence hospital doctor surgery operation treatment consumer commission deficiency service",
    "surgery": "medical negligence hospital doctor surgery operation treatment consumer commission deficiency service",
    "operated": "medical negligence hospital doctor surgery operation treatment consumer commission deficiency service",
    "negligence": "medical negligence hospital doctor surgery operation treatment consumer commission deficiency service",
    "abuse": "domestic violence abuse husband wife cruelty dowry beating maar torture pati patni hinsa",
    "dahej": "domestic violence abuse husband wife cruelty dowry beating maar torture pati patni hinsa",
    "dowry": "domestic violence abuse husband wife cruelty dowry beating maar torture pati patni hinsa",
    
    # Cyber Crime
    "cyber": "cyber crime online fraud hacking netbanking otp upi bank net banking cheated scam blackmail",
    "fraud": "cyber crime online fraud hacking netbanking otp upi bank net banking cheated scam blackmail",
    "online": "cyber crime online fraud hacking netbanking otp upi bank net banking cheated scam blackmail",
    "paise": "cyber crime online fraud hacking netbanking otp upi bank net banking cheated scam blackmail",
    "otp": "cyber crime online fraud hacking netbanking otp upi bank net banking cheated scam blackmail",
    "upi": "cyber crime online fraud hacking netbanking otp upi bank net banking cheated scam blackmail",
    "bank": "cyber crime online fraud hacking netbanking otp upi bank net banking cheated scam blackmail",
    "cheated": "cyber crime online fraud hacking netbanking otp upi bank net banking cheated scam blackmail",
    
    # Consumer
    "consumer": "consumer complaint defective product refund warranty service cheated fraud online shop bill",
    "product": "consumer complaint defective product refund warranty service cheated fraud online shop bill",
    "service": "consumer complaint defective product refund warranty service cheated fraud online shop bill",
    "shikayat": "consumer complaint defective product refund warranty service cheated fraud online shop bill",
    "refund": "consumer complaint defective product refund warranty service cheated fraud online shop bill",
    "warranty": "consumer complaint defective product refund warranty service cheated fraud online shop bill",
    "bill": "consumer complaint defective product refund warranty service cheated fraud online shop bill",
    
    # Cheque Bounce
    "cheque": "cheque bounce dishonour NI Act Section 138 payment return memo",
    "bounce": "cheque bounce dishonour NI Act Section 138 payment return memo",
    
    # Police
    "police": "police FIR arrest bail custody complaint thana daroga SHO zero FIR",
    "fir": "police FIR arrest bail custody complaint thana daroga SHO zero FIR",
    "arrest": "police FIR arrest bail custody complaint thana daroga SHO zero FIR",
    "bail": "police FIR arrest bail custody complaint thana daroga SHO zero FIR",
    "thana": "police FIR arrest bail custody complaint thana daroga SHO zero FIR",
    "daroga": "police FIR arrest bail custody complaint thana daroga SHO zero FIR",
    
    # Property
    "property": "property land inheritance partition encroachment registration title batwara zameen kabza",
    "land": "property land inheritance partition encroachment registration title batwara zameen kabza",
    "zameen": "property land inheritance partition encroachment registration title batwara zameen kabza",
    "ghar": "property land inheritance partition encroachment registration title batwara zameen kabza",
    "hissa": "property land inheritance partition encroachment registration title batwara zameen kabza",
    "batwara": "property land inheritance partition encroachment registration title batwara zameen kabza",
    "kabza": "property land inheritance partition encroachment registration title batwara zameen kabza"
}

def expand_query_multilingual(query):
    query_lower = query.lower()
    words = query_lower.split()
    matched_expansions = []
    
    for word in words:
        clean_word = "".join(c for c in word if c.isalnum())
        if clean_word in KEYWORD_MAPPINGS:
            matched_expansions.append(KEYWORD_MAPPINGS[clean_word])
            
    if matched_expansions:
        unique_expansions = list(set(matched_expansions))
        expanded_query = query + " " + " ".join(unique_expansions)
        print(f"🔑 Multilingual RAG Expansion: '{query}' -> '{expanded_query}'")
        return expanded_query
        
    return query

def get_english_keywords_from_llm(query, language):
    """Extract English search terms from non-English query using LLM."""
    try:
        prompt = (
            "Translate the following user question into 3-5 English search keywords "
            "related to Indian law. Reply with ONLY the space-separated keywords.\n\n"
            f"Question ({language}): {query}\n"
            "Keywords:"
        )
        response = ollama.chat(
            model=get_working_model(),
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0, 'num_ctx': 256}
        )
        result = response['message']['content'].strip()
        print(f"🤖 LLM translated query to English keywords: '{result}'")
        return result
    except Exception as e:
        print(f"LLM translation error: {e}")
        return ""

def preprocess_query_for_rag(query, language):
    """Preprocess query for optimal ChromaDB matching (handles translations & keyword expansion)."""
    query_expanded = expand_query_multilingual(query)

    # Romanized variants (hinglish, tanglish, ...) are already Latin script and
    # usually hit KEYWORD_MAPPINGS, so skip the extra LLM keyword-translation call
    # like we do for English and Hinglish.
    romanized = language in ROMANIZED_LANGS
    if language != 'en' and not romanized and query_expanded == query:
        llm_keywords = get_english_keywords_from_llm(query, language)
        if llm_keywords:
            query_expanded = query + " " + llm_keywords
            
    return query_expanded

def extract_section_numbers(query):
    return re.findall(r'\b\d{3,4}\b', query)

def check_section_keywords(query):
    """Scan query for section numbers and pull BNS/IPC info from static memory."""
    sections = extract_section_numbers(query)
    extra_contexts = []
    
    for num in sections:
        for entry in IPC_BNS_DATA:
            if entry.get('ipc_section') == num or entry.get('bns_section') == num:
                doc = (
                    f"IPC Section {entry['ipc_section']} corresponds to BNS Section {entry['bns_section']}. "
                    f"Offence: {entry['offence']}. "
                    f"Description: {entry['description']} "
                    f"Punishment: {entry['punishment']}. "
                    f"Key Changes: {entry['key_changes']}."
                )
                extra_contexts.append(doc)
                
    return "\n".join(extra_contexts)

def check_case_type_keywords(query):
    """Scan query for case type keywords and pull details from rights JSON in memory."""
    query_lower = query.lower()
    extra_contexts = []
    
    case_types = RIGHTS_DATA.get('case_types', [])
    for ct in case_types:
        match_count = 0
        for kw in ct.get('keywords', []):
            if kw.lower() in query_lower:
                match_count += 1
                
        if match_count >= 2 or ct['name'].lower() in query_lower or ct.get('name_hi', '') in query_lower:
            scenarios = ". ".join(ct['common_scenarios'])
            rights = ". ".join(ct['rights'])
            steps = ". ".join(ct['steps'])
            docs = ", ".join(ct['documents_needed'])
            bns = ", ".join(ct.get('relevant_sections', {}).get('bns', []))
            other = ", ".join(ct.get('relevant_sections', {}).get('other_laws', []))
            
            doc = (
                f"Case Type: {ct['name']}. "
                f"Common Scenarios: {scenarios}. "
                f"Rights: {rights}. "
                f"Action Steps: {steps}. "
                f"Documents Needed: {docs}. "
                f"Relevant BNS Sections: {bns}. "
                f"Other Laws: {other}."
            )
            extra_contexts.append(doc)
            break
            
    return "\n".join(extra_contexts)

# ══════════════════════════════════════════════════════════════
# System Prompts
# ══════════════════════════════════════════════════════════════

LANGUAGE_INSTRUCTIONS = {
    "en": "Respond in clear, simple English. Avoid legal jargon — explain any technical terms in everyday words.",
    "hi": "उपयोगकर्ता को समझने में आसानी हो इसलिए सरल हिंदी का प्रयोग करें। Respond in simple Hindi.",
    "ta": "சட்ட ஆலோசனையை எளிமையான தமிழில் வழங்கவும். Respond in simple Tamil.",
    "te": "చట్టపరమైన సలహాను సాధారణ తెలుగులో అందించండి. Respond in simple Telugu.",
    "bn": "সহজ বাংলায় আইনি পরামর্শ দিন যাতে ব্যবহারকারী সহজে বুঝতে পারে। Respond in simple Bengali.",
    "mr": "कायदेशीर सल्ला सोप्या मराठीत द्या जेणेकरून वापरकर्त्याला सहज समजेल. Respond in simple Marathi.",
    "gu": "સરળ ગુજરાતીમાં કાનૂની સલાહ આપો જેથી વપરાશકર્તા સરળતાથી સમજી શકે. Respond in simple Gujarati.",
    "kn": "ಬಳಕೆದಾರರಿಗೆ ಅರ್ಥವಾಗುವಂತೆ ಸರಳ ಕನ್ನಡದಲ್ಲಿ ಕಾನೂನು ಸಲಹೆ ನೀಡಿ. Respond in simple Kannada.",
    "ml": "ഉപയോക്താവിന് മനസ്സിലാക്കാൻ ലളിതമായ മലയാളത്തിൽ നിയമോപദേശം നൽകുക. Respond in simple Malayalam.",
    "pa": "ਵਰਤੋਂਕਾਰ ਨੂੰ ਸਮਝਣ ਵਿੱਚ ਆਸਾਨੀ ਹੋਵੇ ਇਸਲਈ ਸਰਲ ਪੰਜਾਬੀ ਵਿੱਚ ਕਾਨੂੰਨੀ ਸਲਾਹ ਦਿਓ। Respond in simple Punjabi.",
    "hinglish": "Respond in Hinglish (mix of Hindi and English, like how people normally talk). Use Roman script. Koi bhi legal term ko simple language mein samjhao.",
    "tanglish": "Respond in Tanglish (mix of Tamil and English, the way people casually text). Use only Roman script Yenna panreenga? Romba thanks!  — never Tamil script. Explain legal terms in simple words.",
    "tenglish": "Respond in Tenglish (mix of Telugu and English, the way people casually text). Use only Roman script Ela unnavu ? Lunch aypoyinda?  — never Telugu script. Explain legal terms in simple words.",
    "benglish": "Respond in Benglish (mix of Bengali and English, the way people casually text). Use only Roman script Kemon acho? Ekta help korbe?  — never Bengali script. Explain legal terms in simple words.",
    "marlish": "Respond in Marathi-English mix, the way people casually text. Use only Roman script Tu kasa ahes? Udya bhetuya.  — never Devanagari Explain legal terms in simple words.",
    "gujlish": "Respond in Gujlish (mix of Gujarati and English, the way people casually text). Use only Roman script Kem cho? Tame shu karo cho?  — never Gujarati script. Explain legal terms in simple words.",
    "kanglish": "Respond in Kanglish (mix of Kannada and English, the way people casually text). Use only Roman script Hegiddira? Nange ondu help beku.  — never Kannada script. Explain legal terms in simple words.",
    "manglish": "Respond in Manglish (mix of Malayalam and English, the way people casually text). Use only Roman script Sugamano? Nian pinne vilikkam.  — never Malayalam script. Explain legal terms in simple words.",
    "punglish": "Respond in Punglish (mix of Punjabi and English, the way people casually text). Use only Roman script Ki haal hai? Mainu daso — never Gurmukhi script. Explain legal terms in simple words.",
    "default": "Automatically detect the language of the user's latest query and respond entirely in that language without any emojis."
}

# Maps each romanized "-lish" variant to its base language code. Used for RAG
# preprocessing, TTS voice selection, and whisper STT language hints.
ROMANIZED_LANGS = {
    "hinglish": "hi", "tanglish": "ta", "tenglish": "te", "benglish": "bn",
    "marlish": "mr", "gujlish": "gu", "kanglish": "kn", "manglish": "ml", "punglish": "pa",
}

def base_lang(code):
    """Return the base language code for a romanized variant, else the code itself."""
    return ROMANIZED_LANGS.get(code, code)

# Language of the actual document body. Hinglish keeps English structure with
# Hindi/Hinglish phrasing where natural.
LANGUAGE_NAMES = {
    "en": "English", "hi": "Hindi", "ta": "Tamil", "te": "Telugu",
    "bn": "Bengali", "mr": "Marathi", "gu": "Gujarati", "kn": "Kannada",
    "ml": "Malayalam", "pa": "Punjabi",
    "hinglish": "Hinglish (Hindi-English mix in Roman script)",
    "tanglish": "Tanglish (Tamil-English mix in Roman script)",
    "tenglish": "Tenglish (Telugu-English mix in Roman script)",
    "benglish": "Benglish (Bengali-English mix in Roman script)",
    "marlish": "Marathi-English mix in Roman script",
    "gujlish": "Gujlish (Gujarati-English mix in Roman script)",
    "kanglish": "Kanglish (Kannada-English mix in Roman script)",
    "manglish": "Manglish (Malayalam-English mix in Roman script)",
    "punglish": "Punglish (Punjabi-English mix in Roman script)",
}

MAIN_SYSTEM_PROMPT = """You are an extremely knowledgeable human legal expert with an encyclopedic understanding of Indian law. Your purpose is to provide clear, concise, and direct legal advice to citizens.

CRITICAL RESPONSE RULES:

1. **NO AI DISCLAIMERS (STRICT MANDATE)**: NEVER reveal, hint, or say that you are an AI, a chatbot, or a language model. Speak as a human lawyer.

2. **DYNAMIC RESPONSE LENGTH & DEPTH**:
   - Assess the complexity and intent of the user's input.
   - For simple greetings, affirmations, or thank-yous (e.g., "hi", "yes", "thanks"): Respond briefly in 2-3 lines.
   - For a new legal situation/first turn description: Summarize your understanding of their situation (e.g., "📋 Understanding: ...") and give brief, high-level legal advice in 4-6 lines. Do not list detailed step-by-step actions, section definitions, or list of mistakes immediately.
   - For detailed questions: If the user asks for sections, legal steps, mistakes, or documents, do NOT limit the answer. Provide comprehensive, extensive, and highly detailed answers with every single legal fact, citation, and explanation.

3. **INTENT-BASED DETAILS**:
   - **BNS/IPC Sections**: If asked which sections will be used or what law applies, list the exact BNS sections and corresponding old IPC section numbers, offence name, description, and punishment from the database context.
   - **Legal Steps**: If asked for exact legal steps or what to do next, provide a detailed, sequential, numbered action plan.
   - **Mistakes to Avoid**: If asked what mistakes to avoid or what not to do, provide a clear list of protective warnings.
   - **Required Documents**: If asked what documents are needed or how to make their case strong, list all the relevant papers, records, files, or messages to compile as evidence.

4. **POWER-IMBALANCE DETECTION**: If the situation involves a power imbalance (e.g., Landlord/Tenant, Employer/Worker, Police/Citizen, Domestic Violence), always include a strong ⚠️ PROTECTIVE ADVISORY.

5. **LEGAL REFERENCES**: Always cite specific law sections using BNS numbers. If old IPC sections apply, explain the conversion.

9. **LANGUAGE MATCHING**: {language_instruction} Do not use the language from previous turns if the user has switched to a new language in their latest query. Always match the latest query's language.

CONTEXT FROM KNOWLEDGE BASE:
{rag_context}
"""

LAWYER_IN_OPPOSITION_PROMPT = """You are a highly skilled opposing lawyer in an Indian legal context. Your ONLY job is to relentlessly oppose the user's position and provide counter-arguments directly to them.

CRITICAL EXCEPTION: If you analyze the situation and are 100% absolutely certain that the person is legally correct and there is no valid opposing argument (for example, no FIR possible, no legal basis), DO NOT provide any arguments. Instead, clearly state that their position is flawless and legally unassailable.

If there is room for argument, present the opposing side directly to the user.
- Keep your response extremely concise. Convey in human way only, in paragraphs or concise lines.
- Speak naturally like a real human lawyer having a conversation. DO NOT use emojis.
- DO NOT use any markdown headers, bullet points, or bold titles.
- DO NOT provide counter-arguments to your own points, weaknesses in your case, or strategies for the user to win. ONLY argue against the user.

{language_instruction}

SITUATION CONTEXT:
{rag_context}
"""

CONSEQUENCE_PROMPT = """Based on the user's legal situation, model what happens if they take NO ACTION at all. Present it as specific legal consequences. Do not use any emojis. Convey the given points in 1-2 lines each only with precise and correct answers.

Timeline of Inaction:
1. [What happens right away if nothing is done]
2. [Legal implications, missed opportunities]
3. [Escalation, potential consequences]
4. [Worst-case scenarios, rights that expire]
5. [The absolute worst outcome]
6. [The single most important thing to do RIGHT NOW]

Be specific about Indian law — mention actual deadlines, limitation periods, and legal consequences. Don't be alarmist but be honest about real risks. Write in clear, concise human paragraphs.

GROUNDING: Base every legal claim (section numbers, deadlines, authority names) on the CONTEXT below. If the CONTEXT does not support a specific claim, describe the step generally without inventing a section number. Formal, respectful tone. No emojis, no decorative symbols.

{language_instruction}

SITUATION CONTEXT:
{rag_context}
"""

PANCHAYAT_BRIDGE_PROMPT = """Rewrite the following legal situation and advice in the simplest possible language, formatted to be shown to a respected village elder, panchayat head, ASHA worker, or NGO worker who will help the citizen take action.

RULES:
- Use extremely simple language that a non-educated person can understand
- Be respectful and formal in tone
- Include specific law section numbers (BNS sections) for credibility
- Keep it to 5-7 key points maximum
- Include relevant helpline numbers
- Format as simple text without emojis or complex formatting
- Make clear what ACTION needs to be taken and by whom

COMMUNITY GUIDANCE (very important):
- Only If the issue is a village or community matter (land or boundary disputes, water or common-land problems, caste issues), explicitly advise approaching the Gram Panchayat sarpanch or mukhiya, local NGOs or free legal-aid clinics, and ASHA or anganwadi workers where relevant.
- Name the specific District Legal Services Authority (DLSA) contact and helpline numbers from the CONTEXT when available (for example NALSA 15100).
- Guide the person on exactly what their NEXT step should be for their specific problem.
- End with 2-3 short, reassuring sentences: the person has clear rights, free help exists, and this problem can be solved step by step so they should not feel afraid or alone.

GROUNDING: Base section numbers, authority names, and helplines on the CONTEXT below. Do not invent contact details or section numbers that are not in the CONTEXT.

FORMAT (No emojis, simple text):
Community Helper Summary

Person's Situation: [1-2 sentences]
Their Rights: [3-5 sentences]
Who Can Help Locally: [Sarpanch/mukhiya, NGOs, legal-aid clinic, ASHA worker — as relevant]
What To Do Next: [Numbered steps specific to their problem]
Legal Sections: [Relevant BNS sections]
Helpline Numbers: [Numbers]
Reassurance: [2-3 calming, supportive sentences]

{language_instruction}

KNOWLEDGE BASE CONTEXT:
{rag_context}

SITUATION AND ADVICE TO SIMPLIFY:
{context}
"""

DOCUMENT_TRANSLATE_PROMPT = """The user has a legal document (FIR, court notice, legal notice, summons, etc.) and needs it explained in plain language. The OCR text of the document is provided below.

YOUR TASKS:
1. Identify the document type (FIR, legal notice, court summons, etc.)
2. Translate/explain the document in plain, simple language
3. Highlight key information (Important dates and deadlines, Who is involved, What legal sections are mentioned, What action is required, By when must they respond/appear)
4. List every law and section mentioned in the document (IPC/CrPC/BNS/BNSS or any other Act). For any old IPC or CrPC section, state the current BNS or BNSS equivalent using the CONTEXT below.
5. What should the reader do next — clear, actionable steps

IMPORTANT: Many legal documents are in English or formal Hindi/Urdu legal language. Translate into the user's preferred language using simple, everyday words. DO NOT use any emojis. Present the explanation in natural paragraphs. Do not invent section numbers that are not in the document or the CONTEXT.

{language_instruction}

CONTEXT (section mappings from knowledge base):
{rag_context}

DOCUMENT TEXT (from OCR):
{document_text}
"""

CHECKLIST_PROMPT = """Based on the user's legal situation, generate a comprehensive, actionable checklist they can follow. Organize it by category. Use simple text without emojis.

Rights Checklist

Documents to Collect:
[Document 1 - why it's needed]

Evidence to Preserve:
[Screenshot/photo/recording - what to capture]

Notices to Send:
[What notice, to whom, by when]

Offices to Visit:
[Which office, what to do there]

Deadlines to Remember:
[Action - Deadline - Consequence of missing]

People to Contact:
[Who - Why - Number]

Be specific to Indian law and the user's exact situation. Include BNS sections where relevant. Do not use emojis or checkboxes like [ ]. Just plain text.

GROUNDING: Base every legal claim (section numbers, deadlines, authority names) on the CONTEXT below. If the CONTEXT does not support a specific claim, describe the step generally without inventing a section number. Formal, respectful tone. No emojis, no decorative symbols.

{language_instruction}

SITUATION CONTEXT:
{rag_context}
"""

# ══════════════════════════════════════════════════════════════
# Helper Functions
# ══════════════════════════════════════════════════════════════

MAX_SESSIONS = 500   # evict oldest session beyond this
MAX_HISTORY = 6      # messages kept per session (reduced to prevent context overflow)

def get_session(session_id):
    """Get or create a conversation session (bounded to avoid memory leaks)."""
    if session_id not in sessions:
        if len(sessions) >= MAX_SESSIONS:
            sessions.pop(next(iter(sessions)))
        sessions[session_id] = {
            'history': [],
            'situation_summary': '',
            'case_type': None
        }
    return sessions[session_id]

def get_language_instruction(lang):
    """Get language-specific instruction."""
    return LANGUAGE_INSTRUCTIONS.get(lang, LANGUAGE_INSTRUCTIONS['en'])

def language_directive(language):
    """A forceful, standalone language rule to append as the LAST system message.

    Gemma-class models weight trailing instructions much more heavily than a single
    line buried mid-prompt, so this is the reliable fix for features that otherwise
    drift back to English (e.g. document drafting, converters)."""
    name = LANGUAGE_NAMES.get(language, "English")
    return (
        "CRITICAL LANGUAGE RULE (highest priority):\n"
        f"- Write your ENTIRE response in {name}.\n"
        f"- {get_language_instruction(language)}\n"
        "- Do NOT reply in English unless the requested language is English.\n"
        "- Section numbers, act names (BNS, BNSS, IPC, CrPC, RTI) and proper nouns "
        "may stay in their standard English/Latin form."
    )

def call_gemma_lang(messages, language, **kwargs):
    """call_gemma but with a forceful language directive appended as the final
    system message so the response reliably lands in the user's language."""
    messages = list(messages) + [
        {'role': 'system', 'content': language_directive(language)}
    ]
    return call_gemma(messages, **kwargs)

def call_gemma(messages, temperature=0.7, fallback_cpu=False, num_ctx=4096, response_format=None, num_predict=900):
    """Call the working LLM model via Ollama (auto-detected at first call).

    num_ctx is shared between the prompt and the generation. The larger default here
    avoids the short-answer truncation that happens when the model runs out of room
    for a long reply. num_predict controls how much the model can write in one turn.
    GPU crashes still fall back to CPU below.

    response_format: pass 'json' (or a JSON schema dict) to grammar-constrain the
    output via Ollama's format= — the reliable fix for JSON that won't parse.
    """
    model = get_working_model()
    total_chars = sum(len(m["content"]) for m in messages)
    print(f"[call_gemma] model={model} messages={len(messages)} chars={total_chars} num_ctx={num_ctx} num_predict={num_predict}")
    try:
        options = {
            'temperature': temperature,
            'num_ctx': num_ctx,
            'num_predict': num_predict,
        }
        if fallback_cpu:
            options['num_gpu'] = 0

        kwargs = {'model': model, 'messages': messages, 'options': options}
        if response_format is not None:
            kwargs['format'] = response_format
        response = ollama.chat(**kwargs)
        return response['message']['content']
    except Exception as e:
        error_msg = str(e)
        # If it's a CUDA crash or buffer overrun, try again forcing CPU mode
        if not fallback_cpu and ("CUDA error" in error_msg or "exit status" in error_msg or "0xc0000409" in error_msg):
            print(f"⚠️ GPU crash detected ({error_msg}). Retrying in CPU mode...")
            return call_gemma(messages, temperature, fallback_cpu=True, num_ctx=num_ctx)

        print(f"Gemma error: {e}")
        traceback.print_exc()
        raise

def detect_power_imbalance(text):
    """Detect power imbalance patterns in user's situation."""
    patterns = {
        'employer_worker': {
            'keywords': ['employer', 'boss', 'company', 'manager', 'HR', 'office', 'salary', 'fired', 'terminated', 'naukri', 'office wale', 'seth', 'malik'],
            'vulnerable_party': 'worker/employee',
            'description': 'Employer-Worker power imbalance detected'
        },
        'landlord_tenant': {
            'keywords': ['landlord', 'owner', 'rent', 'eviction', 'tenant', 'makan malik', 'kiraya', 'makaan'],
            'vulnerable_party': 'tenant',
            'description': 'Landlord-Tenant power imbalance detected'
        },
        'police_citizen': {
            'keywords': ['police', 'station', 'arrest', 'FIR', 'custody', 'thana', 'daroga', 'inspector', 'SI', 'SHO'],
            'vulnerable_party': 'citizen',
            'description': 'Police-Citizen power imbalance detected'
        },
        'domestic': {
            'keywords': ['husband', 'wife', 'in-laws', 'sasural', 'pati', 'dowry', 'dahej', 'beating', 'violence', 'maar', 'torture'],
            'vulnerable_party': 'spouse (typically wife)',
            'description': 'Domestic power imbalance detected'
        },
        'company_consumer': {
            'keywords': ['company', 'product', 'service', 'refund', 'warranty', 'customer care', 'complaint ignored'],
            'vulnerable_party': 'consumer',
            'description': 'Company-Consumer power imbalance detected'
        }
    }
    
    text_lower = text.lower()
    detected = []
    for pattern_id, pattern in patterns.items():
        matches = sum(1 for kw in pattern['keywords'] if kw.lower() in text_lower)
        if matches >= 2:
            detected.append(pattern)
    
    return detected

# ══════════════════════════════════════════════════════════════
# API Routes
# ══════════════════════════════════════════════════════════════

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    """Main conversation endpoint with RAG context and dynamic intent detection."""
    try:
        data = request.get_json(silent=True) or {}
        message = data.get('message', '')
        language = data.get('language', 'en')
        session_id = data.get('session_id', str(uuid.uuid4()))

        session = get_session(session_id)

        # Rehydrate context after a server restart: the client stores each case's
        # transcript in localStorage and replays recent turns here. Only seed when
        # the server-side history is empty, so we never duplicate live turns.
        if not session['history'] and isinstance(data.get('history'), list):
            seeded = []
            for h in data['history'][-MAX_HISTORY:]:
                role = h.get('role')
                content = (h.get('content') or '')[:2000]
                if role in ('user', 'assistant') and content:
                    seeded.append({"role": role, "content": content})
            session['history'] = seeded

        # Preprocess and expand search query for ChromaDB (handles translation and keywords)
        search_query = preprocess_query_for_rag(message, language)
        
        # Retrieve relevant context from RAG
        rag_context = ""
        if rights_collection:
            rag_context += retrieve_context(search_query, rights_collection, n_results=2)
        if ipc_bns_collection:
            rag_context += "\n" + retrieve_context(search_query, ipc_bns_collection, n_results=2)
        
        # Inject in-memory hybrid booster matches if any
        extra_bns = check_section_keywords(message)
        if extra_bns:
            rag_context += "\n" + extra_bns
            
        extra_rights = check_case_type_keywords(message)
        if extra_rights and extra_rights[:100] not in rag_context:
            rag_context += "\n" + extra_rights

        # Ground answers in the user's uploaded document, if one is attached to this session
        if session.get('doc'):
            doc_col = load_doc_collection(session_id)
            # threshold high: user explicitly attached this doc, always surface its top chunks
            doc_context = retrieve_context(search_query, doc_col, n_results=4, max_chars=1600, threshold=999)
            if doc_context:
                rag_context += "\n\nFrom the user's uploaded document:\n" + doc_context
        
        # Detect power imbalance
        power_imbalances = detect_power_imbalance(message)
        
        # Build system prompt
        system_prompt = MAIN_SYSTEM_PROMPT.format(
            language_instruction=get_language_instruction(language),
            rag_context=rag_context
        )
        
        # Add power imbalance context to system prompt
        if power_imbalances:
            pi_text = "\n\n🚨 POWER IMBALANCE DETECTED: "
            for pi in power_imbalances:
                pi_text += f"\n- {pi['description']}. The user is likely the {pi['vulnerable_party']}."
            pi_text += "\nProvide STRONG protective advisories."
            system_prompt += pi_text
        
        # Build message history
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history
        for h in session['history'][-10:]:  # Keep last 10 messages for context
            messages.append(h)
        
        # Add current message
        messages.append({"role": "user", "content": message})

        # Call Gemma
        response_text = call_gemma_lang(messages, language, temperature=0.7)
        
        # Update session history
        session['history'].append({"role": "user", "content": message})
        session['history'].append({"role": "assistant", "content": response_text})
        session['history'] = session['history'][-MAX_HISTORY:]  # bound stored history
        session['situation_summary'] = message if not session['situation_summary'] else session['situation_summary']
        
        return jsonify({
            "response": response_text,
            "session_id": session_id,
            "power_imbalance": {
                "detected": len(power_imbalances) > 0,
                "details": [pi['description'] for pi in power_imbalances]
            }
        })
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/devil-advocate', methods=['POST'])
def devil_advocate():
    """Lawyer in opposition mode — argue against the user's position."""
    try:
        data = request.get_json(silent=True) or {}
        situation = data.get('situation', '')
        language = data.get('language', 'en')
        session_id = data.get('session_id', '')
        
        # Get conversation context
        session = get_session(session_id) if session_id else {'history': []}
        
        rag_context = ""
        if rights_collection:
            rag_context += retrieve_context(situation, rights_collection, n_results=3)
        
        system_prompt = LAWYER_IN_OPPOSITION_PROMPT.format(
            language_instruction=get_language_instruction(language),
            rag_context=rag_context
        )
        
        # Build context from conversation history
        history_text = ""
        for h in session.get('history', [])[-6:]:
            history_text += f"\n{h['role'].upper()}: {h['content']}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Here is the person's legal situation:\n{situation}\n\nConversation history:{history_text}\n\nNow argue against their position and then help them prepare."}
        ]

        response_text = call_gemma_lang(messages, language, temperature=0.8, num_ctx=4096, num_predict=900)
        
        return jsonify({"response": response_text})
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


SECTION_EXPLAIN_PROMPT = """You are explaining an Indian law section to a citizen with no legal training.

Using ONLY the CONTEXT below plus the matched mapping entries, explain in a detailed but easy-to-understand way:
1. What this section covers, in everyday words, with one simple real-life example.
2. The old and new section numbers (IPC/CrPC vs BNS/BNSS) and exactly what changed between them.
3. The punishment or the procedure involved.
4. When an ordinary citizen would come across this section and what they should do.

RULES:
- Formal, respectful tone. Do NOT use any emojis or decorative symbols.
- Do NOT invent section numbers, punishments, or facts that are not in the CONTEXT.
- Write in clear paragraphs, not one-word bullets.

{language_instruction}

MATCHED MAPPING ENTRIES:
{entries}

CONTEXT FROM KNOWLEDGE BASE:
{rag_context}
"""


def _section_explanation(query, results, language, kind):
    """Detailed, RAG-grounded explanation of a matched IPC/BNS or CrPC/BNSS section.

    kind is 'ipc_bns' or 'crpc_bnss'. Grounds the answer in the ipc_bns and/or
    official_law ChromaDB collections and answers in the user's language."""
    if not results:
        return ""

    top = results[0]
    if kind == 'ipc_bns':
        search = (
            f"IPC {top.get('ipc_section','')} BNS {top.get('bns_section','')} "
            f"{top.get('offence','')} {top.get('description','')[:200]}"
        )
    else:
        search = (
            f"CrPC {top.get('crpc_section','')} BNSS {top.get('bnss_section','')} "
            f"{top.get('offence','')} {top.get('description','')[:200]}"
        )

    rag_context = ""
    if kind == 'ipc_bns' and ipc_bns_collection:
        rag_context += retrieve_context(search, ipc_bns_collection, n_results=3)
    if official_law_collection:
        rag_context += "\n" + retrieve_context(
            search, official_law_collection, n_results=3, max_chars=2000
        )

    system_prompt = SECTION_EXPLAIN_PROMPT.format(
        language_instruction=get_language_instruction(language),
        entries=json.dumps(results[:3], ensure_ascii=False),
        rag_context=rag_context.strip() or "(no additional statute text retrieved)",
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Explain the section the user searched for: '{query}'."},
    ]
    return call_gemma_lang(messages, language, temperature=0.4, num_ctx=4096)


def _norm_section(value):
    """Normalise a section token for matching: lowercase, drop subsection suffix
    and spaces so '318(4)', '318 (4)' and '318' all compare equal."""
    v = (value or '').lower().strip()
    v = re.split(r'[\s(]', v, 1)[0]  # '318(4)' / '318 (4)' -> '318'
    return v


def _match_entries(data, query, section_field, name_fields):
    """Match converter entries. Number-like queries match the section (subsection
    insensitive); anything else does a case-insensitive substring search over the
    offence/title fields — so 'cheating' or 'murder' work, as the UI promises."""
    q = query.lower().strip()
    is_numeric = bool(re.match(r'^\d', q))  # '379', '318(4)', '354a'
    if is_numeric:
        qn = _norm_section(q)
        return [e for e in data if _norm_section(e.get(section_field, '')) == qn]
    return [e for e in data
            if any(q in (e.get(f, '') or '').lower() for f in name_fields)]


@app.route('/api/bns-convert', methods=['POST'])
def bns_convert():
    """IPC ↔ BNS section converter."""
    try:
        data = request.get_json(silent=True) or {}
        query = data.get('query', '').strip()
        direction = data.get('direction', 'ipc_to_bns')  # or 'bns_to_ipc'
        language = data.get('language', 'en')

        if not query:
            return jsonify({"results": [], "ai_explanation": ""})

        section_field = 'ipc_section' if direction == 'ipc_to_bns' else 'bns_section'
        results = _match_entries(
            IPC_BNS_DATA, query, section_field,
            ['offence', 'ipc_title', 'bns_title', 'description'],
        )

        # Detailed, RAG-grounded explanation of the matched section, in the user's language
        ai_explanation = _section_explanation(query, results, language, 'ipc_bns')

        return jsonify({
            "results": results[:10],
            "ai_explanation": ai_explanation
        })
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/crpc-convert', methods=['POST'])
def crpc_convert():
    """CrPC ↔ BNSS section converter."""
    try:
        data = request.get_json(silent=True) or {}
        query = data.get('query', '').strip()
        direction = data.get('direction', 'crpc_to_bnss')  # or 'bnss_to_crpc'
        language = data.get('language', 'en')

        if not query:
            return jsonify({"results": [], "ai_explanation": ""})

        section_field = 'crpc_section' if direction == 'crpc_to_bnss' else 'bnss_section'
        results = _match_entries(
            BNSS_CRPC_DATA, query, section_field,
            ['offence', 'crpc_title', 'bnss_title', 'description'],
        )

        ai_explanation = _section_explanation(query, results, language, 'crpc_bnss')

        return jsonify({"results": results[:10], "ai_explanation": ai_explanation})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/legal-aid', methods=['GET'])
def legal_aid():
    """Legal aid finder by state and district."""
    try:
        state_query = request.args.get('state', '').strip().lower()
        district_query = request.args.get('district', '').strip().lower()
        
        # Always return helplines
        result = {
            "helplines": LEGAL_AID_DATA.get('helplines', []),
            "states": [],
            "districts": []
        }

        if not state_query:
            # Return list of all states
            result['states'] = [
                {"name": s.get('name', ''), "name_hi": s.get('name_hi', '')}
                for s in LEGAL_AID_DATA.get('states', [])
            ]
            return jsonify(result)

        # Find matching state
        for state in LEGAL_AID_DATA.get('states', []):
            if state_query in state.get('name', '').lower() or state_query in state.get('name_hi', '').lower():
                state_info = {
                    "name": state.get('name', ''),
                    "name_hi": state.get('name_hi', ''),
                    "slsa": state.get('slsa', {}),
                    "districts": state.get('districts', [])
                }
                result['states'] = [state_info]

                # Filter districts if query provided
                if district_query:
                    result['districts'] = [
                        d for d in state.get('districts', [])
                        if district_query in d.get('name', '').lower() or district_query in d.get('name_hi', '').lower()
                    ]
                else:
                    result['districts'] = state.get('districts', [])
                break
        
        return jsonify(result)
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/translate-document', methods=['POST'])
def translate_document():
    """Translate and explain a legal document from OCR text."""
    try:
        data = request.get_json(silent=True) or {}
        document_text = data.get('text', '')
        language = data.get('language', 'en')
        
        if not document_text.strip():
            return jsonify({"error": "No document text provided"}), 400

        # Ground the section explanations: pull exact IPC/BNS mappings for any
        # section numbers in the document, plus related mapping entries.
        rag_context = check_section_keywords(document_text)
        if ipc_bns_collection:
            rag_context += "\n" + retrieve_context(
                document_text[:500], ipc_bns_collection, n_results=3
            )

        system_prompt = DOCUMENT_TRANSLATE_PROMPT.format(
            language_instruction=get_language_instruction(language),
            rag_context=rag_context.strip() or "(no section mappings retrieved)",
            document_text=document_text
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Please explain this legal document to me in simple words:\n\n{document_text}"}
        ]

        response_text = call_gemma_lang(messages, language, temperature=0.5, num_ctx=4096)

        return jsonify({"response": response_text})
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def index_session_document(session_id, text, filename, language):
    """Save + chunk-index a document into the session's ChromaDB collection so chat
    can answer from it, and return a short plain-language summary. Shared by the
    /api/upload-document and /api/extract-document endpoints."""
    session = get_session(session_id)

    # Save a local copy (offline record; git-ignored)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    safe_session = re.sub(r'[^a-zA-Z0-9_-]', '', session_id) or 'default'
    with open(os.path.join(UPLOADS_DIR, f"{safe_session}.txt"), 'w', encoding='utf-8') as f:
        f.write(text)

    # (Re)build the per-session doc collection with fresh chunks
    col_name = doc_collection_name(session_id)
    try:
        chroma_client.delete_collection(col_name)
    except Exception:
        pass
    col = chroma_client.create_collection(col_name, embedding_function=ef)
    chunks = chunk_text(text)
    col.add(documents=chunks, ids=[f"chunk_{i}" for i in range(len(chunks))])

    doc_id = str(uuid.uuid4())
    session['doc'] = {'id': doc_id, 'filename': filename, 'chunks': len(chunks)}

    # 2-3 line plain-language summary in the user's language
    summary = ""
    try:
        messages = [
            {"role": "system", "content":
                "You are a legal expert. Summarize the following document in 2-3 short, "
                "plain-language lines so a citizen understands what it is about. Do not use emojis."},
            {"role": "user", "content": text[:4000]}
        ]
        summary = call_gemma_lang(messages, language, temperature=0.3).strip()
    except Exception as e:
        print(f"Doc summary error: {e}")

    return {"doc_id": doc_id, "filename": filename, "summary": summary, "chunks": len(chunks)}


@app.route('/api/upload-document', methods=['POST'])
def upload_document():
    """Save + index an uploaded document for the session so chat can answer from it."""
    try:
        data = request.get_json(silent=True) or {}
        text = (data.get('text') or '').strip()
        filename = data.get('filename', 'document')
        language = data.get('language', 'en')
        session_id = data.get('session_id', str(uuid.uuid4()))

        if not text:
            return jsonify({"error": "No document text provided"}), 400

        return jsonify(index_session_document(session_id, text, filename, language))

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/clear-document', methods=['POST'])
def clear_document():
    """Drop the session's uploaded doc collection, state, and local file."""
    try:
        data = request.get_json(silent=True) or {}
        session_id = data.get('session_id', '')

        try:
            chroma_client.delete_collection(doc_collection_name(session_id))
        except Exception:
            pass

        if session_id in sessions:
            sessions[session_id].pop('doc', None)

        safe_session = re.sub(r'[^a-zA-Z0-9_-]', '', session_id) or 'default'
        try:
            os.remove(os.path.join(UPLOADS_DIR, f"{safe_session}.txt"))
        except OSError:
            pass

        return jsonify({"ok": True})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
# Server-side document text extraction (PaddleOCR + PDF text layer)
# ══════════════════════════════════════════════════════════════
# Moves OCR off the browser: the client uploads the raw PDF/image and we extract
# text here with PaddleOCR (Indic-script capable), keeping the frontend's
# Tesseract.js path only as a fallback. PaddleOCR models download once, then run
# offline. Coverage is uneven for a few Indic scripts, so unsupported ones fall
# back to a Devanagari or Latin pass.

PADDLE_LANG_MAP = {
    'en': 'en', 'hi': 'devanagari', 'mr': 'devanagari',
    'ta': 'ta', 'te': 'te', 'kn': 'ka', 'ml': 'ml',
    # bn/gu/pa lack good classic PaddleOCR packs — fall back to Latin.
    'bn': 'en', 'gu': 'en', 'pa': 'en',
}

_ocr_engines = {}

def get_ocr_engine(language):
    """Load (and cache) a PaddleOCR engine for the app language. Lazy — never at startup."""
    paddle_lang = PADDLE_LANG_MAP.get(base_lang(language), 'en')
    if paddle_lang not in _ocr_engines:
        from paddleocr import PaddleOCR
        print(f"⏳ Loading PaddleOCR ({paddle_lang}) — first use may download models...")
        try:
            _ocr_engines[paddle_lang] = PaddleOCR(use_angle_cls=True, lang=paddle_lang, show_log=False)
        except TypeError:
            # Newer PaddleOCR (3.x) dropped some of these kwargs.
            _ocr_engines[paddle_lang] = PaddleOCR(lang=paddle_lang)
        print("✅ PaddleOCR ready")
    return _ocr_engines[paddle_lang]


def _paddle_texts(result):
    """Pull recognised text out of a PaddleOCR result, tolerant of 2.x/3.x shapes."""
    texts = []

    def walk(obj):
        if isinstance(obj, dict):
            if 'rec_texts' in obj:                       # 3.x .predict()
                texts.extend(str(t) for t in obj['rec_texts'])
                return
            for v in obj.values():
                walk(v)
        elif isinstance(obj, (list, tuple)):
            # 2.x line: [box, (text, conf)]
            if (len(obj) == 2 and isinstance(obj[1], (list, tuple))
                    and obj[1] and isinstance(obj[1][0], str)):
                texts.append(obj[1][0])
                return
            for it in obj:
                walk(it)

    walk(result)
    return texts


def _ocr_bytes_image(engine, image_bytes):
    import numpy as np
    import cv2  # bundled with paddleocr
    arr = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if arr is None:
        return ""
    try:
        result = engine.ocr(arr)
    except Exception:
        result = engine.predict(arr)
    return "\n".join(_paddle_texts(result))


def _extract_pdf(pdf_bytes, engine, max_ocr_pages=5):
    """Return (text, pages, engine_used). Try the PDF text layer first; if the PDF
    is scanned (little/no embedded text), rasterize and OCR the first few pages."""
    import io
    text, pages = "", 0
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = len(reader.pages)
        text = "\n".join((p.extract_text() or "") for p in reader.pages).strip()
    except Exception as e:
        print(f"pypdf error: {e}")

    if len(text) >= 50:
        return text, pages, "pdf-text"

    # Scanned PDF → rasterize with pypdfium2 (no poppler needed) and OCR.
    try:
        import numpy as np
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(pdf_bytes)
        pages = len(pdf)
        ocr_text = []
        for i in range(min(pages, max_ocr_pages)):
            bitmap = pdf[i].render(scale=200 / 72)  # ~200 dpi
            arr = bitmap.to_numpy()
            try:
                result = engine.ocr(arr)
            except Exception:
                result = engine.predict(arr)
            ocr_text.append("\n".join(_paddle_texts(result)))
        return "\n".join(ocr_text).strip(), pages, "paddleocr"
    except Exception as e:
        print(f"PDF OCR error: {e}")
        return text, pages, "pdf-text"


@app.route('/api/extract-document', methods=['POST'])
def extract_document():
    """Extract text from an uploaded PDF/image server-side, then index it into the
    session so chat can answer follow-up questions about it.

    multipart/form-data: file=<pdf|jpg|png|txt>, language=<code>, session_id=<id>."""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        f = request.files['file']
        language = request.form.get('language', 'en')
        session_id = request.form.get('session_id', str(uuid.uuid4()))
        filename = f.filename or 'document'
        raw = f.read()
        if not raw:
            return jsonify({"error": "Empty file"}), 400

        lower = filename.lower()
        pages, engine_used = 1, "text"

        if lower.endswith('.txt'):
            text = raw.decode('utf-8', errors='replace')
        elif lower.endswith('.pdf') or raw[:5] == b'%PDF-':
            text, pages, engine_used = _extract_pdf(raw, get_ocr_engine(language))
        else:  # image
            text = _ocr_bytes_image(get_ocr_engine(language), raw)
            engine_used = "paddleocr"

        text = (text or "").strip()
        if not text:
            return jsonify({"error": "Could not extract any text from the document."}), 422

        # Index into the per-session collection + get a localized summary.
        indexed = index_session_document(session_id, text, filename, language)

        return jsonify({
            "text": text,
            "pages": pages,
            "engine": engine_used,
            "summary": indexed.get("summary", ""),
            "chunks": indexed.get("chunks", 0),
            "session_id": session_id,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/panchayat-bridge', methods=['POST'])
def panchayat_bridge():
    """Generate elder-friendly explanation for community intermediaries."""
    try:
        data = request.get_json(silent=True) or {}
        situation = data.get('situation', '')
        advice = data.get('advice', '')
        language = data.get('language', 'en')

        context = f"Situation: {situation}\n\nAdvice given: {advice}"

        # Ground the guidance: rights + local legal-aid contacts + statute text.
        search_query = preprocess_query_for_rag(situation, language)
        rag_context = ""
        if rights_collection:
            rag_context += retrieve_context(search_query, rights_collection, n_results=3)
        if legal_aid_collection:
            rag_context += "\n" + retrieve_context(search_query, legal_aid_collection, n_results=3)
        if official_law_collection:
            rag_context += "\n" + retrieve_context(search_query, official_law_collection, n_results=2)

        system_prompt = PANCHAYAT_BRIDGE_PROMPT.format(
            language_instruction=get_language_instruction(language),
            rag_context=rag_context.strip() or "(no additional context retrieved)",
            context=context
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Create a simplified explanation for a community elder/helper:\n\n{context}"}
        ]

        response_text = call_gemma_lang(messages, language, temperature=0.5)

        return jsonify({"response": response_text})
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/rights-checklist', methods=['POST'])
def rights_checklist():
    """Generate case-specific rights checklist."""
    try:
        data = request.get_json(silent=True) or {}
        situation = data.get('situation', '')
        language = data.get('language', 'en')
        
        search_query = preprocess_query_for_rag(situation, language)
        rag_context = ""
        if rights_collection:
            rag_context = retrieve_context(search_query, rights_collection, n_results=4)
        if official_law_collection:
            rag_context += "\n" + retrieve_context(search_query, official_law_collection, n_results=3)

        # Ground the model in a human-reviewed evidence checklist when one fits,
        # so the document list and statutory deadlines are real, not invented.
        template = match_checklist(situation)
        if template:
            rag_context += "\n\nReviewed evidence checklist for this kind of case:\n" + checklist_to_text(template)

        system_prompt = CHECKLIST_PROMPT.format(
            language_instruction=get_language_instruction(language),
            rag_context=rag_context
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Generate a comprehensive rights checklist for this situation:\n\n{situation}"}
        ]

        response_text = call_gemma_lang(messages, language, temperature=0.5)

        return jsonify({"response": response_text, "template": template})
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/evidence-checklists', methods=['GET'])
def evidence_checklists():
    """Browse the reviewed evidence checklists. ?id=<template_id> returns one in full."""
    try:
        tpl_id = request.args.get('id', '').strip()
        if tpl_id:
            tpl = next((t for t in EVIDENCE_CHECKLISTS if t['id'] == tpl_id), None)
            if not tpl:
                return jsonify({"error": "No such checklist"}), 404
            return jsonify({"template": tpl})

        return jsonify({"templates": [
            {k: t[k] for k in ('id', 'title', 'title_hi', 'category', 'description') if k in t}
            for t in EVIDENCE_CHECKLISTS
        ]})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/document-templates', methods=['GET'])
def document_templates():
    """List the document-format templates (id, title, category) for the draft picker."""
    return jsonify({"templates": [
        {k: t.get(k, '') for k in ('id', 'title', 'title_hi', 'category', 'when_to_use')}
        for t in DOCUMENT_TEMPLATES
    ]})


@app.route('/api/consequence-simulator', methods=['POST'])
def consequence_simulator():
    """Simulate consequences of inaction."""
    try:
        data = request.get_json(silent=True) or {}
        situation = data.get('situation', '')
        language = data.get('language', 'en')
        
        search_query = preprocess_query_for_rag(situation, language)
        rag_context = ""
        if rights_collection:
            rag_context = retrieve_context(search_query, rights_collection, n_results=4)
        if official_law_collection:
            rag_context += "\n" + retrieve_context(search_query, official_law_collection, n_results=3)

        system_prompt = CONSEQUENCE_PROMPT.format(
            language_instruction=get_language_instruction(language),
            rag_context=rag_context
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"What happens if I do nothing about this situation?\n\n{situation}"}
        ]

        response_text = call_gemma_lang(messages, language, temperature=0.7)

        return jsonify({"response": response_text})
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/rights-card', methods=['POST'])
def rights_card():
    """Generate data for a rights card."""
    try:
        data = request.get_json(silent=True) or {}
        situation = data.get('situation', '')
        advice = data.get('advice', '')
        language = data.get('language', 'en')
        
        messages = [
            {"role": "system", "content": f"""Generate a concise "Know Your Rights" card content based on the situation. Return ONLY valid JSON in this exact format:
{{
  "title": "Your Rights Card Title",
  "situation_summary": "1-2 sentence summary",
  "rights": ["Right 1", "Right 2", "Right 3", "Right 4", "Right 5"],
  "key_sections": ["BNS Section X - Name", "Law Name - Section Y"],
  "urgent_action": "The most important thing to do right now",
  "helplines": ["NALSA: 15100", "Tele-Law: 14454"]
}}

{get_language_instruction(language)}"""},
            {"role": "user", "content": f"Situation: {situation}\n\nAdvice given: {advice}\n\nGenerate the rights card JSON."}
        ]

        response_text = call_gemma_lang(messages, language, temperature=0.3)
        
        # Try to parse JSON from response
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_text = response_text
            if '```json' in json_text:
                json_text = json_text.split('```json')[1].split('```')[0]
            elif '```' in json_text:
                json_text = json_text.split('```')[1].split('```')[0]
            
            card_data = json.loads(json_text.strip())
            return jsonify({"card": card_data})
        except json.JSONDecodeError:
            # If JSON parsing fails, return raw text
            return jsonify({"card": {
                "title": "Your Rights",
                "situation_summary": situation[:100],
                "rights": [advice[:200] if advice else "Contact NALSA at 15100 for free legal aid"],
                "key_sections": [],
                "urgent_action": "Contact a lawyer or call NALSA helpline 15100",
                "helplines": ["NALSA: 15100", "Tele-Law: 14454", "Police: 112", "Women: 181"]
            }})
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
# Law & Next Steps — single verified structured analysis
# ══════════════════════════════════════════════════════════════

NATIONAL_URLS = [
    {"title": "India Code — Bharatiya Nyaya Sanhita / BNSS and all central acts",
     "url": "https://www.indiacode.nic.in"},
    {"title": "NALSA — free legal aid and helpline 15100",
     "url": "https://nalsa.gov.in"},
]

def _official_urls():
    """Every official URL we are willing to show, taken from bundled legal-aid data."""
    urls = [u["url"] for u in NATIONAL_URLS]
    for st in LEGAL_AID_DATA.get('states', []):
        site = (st.get('slsa') or {}).get('website') or st.get('website')
        if site and site not in urls:
            urls.append(site)
    return urls

def _sanitize_sources(sources, rag_context):
    """Deterministic citation guard, ported from Nyaya's verifier.

    A model can produce a confident deep link to a page that does not exist, and a
    fabricated legal citation is exactly the failure this feature exists to prevent.
    So: a URL is shown verbatim only if it appears in data we actually retrieved.
    Anything else collapses to the domain root of a known official site, and an
    unknown host is dropped to India Code. No prompt rule can guarantee this; this
    check can.
    """
    known = set(_official_urls())
    known.update(re.findall(r'https?://[^\s,;"\')<>]+', rag_context or ''))
    roots = {urlparse(u).netloc.lower(): u for u in _official_urls()}

    cleaned = []
    for src in (sources or []):
        if not isinstance(src, dict):
            continue
        title = str(src.get('title') or '').strip() or 'Official source'
        url = str(src.get('url') or '').strip()
        if url not in known:
            # Not something we retrieved — keep the domain if it is official, drop the path.
            url = roots.get(urlparse(url).netloc.lower(), NATIONAL_URLS[0]["url"])
        cleaned.append({"title": title, "url": url})

    # Always leave the person somewhere official to go.
    if not cleaned:
        cleaned = list(NATIONAL_URLS)
    return cleaned

LAW_STEPS_PROMPT = """You are an Indian legal expert producing ONE verified, structured analysis of a citizen's situation. Assert legal provisions (BNS/BNSS/act sections) ONLY if they appear in the CONTEXT below. You may mention a clearly relevant section that is missing from the CONTEXT, but you MUST then mark its verification status as "unverified". Never invent section numbers.

Return ONLY valid JSON (no text before or after) in EXACTLY this shape:
{{
  "situation_and_law": "Markdown. First restate the person's situation in 2-3 plain sentences. Then give the applicable law with specific BNS/BNSS/act section numbers and what each does.",
  "verification": [
    {{"claim": "one legal statement you made above", "supported_by": "which CONTEXT source or section supports it, or 'No retrieved source'", "status": "verified"}}
  ],
  "sources": [
    {{"title": "Bharatiya Nyaya Sanhita, 2023 — Section X", "url": "https://www.indiacode.nic.in"}}
  ],
  "stress_test": {{
    "for": ["arguments that support the person's position"],
    "against": ["arguments the opposing side will make against them"],
    "weaknesses": ["honest weak points in the person's own position"]
  }},
  "rights_card": {{
    "title": "short shareable title",
    "rights": [{{"text": "one right in plain language", "source": "BNS Section X / Act name"}}]
  }},
  "explain_simply": "A short jargon-free paragraph the person can read aloud to family."
}}

RULES:
- Every section number used in situation_and_law MUST also appear as a "verification" entry with a "status" of "verified" (supported by CONTEXT) or "unverified" (not in CONTEXT).
- For "sources" urls use https://www.indiacode.nic.in for any act/section, https://nalsa.gov.in for legal aid, or an official URL copied exactly from the CONTEXT. Never invent a deep link — if unsure of the page, give the domain root.
- Keep each list to 2-5 concise items. Every rights_card right MUST carry a "source".

{language_instruction}

CONTEXT FROM KNOWLEDGE BASE:
{rag_context}
"""

@app.route('/api/law-and-steps', methods=['POST'])
def law_and_steps():
    """Single verified 'Law & Next Steps' analysis with six panels."""
    try:
        data = request.get_json(silent=True) or {}
        situation = data.get('situation', '').strip()
        language = data.get('language', 'en')
        session_id = data.get('session_id', '')

        if not situation:
            return jsonify({"error": "No situation provided"}), 400

        # Retrieve statute chunks WITH their source URLs (official law first, then
        # curated rights knowledge for plain-language grounding).
        search_query = preprocess_query_for_rag(situation, language)
        chunks = []
        chunks += retrieve_chunks(search_query, official_law_collection, n_results=4)
        chunks += retrieve_chunks(search_query, rights_collection, n_results=2)

        language_name = LANGUAGE_NAMES.get(language, 'English')

        def call_llm(messages, temperature=0.2, num_ctx=8192, response_format=None):
            return call_gemma(messages, temperature=temperature, num_ctx=num_ctx,
                              response_format=response_format)

        pipe = run_law_steps(situation, chunks, language_name, call_llm)

        # Assemble the six-panel response the frontend expects, from verified artifacts.
        next_steps = pipe.get('next_steps') or []
        situation_md = pipe.get('situation_and_law', '')
        if next_steps:
            situation_md += "\n\n**What to do next:**\n" + "\n".join(f"- {s}" for s in next_steps)

        verification = []
        for v in pipe.get('verification', []):
            supported = v['status'] == 'supported'
            cited = ', '.join(v.get('cited_chunk_ids') or []) or 'No retrieved source'
            verification.append({
                "claim": v['claim'],
                "supported_by": cited if supported else "Not supported by a retrieved source",
                "status": "verified" if supported else "unverified",
            })

        # Sources already carry only supported-claim URLs; fold act+section into title.
        sources = []
        for s in pipe.get('sources', []):
            title = s.get('act') or s.get('title') or 'Official source'
            if s.get('section'):
                title = f"{title} — {s['section']}"
            sources.append({"title": title, "url": s.get('url', '')})
        rag_urls = " ".join(c.get('official_url', '') for c in chunks)
        sources = _sanitize_sources(sources, rag_urls)

        result = {
            "situation_and_law": situation_md,
            "verification": verification,
            "sources": sources,
            "stress_test": pipe.get('stress_test', {"for": [], "against": [], "weaknesses": []}),
            "rights_card": {
                "title": "Your Rights",
                "rights": pipe.get('rights', []),
            },
            "explain_simply": pipe.get('explain_simply', ''),
        }

        return jsonify({"result": result, "session_id": session_id})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
# Document Drafting Engine
# ══════════════════════════════════════════════════════════════

DRAFTING_PROMPTS = {
    "legal_notice": """Draft a formal LEGAL NOTICE under Indian law. Use the standard format:
- Sender details (via their advocate if applicable), recipient details
- Subject line
- Numbered paragraphs: facts, legal grounds (cite specific acts/BNS sections), demand, deadline (typically 15/30 days), consequence of non-compliance
- Formal closing""",
    "consumer_complaint": """Draft a CONSUMER COMPLAINT for the District Consumer Disputes Redressal Commission under the Consumer Protection Act, 2019. Use the standard format:
- Complainant and Opposite Party details
- Numbered paragraphs: facts, deficiency in service/defect in goods, jurisdiction (pecuniary + territorial), limitation
- Prayer: refund/replacement/compensation with specific amounts
- Verification clause""",
    "rti_application": """Draft an RTI APPLICATION under the Right to Information Act, 2005. Use the standard format:
- To: The Public Information Officer (with department)
- Applicant details
- Clear, specific, numbered information requests (not opinions, only records/information)
- Declaration of citizenship, application fee mention (Rs. 10)
- Note about first appeal rights""",
    "police_complaint": """Draft a POLICE COMPLAINT (for filing an FIR) addressed to the Station House Officer. Use the standard format:
- To: SHO with police station name
- Complainant details
- Chronological numbered facts with dates, times, places, names
- Specific offences with BNS sections
- Request for FIR registration and investigation
- Note: if FIR is refused, mention right to approach SP under BNSS 173(4) or Magistrate under BNSS 175(3)"""
}

DRAFT_SYSTEM_PROMPT = """You are an expert Indian legal drafter. {doc_instruction}

RULES:
- This is the FINAL, submission-ready document. Every detail is provided below — use the exact values given by the user.
- Your output MUST NOT contain any square-bracket placeholders like [NAME] or [ADDRESS]. If a detail is genuinely not provided and cannot be inferred, omit that clause naturally rather than leaving a placeholder.
- Write the document itself in formal {doc_language} (standard for Indian legal documents).
- Cite current laws: BNS (not IPC), BNSS (not CrPC), Consumer Protection Act 2019, etc.
- Format the output as:

## DOCUMENT

[The complete, ready-to-use document]

## HOW TO USE THIS

[Simple explanation in the user's language: where to submit it, what to attach, deadlines, what happens next]

{language_instruction}
"""

DRAFT_SUGGEST_PROMPT = """You are an Indian legal expert helping a citizen choose which document to prepare for their situation.

From the CANDIDATE DOCUMENTS below, choose the 2 to 3 that are most useful for the user's situation. For each, write one short sentence saying why it helps, in the user's language.

Return ONLY valid JSON in exactly this shape:
{{"suggestions": [{{"template_id": "<id from the candidates>", "reason": "<one short sentence>"}}]}}

Only use template_id values that appear in the candidates. Do not invent ids.

CANDIDATE DOCUMENTS:
{candidates}
"""

DRAFT_REQUIREMENTS_PROMPT = """You are helping a citizen fill in the details needed to complete an Indian legal document.

Below is the list of FIELDS the document needs and the user's SITUATION. For each field, return:
- "key": the field name exactly as given
- "label": a short, friendly label in the user's language explaining what to enter
- "prefill": the value for this field if it can be found in the SITUATION, else an empty string
- "required": true for essential fields, false for optional ones

Return ONLY valid JSON in exactly this shape:
{{"fields": [{{"key": "...", "label": "...", "prefill": "...", "required": true}}]}}

FIELDS:
{fields}

SITUATION:
{situation}
"""


@app.route('/api/draft-suggest', methods=['POST'])
def draft_suggest():
    """Given a described situation, suggest which document templates would help."""
    try:
        data = request.get_json(silent=True) or {}
        situation = data.get('situation', '').strip()
        language = data.get('language', 'en')

        if not situation:
            return jsonify({"suggestions": []})

        # RAG shortlist: query the rights_knowledge collection (which indexes the
        # document templates) for the closest template ids.
        candidate_ids = []
        if rights_collection:
            try:
                res = rights_collection.query(
                    query_texts=[preprocess_query_for_rag(situation, language)],
                    n_results=6,
                    where={"doc_type": "template"},
                )
                for meta in (res.get('metadatas') or [[]])[0]:
                    tid = (meta or {}).get('template_id') or (meta or {}).get('id')
                    if tid and tid not in candidate_ids:
                        candidate_ids.append(tid)
            except Exception as e:
                print(f"draft-suggest RAG error: {e}")

        # Fallback / supplement: deterministic keyword match over template titles.
        if len(candidate_ids) < 3:
            sl = situation.lower()
            for tpl in DOCUMENT_TEMPLATES:
                hay = f"{tpl.get('title','')} {tpl.get('when_to_use','')} {tpl.get('category','')}".lower()
                if any(w in hay for w in sl.split() if len(w) > 4):
                    if tpl['id'] not in candidate_ids:
                        candidate_ids.append(tpl['id'])
                if len(candidate_ids) >= 6:
                    break

        candidates = [_get_template(tid) for tid in candidate_ids if _get_template(tid)]
        if not candidates:
            candidates = DOCUMENT_TEMPLATES[:6]

        cand_brief = [
            {"template_id": t['id'], "title": t.get('title', ''),
             "when_to_use": t.get('when_to_use', ''), "category": t.get('category', '')}
            for t in candidates
        ]

        # Let the model pick the best 2-3 with a localized reason.
        suggestions = []
        try:
            system_prompt = DRAFT_SUGGEST_PROMPT.format(
                candidates=json.dumps(cand_brief, ensure_ascii=False)
            )
            raw = call_gemma_lang(
                [{"role": "system", "content": system_prompt},
                 {"role": "user", "content": f"Situation: {situation}"}],
                language, temperature=0.3, response_format='json'
            )
            parsed = json.loads(raw)
            valid_ids = {t['id'] for t in candidates}
            for s in parsed.get('suggestions', []):
                tid = s.get('template_id')
                if tid in valid_ids:
                    tpl = _get_template(tid)
                    suggestions.append({
                        "template_id": tid,
                        "title": tpl.get('title', ''),
                        "title_hi": tpl.get('title_hi', ''),
                        "category": tpl.get('category', ''),
                        "when_to_use": tpl.get('when_to_use', ''),
                        "reason": s.get('reason', ''),
                    })
        except Exception as e:
            print(f"draft-suggest LLM error: {e}")

        # Fallback: return top-3 candidates without a reason if the model failed.
        if not suggestions:
            for t in candidates[:3]:
                suggestions.append({
                    "template_id": t['id'], "title": t.get('title', ''),
                    "title_hi": t.get('title_hi', ''), "category": t.get('category', ''),
                    "when_to_use": t.get('when_to_use', ''), "reason": t.get('when_to_use', ''),
                })

        return jsonify({"suggestions": suggestions})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/draft-requirements', methods=['POST'])
def draft_requirements():
    """Return the fields needed to complete a chosen template, prefilled from the
    situation where possible so the user is only asked for what is missing."""
    try:
        data = request.get_json(silent=True) or {}
        template_id = data.get('template_id', '')
        situation = data.get('situation', '')
        language = data.get('language', 'en')

        tpl = _get_template(template_id)
        # The 4 hardcoded doc types aren't in document_templates.json; give them a
        # sensible generic field set.
        placeholders = _template_placeholders(template_id)
        if not placeholders:
            placeholders = ["YOUR NAME", "YOUR ADDRESS", "OTHER PARTY NAME",
                            "OTHER PARTY ADDRESS", "DATE", "DETAILS OF THE MATTER"]

        fields = []
        try:
            system_prompt = DRAFT_REQUIREMENTS_PROMPT.format(
                fields=json.dumps(placeholders, ensure_ascii=False),
                situation=situation or "(not provided)"
            )
            raw = call_gemma_lang(
                [{"role": "system", "content": system_prompt},
                 {"role": "user", "content": "Return the fields JSON."}],
                language, temperature=0.2, response_format='json'
            )
            parsed = json.loads(raw)
            valid = {p.upper() for p in placeholders}
            for f in parsed.get('fields', []):
                if (f.get('key') or '').upper() in valid:
                    fields.append({
                        "key": f.get('key'),
                        "label": f.get('label') or f.get('key'),
                        "prefill": f.get('prefill', '') or '',
                        "required": bool(f.get('required', True)),
                    })
        except Exception as e:
            print(f"draft-requirements LLM error: {e}")

        # Fallback: use the raw placeholders as labels.
        if not fields:
            fields = [{"key": p, "label": p.title(), "prefill": "", "required": True}
                      for p in placeholders]

        return jsonify({
            "template": {
                "id": template_id,
                "title": (tpl or {}).get('title', template_id),
                "title_hi": (tpl or {}).get('title_hi', ''),
            },
            "fields": fields,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/draft-document', methods=['POST'])
def draft_document():
    """Generate a final, submission-ready legal document from structured fields."""
    try:
        data = request.get_json(silent=True) or {}
        doc_type = data.get('doc_type', 'legal_notice')
        fields = data.get('fields', {})
        situation = data.get('situation', '')
        language = data.get('language', 'en')

        # Validate that required fields are present. Required = the template's
        # placeholders (minus any the requirements step marked optional, which the
        # client omits from `fields`). If the client sends explicit blanks, flag them.
        missing = [k for k, v in fields.items() if not str(v).strip()]
        if missing:
            return jsonify({"missing": missing}), 422

        # Hardcoded prompt first; otherwise synthesise an instruction from a
        # matching document template (the ~45 in document_templates.json).
        doc_instruction = DRAFTING_PROMPTS.get(doc_type)
        if not doc_instruction:
            doc_instruction = _template_instruction(doc_type) or DRAFTING_PROMPTS['legal_notice']
        doc_language = LANGUAGE_NAMES.get(language, 'English')

        system_prompt = DRAFT_SYSTEM_PROMPT.format(
            doc_instruction=doc_instruction,
            doc_language=doc_language,
            language_instruction=get_language_instruction(language)
        )

        fields_text = "\n".join(f"- {k}: {v}" for k, v in fields.items() if v)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Draft the document with these details:\n{fields_text}\n\nSituation description:\n{situation}"}
        ]

        response_text = call_gemma_lang(messages, language, temperature=0.4, num_ctx=4096)

        # Self-repair: if the model still left [PLACEHOLDERS], ask it once to fix them.
        leftover = re.findall(r'\[[A-Z][^\]]{2,}\]', response_text)
        if leftover:
            repair = messages + [
                {"role": "assistant", "content": response_text},
                {"role": "user", "content":
                    "You left these placeholders unfilled: " + ", ".join(leftover[:10]) +
                    ". Rewrite the full document using the details already provided, and "
                    "remove any remaining square-bracket placeholders (omit the clause if "
                    "the detail is truly unavailable)."},
            ]
            try:
                response_text = call_gemma_lang(repair, language, temperature=0.3, num_ctx=4096)
            except Exception as e:
                print(f"draft repair error: {e}")

        return jsonify({"response": response_text})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
# Virtual Courtroom
# ══════════════════════════════════════════════════════════════

COURTROOM_PROMPT = """You are simulating an Indian courtroom hearing (moot court) focusing on legal arguments.

ROLES:
1. YOUR_LAWYER: Human-like advocate arguing FOR the citizen. Highly knowledgeable in law, IPC, BNS, BNSS, articles, and rights. Argues fiercely with the opposing lawyer.
2. OPPOSING_LAWYER: Human-like advocate arguing AGAINST the citizen. Equally knowledgeable and fiercely opposes YOUR_LAWYER.
3. NEXT_STEPS: Practical, concise advice on what the citizen should do next before actual legal proceedings.

RULES FOR THE HEARING:
- This is a continuous debate. The lawyers must exchange arguments back-and-forth for about 5-6 total lines of argument.
- Keep each response concise.
- At the end, provide clear next steps for the user.
- Use the exact markers below for each speaker.

OUTPUT FORMAT (strict):
[YOUR_LAWYER]
(concise argument)
[OPPOSING_LAWYER]
(concise rebuttal)
[YOUR_LAWYER]
(concise counter-argument)
[OPPOSING_LAWYER]
(concise counter-rebuttal)
[NEXT_STEPS]
(concise next steps)

IMPORTANT LANGUAGE INSTRUCTION:
{language_instruction}
ALL dialogue from YOUR_LAWYER, OPPOSING_LAWYER, and NEXT_STEPS must strictly be in this requested language. Do NOT use English if another language is requested.

CASE CONTEXT:
{rag_context}
"""

@app.route('/api/courtroom', methods=['POST'])
def courtroom():
    """Virtual courtroom simulation — three AI roles per round."""
    try:
        data = request.get_json(silent=True) or {}
        situation = data.get('situation', '')
        language = data.get('language', 'en')

        rag_context = ""
        if rights_collection:
            rag_context = retrieve_context(situation, rights_collection, n_results=3)

        system_prompt = COURTROOM_PROMPT.format(
            language_instruction=get_language_instruction(language),
            rag_context=rag_context
        )

        user_content = f"The citizen's case:\n{situation}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        # Bump temperature slightly for more variety
        response_text = call_gemma_lang(messages, language, temperature=0.9)

        # Parse the sequence of messages from the marked response
        import re
        pattern = r"\[(YOUR_LAWYER|OPPOSING_LAWYER|NEXT_STEPS)\]\s*(.*?)(?=\[(?:YOUR_LAWYER|OPPOSING_LAWYER|NEXT_STEPS)\]|$)"
        matches = re.finditer(pattern, response_text, re.DOTALL)
        
        messages_list = []
        for m in matches:
            role = m.group(1)
            text = m.group(2).strip()
            if text:
                messages_list.append({"role": role, "text": text})
        
        # Fallback if parsing failed
        if not messages_list:
            messages_list.append({"role": "NEXT_STEPS", "text": response_text})

        return jsonify({"messages": messages_list, "raw": response_text})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
# Offline Multilingual TTS (Facebook MMS-TTS via transformers)
# ══════════════════════════════════════════════════════════════
# Browser Web Speech API only speaks languages the OS has voices for, so
# non-English voices are silent on most Windows machines. MMS-TTS runs the
# synthesis server-side (CPU-only OK) and covers every app language.
#
# Models download once from Hugging Face, then run fully offline. To
# pre-download them (e.g. before going offline), run:
#   python -c "from transformers import VitsModel, AutoTokenizer; \\
#     [ (VitsModel.from_pretrained(m), AutoTokenizer.from_pretrained(m)) \\
#       for m in set(__import__('app').MMS_TTS_MODELS.values()) ]"

MMS_TTS_MODELS = {
    'en': 'facebook/mms-tts-eng',
    'hi': 'facebook/mms-tts-hin',
    'hinglish': 'facebook/mms-tts-hin',
    'ta': 'facebook/mms-tts-tam',
    'te': 'facebook/mms-tts-tel',
    'bn': 'facebook/mms-tts-ben',
    'mr': 'facebook/mms-tts-mar',
    'gu': 'facebook/mms-tts-guj',
    'kn': 'facebook/mms-tts-kan',
    'ml': 'facebook/mms-tts-mal',
    'pa': 'facebook/mms-tts-pan',
}

TTS_MAX_CHARS = 800  # ponytail: naive truncation; chunk+concat if long answers get cut off

# Lazily loaded + cached VitsModel/tokenizer, keyed by HF model id
_tts_models = {}

def get_tts_model(language):
    """Load (and cache) the MMS-TTS model for an app language code. Lazy — never at startup.

    Romanized variants (hinglish, tanglish, ...) fall back to their base language's
    voice — MMS tokenizers uroman-normalize Roman input, so this works well."""
    model_id = MMS_TTS_MODELS.get(language) or MMS_TTS_MODELS.get(base_lang(language), MMS_TTS_MODELS['en'])
    if model_id not in _tts_models:
        from transformers import VitsModel, AutoTokenizer
        print(f"⏳ Loading TTS model {model_id} (first use — may download)...")
        model = VitsModel.from_pretrained(model_id)
        model.eval()
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        _tts_models[model_id] = (model, tokenizer)
        print(f"✅ TTS model {model_id} ready")
    return _tts_models[model_id]

@app.route('/api/tts', methods=['POST'])
def tts():
    """Synthesize speech offline with MMS-TTS. Returns raw WAV (audio/wav) or JSON error."""
    try:
        data = request.get_json(silent=True) or {}
        text = (data.get('text') or '').strip()[:TTS_MAX_CHARS]
        language = data.get('language', 'en')
        if not text:
            return jsonify({"error": "No text provided"}), 400

        import io
        import numpy as np
        import torch
        from scipy.io.wavfile import write as wav_write

        model, tokenizer = get_tts_model(language)
        inputs = tokenizer(text, return_tensors="pt")
        with torch.no_grad():
            waveform = model(**inputs).waveform.squeeze().cpu().numpy()

        # float32 [-1,1] -> int16 PCM for broad browser <audio> compatibility
        pcm16 = (np.clip(waveform, -1.0, 1.0) * 32767).astype(np.int16)
        buf = io.BytesIO()
        wav_write(buf, model.config.sampling_rate, pcm16)
        from flask import Response
        return Response(buf.getvalue(), mimetype='audio/wav')

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
# Offline Speech-to-Text (faster-whisper)
# ══════════════════════════════════════════════════════════════
# The browser records raw audio with MediaRecorder and POSTs it here; we
# transcribe locally with faster-whisper so nothing leaves the machine and
# every Indian language is supported (unlike the browser Web Speech API).
#
# The "small" model (~460 MB) downloads once from Hugging Face, then runs fully
# offline on CPU. Pre-download: python -c "from faster_whisper import WhisperModel; WhisperModel('small')"

# Cap request bodies so a huge upload can't exhaust memory (shared with OCR uploads).
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25 MB

_whisper_model = None

def get_whisper_model():
    """Load (and cache) the faster-whisper model. Lazy — never at startup."""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        print("⏳ Loading faster-whisper 'small' model (first use — may download)...")
        _whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
        print("✅ Whisper model ready")
    return _whisper_model


@app.route('/api/transcribe', methods=['POST'])
def transcribe():
    """Transcribe a recorded audio blob to text with offline faster-whisper.

    multipart/form-data: audio=<blob>, language=<app language code>.
    Native language codes hint whisper to that language; romanized variants use
    auto-detection (the user is speaking the base language, written back in Roman)."""
    try:
        if 'audio' not in request.files:
            return jsonify({"error": "No audio uploaded"}), 400

        language = request.form.get('language', 'en')
        # Romanized variants → auto-detect; native codes → hint the base language.
        whisper_lang = None if language in ROMANIZED_LANGS else base_lang(language)

        import io
        audio_bytes = request.files['audio'].read()
        if not audio_bytes:
            return jsonify({"error": "Empty audio"}), 400

        model = get_whisper_model()
        segments, info = model.transcribe(
            io.BytesIO(audio_bytes),
            language=whisper_lang,
            beam_size=1,
            vad_filter=True,
        )
        text = "".join(seg.text for seg in segments).strip()

        return jsonify({
            "text": text,
            "detected_language": getattr(info, 'language', whisper_lang or ''),
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════════╗
    ║         अधिKaar — AI Legal Assistant         ║
    ║      Empowering Every Citizen with Rights     ║
    ╚══════════════════════════════════════════════╝
    """)
    print(f"  Model: {GEMMA_MODEL_PREFERRED} (or fallback)")
    print(f"  RAG DB: {CHROMA_DIR}")
    print(f"  Server: http://localhost:5000")
    print(f"  Make sure Ollama is running: ollama serve")
    print(f"  Make sure model is pulled: ollama pull {GEMMA_MODEL_PREFERRED}")
    print()
    
    app.run(debug=True, host='0.0.0.0', port=5000)