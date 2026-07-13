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
    
    if language not in ['en', 'hinglish'] and query_expanded == query:
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
    "default": "Automatically detect the language of the user's latest query and respond entirely in that language without any emojis."
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

CONSEQUENCE_PROMPT = """Based on the user's legal situation, model what happens if they take NO ACTION at all. Present as a realistic timeline with specific legal consequences. Do not use any emojis. Convey the timeline in simple paragraphs.

Timeline of Inaction:
Immediate (0-7 days): [What happens right away if nothing is done]
Short term (1-4 weeks): [Legal implications, missed opportunities]
Medium term (1-6 months): [Escalation, potential consequences]
Long term (6+ months): [Worst-case scenarios, rights that expire]
Worst Case Scenario: [The absolute worst outcome]
Most Urgent Action: [The single most important thing to do RIGHT NOW]

Be specific about Indian law — mention actual deadlines, limitation periods, and legal consequences. Don't be alarmist but be honest about real risks. Write in clear, concise human paragraphs.

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

FORMAT (No emojis, simple text):
Community Helper Summary

Person's Situation: [1-2 sentences]
Their Rights: [3-5 sentences]
What To Do: [Numbered steps]
Legal Sections: [Relevant BNS sections]
Helpline Numbers: [Numbers]

{language_instruction}

SITUATION AND ADVICE TO SIMPLIFY:
{context}
"""

