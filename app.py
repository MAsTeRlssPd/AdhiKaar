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
import uuid
import traceback

# ══════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

GEMMA_MODEL = 'gemma4'
CHROMA_DIR = os.path.join(os.path.dirname(__file__), 'chroma_db')
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

# In-memory session storage
sessions = {}

# ══════════════════════════════════════════════════════════════
# Load Static Data
# ══════════════════════════════════════════════════════════════

def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

IPC_BNS_DATA = load_json('ipc_bns_mapping.json')
LEGAL_AID_DATA = load_json('legal_aid_directory.json')
RIGHTS_DATA = load_json('rights_knowledge.json')

# ══════════════════════════════════════════════════════════════
# Initialize RAG (ChromaDB)
# ══════════════════════════════════════════════════════════════

ef = embedding_functions.DefaultEmbeddingFunction()
chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)

try:
    ipc_bns_collection = chroma_client.get_collection("ipc_bns", embedding_function=ef)
    rights_collection = chroma_client.get_collection("rights_knowledge", embedding_function=ef)
    legal_aid_collection = chroma_client.get_collection("legal_aid", embedding_function=ef)
    print("✅ ChromaDB collections loaded")
except Exception as e:
    print(f"⚠️ ChromaDB collections not found. Run rag_setup.py first. Error: {e}")
    ipc_bns_collection = None
    rights_collection = None
    legal_aid_collection = None

# ══════════════════════════════════════════════════════════════
# RAG Helper
# ══════════════════════════════════════════════════════════════

def retrieve_context(query, collection, n_results=5):
    """Retrieve relevant documents from ChromaDB."""
    if collection is None:
        return ""
    try:
        results = collection.query(query_texts=[query], n_results=n_results)
        docs = results.get('documents', [[]])[0]
        return "\n".join(docs)
    except Exception as e:
        print(f"RAG retrieval error: {e}")
        return ""

# ══════════════════════════════════════════════════════════════
# System Prompts
# ══════════════════════════════════════════════════════════════

LANGUAGE_INSTRUCTIONS = {
    "en": "Respond in clear, simple English. Avoid legal jargon — explain any technical terms in everyday words.",
    "hi": "कृपया सरल हिंदी में जवाब दें। कानूनी शब्दों को आम भाषा में समझाएं। Respond in simple Hindi.",
    "ta": "எளிய தமிழில் பதிலளிக்கவும். சட்ட சொற்களை எளிய வார்த்தைகளில் விளக்கவும். Respond in simple Tamil.",
    "te": "సరళమైన తెలుగులో సమాధానం ఇవ్వండి. చట్టపరమైన పదాలను సాధారణ పదాలలో వివరించండి. Respond in simple Telugu.",
    "bn": "সরল বাংলায় উত্তর দিন। আইনি শব্দগুলি সাধারণ ভাষায় ব্যাখ্যা করুন। Respond in simple Bengali.",
    "mr": "कृपया सोप्या मराठीत उत्तर द्या। कायदेशीर शब्दांना सोप्या शब्दांत समजावून सांगा. Respond in simple Marathi.",
    "gu": "કૃપા કરીને સરળ ગુજરાતીમાં જવાબ આપો. કાનૂની શબ્દોને સરળ ભાષામાં સમજાવો. Respond in simple Gujarati.",
    "kn": "ಸರಳ ಕನ್ನಡದಲ್ಲಿ ಉತ್ತರಿಸಿ. ಕಾನೂನು ಪದಗಳನ್ನು ಸಾಮಾನ್ಯ ಭಾಷೆಯಲ್ಲಿ ವಿವರಿಸಿ. Respond in simple Kannada.",
    "ml": "ലളിതമായ മലയാളത്തിൽ ഉത്തരം നൽകുക. നിയമ പദങ്ങൾ സാധാരണ ഭാഷയിൽ വിശദീകരിക്കുക. Respond in simple Malayalam.",
    "pa": "ਕਿਰਪਾ ਕਰਕੇ ਸਰਲ ਪੰਜਾਬੀ ਵਿੱਚ ਜਵਾਬ ਦਿਓ। ਕਾਨੂੰਨੀ ਸ਼ਬਦਾਂ ਨੂੰ ਆਮ ਭਾਸ਼ਾ ਵਿੱਚ ਸਮਝਾਓ। Respond in simple Punjabi.",
    "hinglish": "Respond in Hinglish (mix of Hindi and English, like how people normally talk). Use Roman script. Koi bhi legal term ko simple language mein samjhao."
}

