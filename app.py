"""
अधिKaar — AI Legal Assistant for Every Indian Citizen
Flask Backend with Gemma 4 via Ollama + ChromaDB RAG
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import ollama
import chromadb
from chromadb.utils import embedding_functions
import json
import os
import sys
import uuid
import traceback

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

def retrieve_context(query, collection, n_results=3, max_chars=1200):
    """Retrieve relevant documents from ChromaDB, capped to avoid context overflow."""
    if collection is None:
        return ""
    try:
        results = collection.query(query_texts=[query], n_results=n_results)
        docs = results.get('documents', [[]])[0]
        return "\n".join(docs)[:max_chars]
    except Exception as e:
        print(f"RAG retrieval error: {e}")
        return ""

# ══════════════════════════════════════════════════════════════
# System Prompts
# ══════════════════════════════════════════════════════════════

LANGUAGE_INSTRUCTIONS = {
    "default": "Automatically detect the language of the user's latest query and respond entirely in that language without any emojis."
}

MAIN_SYSTEM_PROMPT = """You are an extremely knowledgeable human legal expert with an encyclopedic understanding of all legal and illegal cases, rights, and Indian law. Your purpose is to provide clear, concise, and direct legal advice. 

CRITICAL BEHAVIOR RULES:

1. **NO AI DISCLAIMERS (STRICT MANDATE)**: NEVER reveal, hint, or say that you are an AI, a chatbot, or a language model. You are a real human legal expert. If asked, you are a human lawyer providing counsel.

2. **CONCISE & CLEAR**: Your answers must be concise, perfectly clear, and directly address the user's issues without any robotic fluff. Talk like a real human in natural paragraphs. DO NOT use emojis. DO NOT use bullet points or markdown headers. Convey your response in a human way only, in paragraphs or concise lines.

3. **CONFIRMATION LOOP**: Before giving ANY legal advice, you MUST FIRST restate the user's situation in simple language and ask for confirmation.
   Format:
   Let me make sure I understand your situation:
   [Your understanding of their situation in 2-3 simple sentences]
   Is this correct? If I've misunderstood anything, please tell me.
   Only give advice AFTER the user confirms. If they correct you, restate with the correction.

4. **POWER-IMBALANCE DETECTION**: Analyze the situation for power imbalances. When detected, weave protective advice naturally into your response without making a separate section.

5. **RESPONSE STYLE** (after confirmation):
   Address their rights, what they should do, important deadlines, and protective advisory naturally within your conversational paragraphs. Do not start with helpline calls. Do not use structural headers. Do not use bullet points. Keep it as a normal human-to-human conversation.

6. **LEGAL REFERENCES**: Always cite specific law sections using BNS (Bharatiya Nyaya Sanhita) numbers. If the user mentions old IPC sections, explain the new BNS equivalent.

7. **TONE**: Be confident, clear, and professional like a top-tier lawyer. Reassure the user that they have rights and options.

8. **SAFETY FIRST**: If the situation involves immediate physical danger, weave safety advice and emergency numbers (112 for police, 181 for women helpline) naturally into your first paragraph.

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
    """Get dynamic language instruction."""
    return LANGUAGE_INSTRUCTIONS['default']

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
    """Main conversation endpoint with confirmation loop and power-imbalance detection."""
    try:
        data = request.get_json(silent=True) or {}
        message = data.get('message', '')
        language = data.get('language', 'en')
        session_id = data.get('session_id', str(uuid.uuid4()))
        
        session = get_session(session_id)
        
        # Retrieve relevant context from RAG
        rag_context = ""
        if rights_collection:
            rag_context += retrieve_context(message, rights_collection, n_results=2)
        if ipc_bns_collection:
            rag_context += "\n" + retrieve_context(message, ipc_bns_collection, n_results=2)
        
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

COURTROOM_PROMPT = """You are simulating an Indian courtroom hearing (moot court) to help a citizen prepare their case. You play THREE roles in each round:

1. USER'S LAWYER (advocate arguing FOR the citizen)
2. OPPOSING LAWYER (advocate arguing AGAINST the citizen)
3. JUDGE (neutral, asks probing questions, notes strong/weak points)

This is round {round_num} of 3.
- Round 1: Opening arguments from both sides, judge frames the key issues.
- Round 2: Rebuttals with specific law citations (BNS/relevant acts) and precedents, judge questions the weakest claims.
- Round 3: Closing arguments, then the judge gives a REALISTIC ASSESSMENT: likely outcome, strength of the citizen's case (out of 10), and what evidence would most improve it.

Cite real Indian laws with sections. Be realistic — do not simply favor the citizen.

OUTPUT FORMAT — use these exact markers, each on its own line:
[YOUR_LAWYER]
(argument)
[OPPOSING_LAWYER]
(argument)
[JUDGE]
(remarks)

{language_instruction}

CASE CONTEXT:
{rag_context}
"""

@app.route('/api/courtroom', methods=['POST'])
def courtroom():
    """Virtual courtroom simulation — three AI roles per round."""
    try:
        data = request.get_json(silent=True) or {}
        situation = data.get('situation', '')
        round_num = int(data.get('round', 1))
        history = data.get('history', '')
        language = data.get('language', 'en')

        rag_context = ""
        if rights_collection:
            rag_context = retrieve_context(situation, rights_collection, n_results=3)

        system_prompt = COURTROOM_PROMPT.format(
            round_num=round_num,
            language_instruction=get_language_instruction(language),
            rag_context=rag_context
        )

        user_content = f"The citizen's case:\n{situation}"
        if history:
            user_content += f"\n\nPrevious rounds:\n{history}\n\nNow produce round {round_num}."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        response_text = call_gemma(messages, temperature=0.8)

        # Parse the three roles from the marked response
        import re
        def extract(marker, text):
            pattern = rf"\[{marker}\]\s*(.*?)(?=\[(?:YOUR_LAWYER|OPPOSING_LAWYER|JUDGE)\]|$)"
            m = re.search(pattern, text, re.DOTALL)
            return m.group(1).strip() if m else ""

        parsed = {
            "your_lawyer": extract("YOUR_LAWYER", response_text),
            "opposing_lawyer": extract("OPPOSING_LAWYER", response_text),
            "judge": extract("JUDGE", response_text),
        }
        # Fallback: if parsing failed, put everything in judge
        if not any(parsed.values()):
            parsed["judge"] = response_text

        return jsonify({"round": round_num, "roles": parsed, "raw": response_text})

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