DOCUMENT_TRANSLATE_PROMPT = """The user has a legal document (FIR, court notice, legal notice, summons, etc.) and needs it explained in plain language. The OCR text of the document is provided below.

YOUR TASKS:
1. Identify the document type (FIR, legal notice, court summons, etc.)
2. Translate/explain the document in plain, simple language
3. Highlight key information (Important dates and deadlines, Who is involved, What legal sections are mentioned, What action is required, By when must they respond/appear)
4. What should the reader do next — clear, actionable steps

IMPORTANT: Many legal documents are in English or formal Hindi/Urdu legal language. Translate into the user's preferred language using simple, everyday words. DO NOT use any emojis. Present the explanation in natural paragraphs.

{language_instruction}

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

def call_gemma(messages, temperature=0.7, fallback_cpu=False):
    """Call the working LLM model via Ollama (auto-detected at first call)."""
    model = get_working_model()
    total_chars = sum(len(m["content"]) for m in messages)
    print(f"[call_gemma] model={model} messages={len(messages)} chars={total_chars}")
    try:
        options = {
            'temperature': temperature,
            'num_ctx': 2048,   # keep context window small to avoid GGML_SCHED_MAX_SPLIT_INPUTS crash
        }
        if fallback_cpu:
            options['num_gpu'] = 0
            
        response = ollama.chat(
            model=model,
            messages=messages,
            options=options
        )
        return response['message']['content']
    except Exception as e:
        error_msg = str(e)
        # If it's a CUDA crash or buffer overrun, try again forcing CPU mode
        if not fallback_cpu and ("CUDA error" in error_msg or "exit status" in error_msg or "0xc0000409" in error_msg):
            print(f"⚠️ GPU crash detected ({error_msg}). Retrying in CPU mode...")
            return call_gemma(messages, temperature, fallback_cpu=True)
            
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

@app.route('/api/languages', methods=['GET'])
def get_languages():
    """Return supported languages."""
    languages = [
        {"code": "en", "name": "English", "native": "English", "speech_code": "en-IN"},
        {"code": "hi", "name": "Hindi", "native": "हिन्दी", "speech_code": "hi-IN"},
        {"code": "ta", "name": "Tamil", "native": "தமிழ்", "speech_code": "ta-IN"},
        {"code": "te", "name": "Telugu", "native": "తెలుగు", "speech_code": "te-IN"},
        {"code": "bn", "name": "Bengali", "native": "বাংলা", "speech_code": "bn-IN"},
        {"code": "mr", "name": "Marathi", "native": "मराठी", "speech_code": "mr-IN"},
        {"code": "gu", "name": "Gujarati", "native": "ગુજરાતી", "speech_code": "gu-IN"},
        {"code": "kn", "name": "Kannada", "native": "ಕನ್ನಡ", "speech_code": "kn-IN"},
        {"code": "ml", "name": "Malayalam", "native": "മലയാളം", "speech_code": "ml-IN"},
        {"code": "pa", "name": "Punjabi", "native": "ਪੰਜਾਬੀ", "speech_code": "pa-IN"},
        {"code": "hinglish", "name": "Hinglish", "native": "Hinglish", "speech_code": "hi-IN"}
    ]
    return jsonify({"languages": languages})


@app.route('/api/chat', methods=['POST'])
def chat():
    """Main conversation endpoint with RAG context and dynamic intent detection."""
    try:
        data = request.get_json(silent=True) or {}
        message = data.get('message', '')
        language = data.get('language', 'en')
        session_id = data.get('session_id', str(uuid.uuid4()))
        
        session = get_session(session_id)
        
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
        response_text = call_gemma(messages, temperature=0.7)
        
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
        
        response_text = call_gemma(messages, temperature=0.8)
        
        return jsonify({"response": response_text})
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/bns-convert', methods=['POST'])
def bns_convert():
    """IPC ↔ BNS section converter."""
    try:
        data = request.get_json(silent=True) or {}
        query = data.get('query', '').strip()
        direction = data.get('direction', 'ipc_to_bns')  # or 'bns_to_ipc'
        
        if not query:
            return jsonify({"results": [], "ai_explanation": ""})
        
        # Search in static data strictly
        results = []
        query_lower = query.lower()
        
        for entry in IPC_BNS_DATA:
            match = False
            if direction == 'ipc_to_bns':
                # Strictly convert typed value
                if query_lower == entry.get('ipc_section', '').lower():
                    match = True
            else:
                # Strictly convert typed value
                if query_lower == entry.get('bns_section', '').lower():
                    match = True
            
            if match:
                results.append(entry)
        
        # Get AI explanation if results found, no RAG to keep it strict
        ai_explanation = ""
        if results:
            messages = [
                {"role": "system", "content": "You are a legal expert on Indian criminal law. Explain the IPC to BNS conversion briefly and clearly. Highlight any important changes in the new law. Do not use emojis."},
                {"role": "user", "content": f"User searched for: '{query}'. Found matches: {json.dumps(results[:3], ensure_ascii=False)}. Explain the conversion briefly in simple paragraphs."}
            ]
            ai_explanation = call_gemma(messages, temperature=0.5)
        
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

        if not query:
            return jsonify({"results": [], "ai_explanation": ""})

        src = 'crpc_section' if direction == 'crpc_to_bnss' else 'bnss_section'
        query_lower = query.lower()

        results = [e for e in BNSS_CRPC_DATA if query_lower == e.get(src, '').lower()]

        ai_explanation = ""
        if results:
            messages = [
                {"role": "system", "content": "You are a legal expert on Indian criminal procedure. Explain the CrPC (1973) to BNSS (2023) conversion briefly and clearly. Highlight any important procedural changes in the new law. Do not use emojis."},
                {"role": "user", "content": f"User searched for: '{query}'. Found matches: {json.dumps(results[:3], ensure_ascii=False)}. Explain the conversion briefly in simple paragraphs."}
            ]
            ai_explanation = call_gemma(messages, temperature=0.5)

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
        
        system_prompt = DOCUMENT_TRANSLATE_PROMPT.format(
            language_instruction=get_language_instruction(language),
            document_text=document_text
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Please explain this legal document to me in simple words:\n\n{document_text}"}
        ]
        
        response_text = call_gemma(messages, temperature=0.5)
        
        return jsonify({"response": response_text})
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


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

        # 2-3 line plain-language summary
        summary = ""
        try:
            messages = [
                {"role": "system", "content":
                    "You are a legal expert. Summarize the following document in 2-3 short, "
                    "plain-language lines so a citizen understands what it is about. Do not use emojis. "
                    + get_language_instruction(language)},
                {"role": "user", "content": text[:4000]}
            ]
            summary = call_gemma(messages, temperature=0.3).strip()
        except Exception as e:
            print(f"Doc summary error: {e}")

        return jsonify({
            "doc_id": doc_id,
            "filename": filename,
            "summary": summary,
            "chunks": len(chunks)
        })

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


@app.route('/api/panchayat-bridge', methods=['POST'])
def panchayat_bridge():
    """Generate elder-friendly explanation for community intermediaries."""
    try:
        data = request.get_json(silent=True) or {}
        situation = data.get('situation', '')
        advice = data.get('advice', '')
        language = data.get('language', 'en')
        
        context = f"Situation: {situation}\n\nAdvice given: {advice}"
        
        system_prompt = PANCHAYAT_BRIDGE_PROMPT.format(
            language_instruction=get_language_instruction(language),
            context=context
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Create a simplified explanation for a community elder/helper:\n\n{context}"}
        ]
        
        response_text = call_gemma(messages, temperature=0.5)
        
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
        
        rag_context = ""
        if rights_collection:
            rag_context = retrieve_context(situation, rights_collection, n_results=5)
        
        system_prompt = CHECKLIST_PROMPT.format(
            language_instruction=get_language_instruction(language),
            rag_context=rag_context
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Generate a comprehensive rights checklist for this situation:\n\n{situation}"}
        ]
        
        response_text = call_gemma(messages, temperature=0.5)
        
        return jsonify({"response": response_text})
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/consequence-simulator', methods=['POST'])
def consequence_simulator():
    """Simulate consequences of inaction."""
    try:
        data = request.get_json(silent=True) or {}
        situation = data.get('situation', '')
        language = data.get('language', 'en')
        
        rag_context = ""
        if rights_collection:
            rag_context = retrieve_context(situation, rights_collection, n_results=5)
        
        system_prompt = CONSEQUENCE_PROMPT.format(
            language_instruction=get_language_instruction(language),
            rag_context=rag_context
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"What happens if I do nothing about this situation?\n\n{situation}"}
        ]
        
        response_text = call_gemma(messages, temperature=0.7)
        
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
        
        response_text = call_gemma(messages, temperature=0.3)
        
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

        # Retrieve grounding context from all three collections + in-memory boosters
        search_query = preprocess_query_for_rag(situation, language)
        rag_context = ""
        if ipc_bns_collection:
            rag_context += retrieve_context(search_query, ipc_bns_collection, n_results=3)
        if rights_collection:
            rag_context += "\n" + retrieve_context(search_query, rights_collection, n_results=3)
        if legal_aid_collection:
            rag_context += "\n" + retrieve_context(search_query, legal_aid_collection, n_results=2)

        extra_bns = check_section_keywords(situation)
        if extra_bns:
            rag_context += "\n" + extra_bns
        extra_rights = check_case_type_keywords(situation)
        if extra_rights and extra_rights[:100] not in rag_context:
            rag_context += "\n" + extra_rights

        system_prompt = LAW_STEPS_PROMPT.format(
            language_instruction=get_language_instruction(language),
            rag_context=rag_context or "(no matching sources retrieved)"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Situation:\n{situation}\n\nProduce the verified JSON analysis."}
        ]

        response_text = call_gemma(messages, temperature=0.3)

        # Parse JSON (handle markdown code fences, same approach as rights-card)
        json_text = response_text
        if '```json' in json_text:
            json_text = json_text.split('```json')[1].split('```')[0]
        elif '```' in json_text:
            json_text = json_text.split('```')[1].split('```')[0]

        try:
            result = json.loads(json_text.strip())
        except json.JSONDecodeError:
            # Fail soft: at least show the model's prose in panel (a)
            result = {
                "situation_and_law": response_text,
                "verification": [],
                "sources": [],
                "stress_test": {"for": [], "against": [], "weaknesses": []},
                "rights_card": {"title": "Your Rights", "rights": []},
                "explain_simply": ""
            }

        # No citation reaches the user without passing the deterministic guard.
        result["sources"] = _sanitize_sources(result.get("sources"), rag_context)

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
- Use the exact details provided by the user. Where a required detail is missing, insert a clear placeholder like [YOUR FULL ADDRESS].
- Write the document itself in formal {doc_language} (standard for Indian legal documents).
- Cite current laws: BNS (not IPC), BNSS (not CrPC), Consumer Protection Act 2019, etc.
- Format the output as:

## 📄 DOCUMENT

[The complete, ready-to-use document]

## 📝 HOW TO USE THIS

[Simple explanation in the user's language: where to submit it, what to attach, deadlines, what happens next]

{language_instruction}
"""

@app.route('/api/draft-document', methods=['POST'])
def draft_document():
    """Generate a formatted legal document from structured fields."""
    try:
        data = request.get_json(silent=True) or {}
        doc_type = data.get('doc_type', 'legal_notice')
        fields = data.get('fields', {})
        situation = data.get('situation', '')
        language = data.get('language', 'en')

        doc_instruction = DRAFTING_PROMPTS.get(doc_type, DRAFTING_PROMPTS['legal_notice'])
        doc_language = 'Hindi' if language == 'hi' else 'English'

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

        response_text = call_gemma(messages, temperature=0.4)
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
        response_text = call_gemma(messages, temperature=0.9)

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
    """Load (and cache) the MMS-TTS model for an app language code. Lazy — never at startup."""
    model_id = MMS_TTS_MODELS.get(language, MMS_TTS_MODELS['en'])
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