MAIN_SYSTEM_PROMPT = """You are अधिKaar (Adhikaar), a trusted AI legal assistant for Indian citizens. Your purpose is to help ordinary people understand their legal rights and options in plain, simple language.

CRITICAL BEHAVIOR RULES:

1. **CONFIRMATION LOOP (MANDATORY)**: Before giving ANY legal advice, you MUST FIRST restate the user's situation in simple language and ask for confirmation. Format:
   "📋 Let me make sure I understand your situation:
   [Your understanding of their situation in 2-3 simple sentences]
   
   Is this correct? If I've misunderstood anything, please tell me."
   
   Only give advice AFTER the user confirms. If they correct you, restate with the correction.

2. **POWER-IMBALANCE DETECTION**: Analyze the situation for power imbalances:
   - Employer vs Worker → worker is vulnerable
   - Landlord vs Tenant → tenant is vulnerable  
   - Police vs Citizen → citizen is vulnerable
   - Husband/In-laws vs Wife → wife is vulnerable
   - Company vs Consumer → consumer is vulnerable
   - Government vs Citizen → citizen is vulnerable
   
   When detected, add a ⚠️ PROTECTIVE ADVISORY section:
   - "You are NOT legally required to sign anything on the spot"
   - "You have the right to consult a lawyer before taking any action"
   - "Do NOT hand over original documents to anyone"
   - "Recording conversations/keeping written evidence can help your case"
   - Other relevant protective advice based on the specific situation

3. **RESPONSE FORMAT** (after confirmation):
   📌 **Your Rights**: List 3-5 key rights that apply
   📋 **What You Should Do**: Step-by-step action plan (numbered)
   ⏰ **Important Deadlines**: Any time-sensitive actions
   📞 **Get Help**: Relevant helpline numbers
   ⚠️ **Protective Advisory**: (only if power imbalance detected)

4. **LEGAL REFERENCES**: Always cite specific law sections using BNS (Bharatiya Nyaya Sanhita) numbers. If the user mentions old IPC sections, explain the new BNS equivalent.

5. **TONE**: Be warm, empathetic, and encouraging. The user may be scared or confused. Reassure them that they have rights and options.

6. **SAFETY FIRST**: If the situation involves immediate physical danger, ALWAYS start with safety advice and emergency numbers (112 for police, 181 for women helpline).

7. **LIMITATIONS**: Make clear you are an AI assistant providing legal information, not a lawyer. For complex cases, always recommend consulting a qualified lawyer or contacting NALSA (15100) for free legal aid.

{language_instruction}

CONTEXT FROM KNOWLEDGE BASE:
{rag_context}
"""

DEVIL_ADVOCATE_PROMPT = """You are playing the role of a skilled opposing lawyer in an Indian legal context. Based on the user's situation, you must present BOTH sides:

**PART 1 — 👿 OPPOSING ARGUMENT** (What the other party's lawyer will argue):
Present the strongest legal arguments the opposing party could make. Be specific about which laws or precedents they might cite. Be realistic about weaknesses in the user's position.

**PART 2 — 🛡️ WEAKNESSES IN THEIR ARGUMENT** (Where the opponent is vulnerable):
Identify holes in the opposing argument. Point out where the law actually favors the user.

**PART 3 — ⚔️ HOW TO COUNTER** (What the user should prepare):
Provide specific counter-arguments, evidence to gather, and strategies to strengthen their case.

Be thorough and realistic. Real lawyers prepare for opposing arguments — this helps the user be ready.

{language_instruction}

SITUATION CONTEXT:
{rag_context}
"""

CONSEQUENCE_PROMPT = """Based on the user's legal situation, model what happens if they take NO ACTION at all. Present as a realistic timeline with specific legal consequences:

⏱️ **Timeline of Inaction:**

**Immediate (0-7 days):** [What happens right away if nothing is done]

**Short term (1-4 weeks):** [Legal implications, missed opportunities]

**Medium term (1-6 months):** [Escalation, potential consequences]

**Long term (6+ months):** [Worst-case scenarios, rights that expire]

⚠️ **Worst Case Scenario:** [The absolute worst outcome]

✅ **Most Urgent Action:** [The single most important thing to do RIGHT NOW]

Be specific about Indian law — mention actual deadlines, limitation periods, and legal consequences. Don't be alarmist but be honest about real risks.

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
- Format as a printable summary
- Make clear what ACTION needs to be taken and by whom

FORMAT:
🏘️ **समुदाय सहायता सारांश / Community Helper Summary**

**व्यक्ति की स्थिति (Person's Situation):** [1-2 sentences]

**उनके अधिकार (Their Rights):** [3-5 bullet points]

**क्या करना है (What To Do):** [Numbered steps]

**कानूनी धारा (Legal Sections):** [Relevant BNS sections]

**मदद के लिए फोन (Helpline Numbers):** [Numbers]

{language_instruction}

SITUATION AND ADVICE TO SIMPLIFY:
{context}
"""

DOCUMENT_TRANSLATE_PROMPT = """The user has a legal document (FIR, court notice, legal notice, summons, etc.) and needs it explained in plain language. The OCR text of the document is provided below.

YOUR TASKS:
1. **Identify the document type** (FIR, legal notice, court summons, etc.)
2. **Translate/explain** the document in plain, simple language
3. **Highlight key information**:
   - 📅 Important dates and deadlines
   - 👤 Who is involved (parties, court, police station)
   - ⚖️ What legal sections are mentioned and what they mean
   - ❗ What action is required from the reader
   - ⏰ By when must they respond/appear
4. **What should the reader do next** — clear, actionable steps

IMPORTANT: Many legal documents are in English or formal Hindi/Urdu legal language. Translate into the user's preferred language using simple, everyday words.

{language_instruction}

DOCUMENT TEXT (from OCR):
{document_text}
"""

CHECKLIST_PROMPT = """Based on the user's legal situation, generate a comprehensive, actionable checklist they can follow. Organize it by category:

📋 **अधिKaar Rights Checklist**

**📄 Documents to Collect:**
- [ ] [Document 1 - why it's needed]
- [ ] [Document 2 - why it's needed]
...

**📸 Evidence to Preserve:**
- [ ] [Screenshot/photo/recording - what to capture]
...

**📝 Notices to Send:**
- [ ] [What notice, to whom, by when]
...

**🏢 Offices to Visit:**
- [ ] [Which office, what to do there]
...

**⏰ Deadlines to Remember:**
- [ ] [Action - Deadline - Consequence of missing]
...

**📞 People to Contact:**
- [ ] [Who - Why - Number]
...

Be specific to Indian law and the user's exact situation. Include BNS sections where relevant.

{language_instruction}

SITUATION CONTEXT:
{rag_context}
"""

# ══════════════════════════════════════════════════════════════
# Helper Functions
# ══════════════════════════════════════════════════════════════

def get_session(session_id):
    """Get or create a conversation session."""
    if session_id not in sessions:
        sessions[session_id] = {
            'history': [],
            'confirmed': False,
            'situation_summary': '',
            'case_type': None
        }
    return sessions[session_id]

def get_language_instruction(lang):
    """Get language-specific instruction."""
    return LANGUAGE_INSTRUCTIONS.get(lang, LANGUAGE_INSTRUCTIONS['en'])

def call_gemma(messages, temperature=0.7):
    """Call Gemma via Ollama."""
    try:
        response = ollama.chat(
            model=GEMMA_MODEL,
            messages=messages,
            options={'temperature': temperature}
        )
        return response['message']['content']
    except Exception as e:
        print(f"Gemma error: {e}")
        traceback.print_exc()
        return f"I'm having trouble connecting to the AI model. Please make sure Ollama is running with Gemma 4. Error: {str(e)}"

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
        data = request.json
        message = data.get('message', '')
        language = data.get('language', 'en')
        session_id = data.get('session_id', str(uuid.uuid4()))
        
        session = get_session(session_id)
        
        # Retrieve relevant context from RAG
        rag_context = ""
        if rights_collection:
            rag_context += retrieve_context(message, rights_collection, n_results=3)
        if ipc_bns_collection:
            rag_context += "\n" + retrieve_context(message, ipc_bns_collection, n_results=3)
        
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
    """Devil's Advocate mode — argue against the user's position."""
    try:
        data = request.json
        situation = data.get('situation', '')
        language = data.get('language', 'en')
        session_id = data.get('session_id', '')
        
        # Get conversation context
        session = get_session(session_id) if session_id else {'history': []}
        
        rag_context = ""
        if rights_collection:
            rag_context += retrieve_context(situation, rights_collection, n_results=3)
        
        system_prompt = DEVIL_ADVOCATE_PROMPT.format(
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
        data = request.json
        query = data.get('query', '').strip()
        direction = data.get('direction', 'ipc_to_bns')  # or 'bns_to_ipc'
        
        if not query:
            return jsonify({"results": [], "ai_explanation": ""})
        
        # Search in static data first
        results = []
        query_lower = query.lower()
        
        for entry in IPC_BNS_DATA:
            match = False
            if direction == 'ipc_to_bns':
                if (query_lower in entry['ipc_section'].lower() or 
                    query_lower in entry['offence'].lower() or
                    query_lower in entry['description'].lower()):
                    match = True
            else:
                if (query_lower in entry['bns_section'].lower() or 
                    query_lower in entry['offence'].lower() or
                    query_lower in entry['description'].lower()):
                    match = True
            
            if match:
                results.append(entry)
        
        # Also search via RAG for semantic matches
        rag_results = ""
        if ipc_bns_collection:
            rag_results = retrieve_context(query, ipc_bns_collection, n_results=5)
        
        # Get AI explanation if results found
        ai_explanation = ""
        if results or rag_results:
            messages = [
                {"role": "system", "content": "You are a legal expert on Indian criminal law. Explain the IPC to BNS conversion briefly and clearly. Highlight any important changes in the new law."},
                {"role": "user", "content": f"User searched for: '{query}'. Found matches: {json.dumps(results[:3], ensure_ascii=False) if results else 'None from exact match'}. RAG context: {rag_results}. Explain the conversion briefly."}
            ]
            ai_explanation = call_gemma(messages, temperature=0.5)
        
        return jsonify({
            "results": results[:10],
            "ai_explanation": ai_explanation
        })
    
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
            "helplines": LEGAL_AID_DATA['helplines'],
            "states": [],
            "districts": []
        }
        
        if not state_query:
            # Return list of all states
            result['states'] = [
                {"name": s['name'], "name_hi": s['name_hi']} 
                for s in LEGAL_AID_DATA['states']
            ]
            return jsonify(result)
        
        # Find matching state
        for state in LEGAL_AID_DATA['states']:
            if state_query in state['name'].lower() or state_query in state.get('name_hi', '').lower():
                state_info = {
                    "name": state['name'],
                    "name_hi": state['name_hi'],
                    "slsa": state['slsa'],
                    "districts": state['districts']
                }
                result['states'] = [state_info]
                
                # Filter districts if query provided
                if district_query:
                    result['districts'] = [
                        d for d in state['districts']
                        if district_query in d['name'].lower() or district_query in d.get('name_hi', '').lower()
                    ]
                else:
                    result['districts'] = state['districts']
                break
        
        return jsonify(result)
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/translate-document', methods=['POST'])
def translate_document():
    """Translate and explain a legal document from OCR text."""
    try:
        data = request.json
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
        data = request.json
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
        data = request.json
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
        data = request.json
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
        data = request.json
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
# Main
# ══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════════╗
    ║         अधिKaar — AI Legal Assistant         ║
    ║      Empowering Every Citizen with Rights     ║
    ╚══════════════════════════════════════════════╝
    """)
    print(f"  Model: {GEMMA_MODEL}")
    print(f"  RAG DB: {CHROMA_DIR}")
    print(f"  Server: http://localhost:5000")
    print(f"  Make sure Ollama is running: ollama serve")
    print(f"  Make sure model is pulled: ollama pull {GEMMA_MODEL}")
    print()
    
    app.run(debug=True, host='0.0.0.0', port=5000)
