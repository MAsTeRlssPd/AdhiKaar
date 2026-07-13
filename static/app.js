/**
 * अधिKaar — AI Legal Assistant
 * Frontend Application Logic
 */

// ══════════════════════════════════════════════════════════════
// Configuration & State
// ══════════════════════════════════════════════════════════════

const API_BASE = '';  // Same origin

const LANGUAGES = [
  { code: 'en', name: 'English', native: 'English', speechCode: 'en-IN', label: 'EN' },
  { code: 'hi', name: 'Hindi', native: 'हिन्दी', speechCode: 'hi-IN', label: 'हि' },
  { code: 'hinglish', name: 'Hinglish', native: 'Hinglish', speechCode: 'hi-IN', label: 'HG' },
  { code: 'ta', name: 'Tamil', native: 'தமிழ்', speechCode: 'ta-IN', label: 'த' },
  { code: 'te', name: 'Telugu', native: 'తెలుగు', speechCode: 'te-IN', label: 'తె' },
  { code: 'bn', name: 'Bengali', native: 'বাংলা', speechCode: 'bn-IN', label: 'বা' },
  { code: 'mr', name: 'Marathi', native: 'मराठी', speechCode: 'mr-IN', label: 'म' },
  { code: 'gu', name: 'Gujarati', native: 'ગુજરાતી', speechCode: 'gu-IN', label: 'ગુ' },
  { code: 'kn', name: 'Kannada', native: 'ಕನ್ನಡ', speechCode: 'kn-IN', label: 'ಕ' },
  { code: 'ml', name: 'Malayalam', native: 'മലയാളം', speechCode: 'ml-IN', label: 'മ' },
  { code: 'pa', name: 'Punjabi', native: 'ਪੰਜਾਬੀ', speechCode: 'pa-IN', label: 'ਪ' },
];

const state = {
  currentView: 'home',
  language: localStorage.getItem('adhikaar_lang') || 'en',
  sessionId: localStorage.getItem('adhikaar_session') || generateId(),
  chatHistory: [],
  isRecording: false,
  recognition: null,
  bnsDirection: 'ipc_to_bns',
  bnsSearchTimeout: null,
  crpcDirection: 'crpc_to_bnss',
  crpcSearchTimeout: null,
  lastSituation: '',
  lastAdvice: '',
  autoSpeak: localStorage.getItem('adhikaar_autospeak') === '1',
};

// Save session ID
localStorage.setItem('adhikaar_session', state.sessionId);

// ══════════════════════════════════════════════════════════════
// Utilities
// ══════════════════════════════════════════════════════════════

function generateId() {
  return 'xxxx-xxxx-xxxx'.replace(/x/g, () => Math.floor(Math.random() * 16).toString(16));
}

function $(id) {
  return document.getElementById(id);
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function renderMarkdown(text) {
  if (typeof marked !== 'undefined') {
    try {
      return marked.parse(text);
    } catch (e) {
      return text.replace(/\n/g, '<br>');
    }
  }
  // Basic fallback markdown
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/^### (.*)/gm, '<h3>$1</h3>')
    .replace(/^## (.*)/gm, '<h2>$1</h2>')
    .replace(/^# (.*)/gm, '<h1>$1</h1>')
    .replace(/^- (.*)/gm, '<li>$1</li>')
    .replace(/^(\d+)\. (.*)/gm, '<li>$2</li>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>');
}

async function apiCall(endpoint, options = {}) {
  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('API call failed:', error);
    throw error;
  }
}

// ══════════════════════════════════════════════════════════════
// Navigation / Router
// ══════════════════════════════════════════════════════════════

function navigateTo(viewName) {
  // Hide all views
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  // Show target view
  const target = $(`view-${viewName}`);
  if (target) {
    target.classList.add('active');
    state.currentView = viewName;
  }
  // Enforce single visible view with inline styles (immune to CSS conflicts)
  document.querySelectorAll('.view').forEach(v => {
    v.style.display = v.classList.contains('active') ? 'flex' : 'none';
  });

  // Quick-ask bar shows on feature pages (chat and home have their own inputs)
  const ga = $('global-ask');
  if (ga) ga.style.display = (viewName === 'chat' || viewName === 'home') ? 'none' : 'block';

  // Update sidebar active state
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const navItem = document.querySelector(`.nav-item[data-view="${viewName}"]`);
  if (navItem) navItem.classList.add('active');

  // Update mobile nav
  document.querySelectorAll('.mobile-nav-item').forEach(n => n.classList.remove('active'));
  const mobileNavItem = document.querySelector(`.mobile-nav-item[data-view="${viewName}"]`);
  if (mobileNavItem) mobileNavItem.classList.add('active');

  // Initialize view-specific content
  if (viewName === 'legal-aid') initLegalAid();
  if (viewName === 'chat') {
    const input = $('chat-input');
    if (input) setTimeout(() => input.focus(), 100);
  }

  // Always start a view from the top
  const main = document.querySelector('.main-content');
  if (main) main.scrollTop = 0;
  window.scrollTo(0, 0);

  // Update URL hash
  window.location.hash = viewName;
}

// Handle browser back/forward
window.addEventListener('hashchange', () => {
  const hash = window.location.hash.slice(1);
  if (hash && hash !== state.currentView) {
    navigateTo(hash);
  }
});

// ══════════════════════════════════════════════════════════════
// Language Management
// ══════════════════════════════════════════════════════════════

function setLanguage(langCode) {
  state.language = langCode;
  localStorage.setItem('adhikaar_lang', langCode);

  // Update desktop selector
  const select = $('language-select');
  if (select) select.value = langCode;

  // Update mobile label
  const lang = LANGUAGES.find(l => l.code === langCode);
  const mobileLabelEl = $('mobile-lang-label');
  if (mobileLabelEl && lang) {
    mobileLabelEl.textContent = lang.label;
  }

  // Translate the whole interface
  applyTranslations();
}

function toggleMobileLang() {
  const modal = $('lang-modal');
  const container = $('lang-modal-options');
  container.innerHTML = '';

  LANGUAGES.forEach(lang => {
    const btn = document.createElement('button');
    btn.className = `btn ${state.language === lang.code ? 'btn-primary' : 'btn-secondary'}`;
    btn.style.justifyContent = 'flex-start';
    btn.textContent = `${lang.native} (${lang.name})`;
    btn.onclick = () => {
      setLanguage(lang.code);
      closeModal('lang-modal');
    };
    container.appendChild(btn);
  });

  modal.classList.add('active');
}

// ══════════════════════════════════════════════════════════════
// Chat Engine
// ══════════════════════════════════════════════════════════════

function sendSuggestion(text) {
  const input = $('chat-input');
  input.value = text;
  sendMessage();
}

// Jump from home hero chips straight into chat with the question sent
function goToChatWith(text) {
  navigateTo('chat');
  sendSuggestion(text);
}

// Re-render lucide icons after dynamic DOM changes
function refreshIcons() {
  if (window.lucide) lucide.createIcons();
}

function formatTime(date) {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

async function copyMessageText(btn, text) {
  try {
    await navigator.clipboard.writeText(text);
    btn.innerHTML = '<i data-lucide="check"></i> Copied';
    refreshIcons();
    setTimeout(() => {
      btn.innerHTML = '<i data-lucide="copy"></i> Copy';
      refreshIcons();
    }, 1500);
  } catch (e) {
    console.error('Copy failed', e);
  }
}

async function sendMessage() {
  const input = $('chat-input');
  const message = input.value.trim();
  if (!message) return;

  // Clear input
  input.value = '';
  autoResizeTextarea(input);

  // Hide welcome
  const welcome = $('chat-welcome');
  if (welcome) welcome.style.display = 'none';

  // Add user message
  addMessage('user', message);
  state.lastSituation = message;

  // Show typing indicator
  showTyping();

  const isDevilMode = $('devil-mode-toggle') && $('devil-mode-toggle').checked;
  const endpoint = isDevilMode ? '/api/devil-advocate' : '/api/chat';
  const bodyData = isDevilMode 
    ? { situation: message, language: state.language, session_id: state.sessionId }
    : { message: message, language: state.language, session_id: state.sessionId };

  try {
    const data = await apiCall(endpoint, {
      method: 'POST',
      body: JSON.stringify(bodyData),
    });

    hideTyping();
    if (!isDevilMode) {
      state.lastAdvice = data.response;
    }

    // Add assistant message with action buttons
    addMessage('assistant', data.response, {
      powerImbalance: data.power_imbalance,
      showActions: !isDevilMode,
    });

  } catch (error) {
    hideTyping();
    addMessage('assistant', '⚠️ Sorry, I could not connect to the AI model. Please make sure:\n\n1. **Ollama is running** (`ollama serve`)\n2. **The Gemma model is installed** (check `ollama list`)\n3. **The server is running** (`python app.py`)\n\nThen try again.');
  }
}

function addMessage(role, content, options = {}) {
  const container = $('chat-messages');

  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${role}`;

  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  avatar.innerHTML = role === 'user' ? '<i data-lucide="user"></i>' : '<i data-lucide="scale"></i>';

  const contentDiv = document.createElement('div');
  contentDiv.className = 'message-content markdown-body';

  if (role === 'assistant') {
    contentDiv.innerHTML = renderMarkdown(content);

    // Add action buttons after assistant responses
    if (options.showActions) {
      const actionsDiv = document.createElement('div');
      actionsDiv.className = 'message-actions';

      const actions = [
        { label: 'What If I Do Nothing?', icon: 'clock', cls: '', fn: () => runConsequenceSimulator() },
        { label: 'Explain to Elder', icon: 'users', cls: '', fn: () => runPanchayatBridge() },
        { label: 'Rights Card', icon: 'id-card', cls: '', fn: () => generateRightsCard() },
        { label: 'Checklist', icon: 'list-checks', cls: '', fn: () => generateChecklist() },
      ];

      actions.forEach(action => {
        const btn = document.createElement('button');
        btn.className = `message-action-btn ${action.cls}`;
        btn.innerHTML = `<i data-lucide="${action.icon}" class="inline-icon"></i> ${action.label}`;
        btn.onclick = action.fn;
        actionsDiv.appendChild(btn);
      });

      contentDiv.appendChild(actionsDiv);
    }

    // Timestamp + copy button
    const metaDiv = document.createElement('div');
    metaDiv.className = 'message-meta';
    const timeSpan = document.createElement('span');
    timeSpan.textContent = formatTime(new Date());
    const listenBtn = document.createElement('button');
    listenBtn.className = 'copy-btn';
    listenBtn.innerHTML = '<i data-lucide="volume-2"></i> Listen';
    listenBtn.onclick = () => toggleSpeak(listenBtn, content);
    const copyBtn = document.createElement('button');
    copyBtn.className = 'copy-btn';
    copyBtn.innerHTML = '<i data-lucide="copy"></i> Copy';
    copyBtn.onclick = () => copyMessageText(copyBtn, content);
    metaDiv.appendChild(timeSpan);
    metaDiv.appendChild(listenBtn);
    metaDiv.appendChild(copyBtn);
    contentDiv.appendChild(metaDiv);

    // Auto-read the answer aloud if the user enabled it
    if (state.autoSpeak) toggleSpeak(listenBtn, content);
  } else {
    contentDiv.textContent = content;
  }

  messageDiv.appendChild(avatar);
  messageDiv.appendChild(contentDiv);
  container.appendChild(messageDiv);
  refreshIcons();

  // Scroll to bottom
  container.scrollTop = container.scrollHeight;

  // Store in history
  state.chatHistory.push({ role, content });

  // Persist to active case (Case Workspace)
  persistToActiveCase(role, content);
}

function showTyping() {
  const container = $('chat-messages');
  const typingDiv = document.createElement('div');
  typingDiv.id = 'typing-indicator';
  typingDiv.className = 'typing-indicator';
  typingDiv.innerHTML = `
    <div class="message-avatar" style="background: var(--primary-subtle);"><i data-lucide="scale"></i></div>
    <div class="typing-dots"><span></span><span></span><span></span></div>
    <span style="color: var(--text-tertiary); font-size: var(--font-size-sm);">Thinking… local AI can take up to a minute</span>
  `;
  container.appendChild(typingDiv);
  refreshIcons();
  container.scrollTop = container.scrollHeight;
}

function hideTyping() {
  const typing = $('typing-indicator');
  if (typing) typing.remove();
}

function clearChat() {
  state.sessionId = generateId();
  localStorage.setItem('adhikaar_session', state.sessionId);
  localStorage.removeItem('adhikaar_active_case');
  if (typeof updateCaseBanner === 'function') updateCaseBanner();
  state.chatHistory = [];
  state.lastSituation = '';
  state.lastAdvice = '';

  const container = $('chat-messages');
  container.innerHTML = `
    <div class="chat-welcome" id="chat-welcome">
      <div class="welcome-icon"><i data-lucide="scale"></i></div>
      <h3>Welcome to अधिKaar</h3>
      <p>Tell me about your legal problem in your own words. I'll help you understand your rights and options.</p>
      <div class="suggestions">
        <button class="suggestion-chip" onclick="sendSuggestion('My employer has not paid my salary for 3 months')">Unpaid salary</button>
        <button class="suggestion-chip" onclick="sendSuggestion('My landlord is not returning my security deposit')">Security deposit</button>
        <button class="suggestion-chip" onclick="sendSuggestion('I received a legal notice and I don\\'t understand it')">Got a legal notice</button>
        <button class="suggestion-chip" onclick="sendSuggestion('Police refused to file my FIR')">FIR not filed</button>
        <button class="suggestion-chip" onclick="sendSuggestion('I am facing domestic violence from my husband and in-laws')">Domestic violence</button>
        <button class="suggestion-chip" onclick="sendSuggestion('Someone cheated me online and took my money')">Online fraud</button>
      </div>
    </div>
  `;
  refreshIcons();
  applyTranslations();
  renderChatSidebar();
}

function handleChatKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

// Auto-resize textarea
function autoResizeTextarea(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 150) + 'px';
}

// ══════════════════════════════════════════════════════════════
// Special Chat Modes
// ══════════════════════════════════════════════════════════════

async function runDevilAdvocate() {
  if (!state.lastSituation) return;

  showTyping();
  try {
    const data = await apiCall('/api/devil-advocate', {
      method: 'POST',
      body: JSON.stringify({
        situation: state.lastSituation,
        language: state.language,
        session_id: state.sessionId,
      }),
    });
    hideTyping();
    addMessage('assistant', '## 👿 Devil\'s Advocate Analysis\n\n' + data.response);
  } catch (error) {
    hideTyping();
    addMessage('assistant', '⚠️ Could not run Devil\'s Advocate mode. Please check if the server is running.');
  }
}

async function runConsequenceSimulator() {
  if (!state.lastSituation) return;

  showTyping();
  try {
    const data = await apiCall('/api/consequence-simulator', {
      method: 'POST',
      body: JSON.stringify({
        situation: state.lastSituation,
        language: state.language,
      }),
    });
    hideTyping();
    addMessage('assistant', '## ⏰ What Happens If You Do Nothing\n\n' + data.response);
  } catch (error) {
    hideTyping();
    addMessage('assistant', '⚠️ Could not run consequence simulator. Please check if the server is running.');
  }
}

async function runPanchayatBridge() {
  if (!state.lastSituation) return;

  showTyping();
  try {
    const data = await apiCall('/api/panchayat-bridge', {
      method: 'POST',
      body: JSON.stringify({
        situation: state.lastSituation,
        advice: state.lastAdvice,
        language: state.language,
      }),
    });
    hideTyping();
    addMessage('assistant', '## 🏘️ Community Elder Summary\n\n' + data.response);
  } catch (error) {
    hideTyping();
    addMessage('assistant', '⚠️ Could not generate elder summary. Please check if the server is running.');
  }
}

async function generateChecklist() {
  if (!state.lastSituation) return;

  showTyping();
  try {
    const data = await apiCall('/api/rights-checklist', {
      method: 'POST',
      body: JSON.stringify({
        situation: state.lastSituation,
        language: state.language,
      }),
    });
    hideTyping();
    addMessage('assistant', data.response);
  } catch (error) {
    hideTyping();
    addMessage('assistant', '⚠️ Could not generate checklist. Please check if the server is running.');
  }
}

// ══════════════════════════════════════════════════════════════
// Rights Card Generator
// ══════════════════════════════════════════════════════════════

async function generateRightsCard() {
  if (!state.lastSituation) return;

  showTyping();
  try {
    const data = await apiCall('/api/rights-card', {
      method: 'POST',
      body: JSON.stringify({
        situation: state.lastSituation,
        advice: state.lastAdvice,
        language: state.language,
      }),
    });
    hideTyping();

    const card = data.card;

    // Populate card
    $('card-title').textContent = card.title || 'Your Rights';
    $('card-situation').textContent = card.situation_summary || state.lastSituation.slice(0, 100);

    const rightsList = $('card-rights');
    rightsList.innerHTML = '';
    (card.rights || []).forEach(right => {
      const li = document.createElement('li');
      li.textContent = right;
      rightsList.appendChild(li);
    });

    const helplines = card.helplines || ['NALSA: 15100', 'Tele-Law: 14454', 'Police: 112'];
    $('card-helplines').innerHTML = `<strong>📞 Emergency Numbers:</strong><span>${helplines.join(' | ')}</span>`;

    // Show modal
    $('rights-card-modal').classList.add('active');
  } catch (error) {
    hideTyping();
    addMessage('assistant', '⚠️ Could not generate rights card. Please check if the server is running.');
  }
}

async function downloadRightsCard() {
  const cardEl = $('rights-card-content');
  if (typeof html2canvas === 'undefined') {
    alert('Image generation library is loading. Please try again in a moment.');
    return;
  }

  try {
    const canvas = await html2canvas(cardEl, {
      scale: 2,
      backgroundColor: null,
      useCORS: true,
    });

    const link = document.createElement('a');
    link.download = 'adhikaar-rights-card.png';
    link.href = canvas.toDataURL('image/png');
    link.click();
  } catch (error) {
    console.error('Card download error:', error);
    alert('Could not generate image. Please try again.');
  }
}

async function shareRightsCard() {
  const cardEl = $('rights-card-content');
  if (typeof html2canvas === 'undefined') {
    alert('Image generation library is loading. Please try again.');
    return;
  }

  try {
    const canvas = await html2canvas(cardEl, { scale: 2, backgroundColor: null });

    canvas.toBlob(async (blob) => {
      if (!blob) return;

      const file = new File([blob], 'adhikaar-rights-card.png', { type: 'image/png' });

      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({
          files: [file],
          title: 'अधिKaar — Know Your Rights',
          text: 'Here are my rights as explained by अधिKaar AI Legal Assistant',
        });
      } else {
        // Fallback: download
        downloadRightsCard();
      }
    });
  } catch (error) {
    console.error('Share error:', error);
    downloadRightsCard();
  }
}

// ══════════════════════════════════════════════════════════════
// Voice Input (Web Speech API) — single shared dictation engine
// ══════════════════════════════════════════════════════════════
//
// NOTE: The browser Web Speech API sends microphone audio to the
// browser vendor's cloud (e.g. Google) for transcription. It is NOT
// on-device and needs an internet connection. For a fully-local,
// private pipeline, transcription should move to a backend Whisper/
// Vosk endpoint — tracked separately.

let activeRecognition = null;     // the one recognizer currently running
let dictationTimer = null;        // safety auto-stop timer

// Browser speech recognition is only dependable for these in practice.
// Others (Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada, Malayalam,
// Punjabi) are hit-or-miss — we warn the user once rather than fail silently.
const RELIABLE_STT_LANGS = ['en', 'hi', 'hinglish'];
const warnedSttLangs = new Set();

function getSpeechRecognition() {
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

// Persistent "Listening…" pill (kiosk has its own; this is for chat/home/quick-ask)
function setListeningIndicator(on) {
  let el = document.getElementById('listening-indicator');
  if (on) {
    if (!el) {
      el = document.createElement('div');
      el.id = 'listening-indicator';
      el.style.cssText = [
        'position:fixed', 'left:50%', 'bottom:150px', 'transform:translateX(-50%)',
        'background:#dc2626', 'color:#fff', 'padding:8px 16px', 'border-radius:999px',
        'font-size:14px', 'z-index:9998', 'display:flex', 'align-items:center', 'gap:8px',
        'box-shadow:0 4px 16px rgba(0,0,0,.2)'
      ].join(';');
      el.innerHTML = '<span style="width:10px;height:10px;border-radius:50%;background:#fff"></span> Listening… tap the mic to stop';
      document.body.appendChild(el);
    }
    el.style.display = 'flex';
  } else if (el) {
    el.style.display = 'none';
  }
}

// Human-readable, language-agnostic error hints
function voiceErrorMessage(err) {
  switch (err) {
    case 'not-allowed':
    case 'service-not-allowed':
      return 'Microphone is blocked. Please allow mic access in your browser and try again.';
    case 'no-speech':
      return "I didn't catch that — tap the mic and speak again.";
    case 'audio-capture':
      return 'No microphone found. Please connect a microphone and try again.';
    case 'network':
      return 'Voice typing needs an internet connection right now. You can type instead.';
    default:
      return 'Voice input stopped. Please try again, or type your message.';
  }
}

// Lightweight, self-contained toast (no CSS dependency)
function showToast(msg) {
  let toast = document.getElementById('voice-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'voice-toast';
    toast.style.cssText = [
      'position:fixed', 'left:50%', 'bottom:96px', 'transform:translateX(-50%)',
      'background:#1f2937', 'color:#fff', 'padding:12px 18px', 'border-radius:12px',
      'font-size:15px', 'max-width:90vw', 'z-index:9999', 'box-shadow:0 6px 24px rgba(0,0,0,.25)',
      'text-align:center', 'transition:opacity .3s', 'opacity:0'
    ].join(';');
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  requestAnimationFrame(() => { toast.style.opacity = '1'; });
  clearTimeout(toast._hideTimer);
  toast._hideTimer = setTimeout(() => { toast.style.opacity = '0'; }, 4000);
}

function setMicIcon(btn, icon) {
  if (btn) {
    btn.innerHTML = `<i data-lucide="${icon}"></i>`;
    refreshIcons();
  }
}

/**
 * Start voice dictation into a target input/textarea.
 *  - Appends to existing text (never overwrites what the user typed).
 *  - continuous: does NOT cut off on natural pauses; user taps mic to stop.
 *  - Never auto-sends: the caller decides what to do via opts.onStop.
 *  - Cancels any speaking TTS first so the mic doesn't hear it.
 * Returns the recognition object, or null if it couldn't start.
 */
function startDictation(targetEl, micBtn, opts = {}) {
  const SR = getSpeechRecognition();
  if (!SR) {
    showToast('Voice input needs Chrome or Edge.');
    return null;
  }
  if (!targetEl) return null;

  // Stop TTS + any recognizer already running (prevents overlap/feedback loops)
  window.speechSynthesis?.cancel();
  if (activeRecognition) { try { activeRecognition.stop(); } catch (e) {} activeRecognition = null; }

  const rec = new SR();
  rec.lang = speechLang();
  rec.interimResults = true;
  rec.continuous = true;   // don't cut off slow / hesitant speakers

  const baseText = targetEl.value && targetEl.value.trim() ? targetEl.value.trim() + ' ' : '';

  // One-time heads-up if this language is unreliable for browser speech input
  if (!RELIABLE_STT_LANGS.includes(state.language) && !warnedSttLangs.has(state.language)) {
    warnedSttLangs.add(state.language);
    showToast('Voice typing for this language may be limited in your browser. If it struggles, please type instead.');
  }

  micBtn?.classList.add('recording', 'listening');
  setMicIcon(micBtn, 'square');
  setListeningIndicator(true);

  const stopUI = () => {
    micBtn?.classList.remove('recording', 'listening');
    setMicIcon(micBtn, 'mic');
    setListeningIndicator(false);
    clearTimeout(dictationTimer);
    if (activeRecognition === rec) activeRecognition = null;
  };

  rec.onresult = (event) => {
    let finalText = '', interim = '';
    for (let i = 0; i < event.results.length; i++) {
      const res = event.results[i];
      if (res.isFinal) finalText += res[0].transcript;
      else interim += res[0].transcript;
    }
    let spoken = finalText + interim;
    // Hinglish is recognised as Hindi (Devanagari) — convert to Roman so it
    // matches how Hinglish is typed.
    if (state.language === 'hinglish') spoken = transliterateHiToLatin(spoken);
    targetEl.value = baseText + spoken;
    if (targetEl.tagName === 'TEXTAREA' && typeof autoResizeTextarea === 'function') {
      autoResizeTextarea(targetEl);
    }
  };

  rec.onend = () => {
    stopUI();
    if (opts.onStop) opts.onStop(targetEl.value.trim());
  };

  rec.onerror = (event) => {
    stopUI();
    // 'aborted' happens on normal manual stop — don't nag the user about it
    if (event.error && event.error !== 'aborted') {
      showToast(voiceErrorMessage(event.error));
    }
  };

  try {
    rec.start();
  } catch (e) {
    stopUI();
    showToast('Could not start voice input. Please try again.');
    return null;
  }

  activeRecognition = rec;
  // Safety net: auto-stop after 60s so the mic button never sticks on
  dictationTimer = setTimeout(() => { try { rec.stop(); } catch (e) {} }, 60000);
  return rec;
}

function stopDictation() {
  if (activeRecognition) { try { activeRecognition.stop(); } catch (e) {} }
}

// Feature-detect once on load; pre-warm TTS voices; hide mic buttons if unsupported.
function initVoice() {
  loadVoices();
  if (window.speechSynthesis) {
    window.speechSynthesis.onvoiceschanged = loadVoices;
  }
  if (!getSpeechRecognition()) {
    document.querySelectorAll('#voice-btn, #home-chat-mic, #global-ask-mic, #kiosk-mic-btn')
      .forEach(b => { if (b) b.style.display = 'none'; });
    console.log('Speech Recognition not supported — mic buttons hidden.');
  }
  updateAutoSpeakBtn();
}

// Chat mic: tap to start (review before sending), tap again to stop without sending.
function toggleVoice() {
  if (activeRecognition) { stopDictation(); return; }
  const input = $('chat-input');
  startDictation(input, $('voice-btn'), {
    onStop: () => { if (input) input.focus(); }   // user reviews, then presses send
  });
}

// ══════════════════════════════════════════════════════════════
// BNS Converter
// ══════════════════════════════════════════════════════════════

// Open the merged converter view on a given code tab (from home cards)
function openConverter(code) {
  navigateTo('bns');
  setConverterCode(code || 'ipc_bns');
}

// Switch between IPC↔BNS and CrPC↔BNSS panels inside the converter view
function setConverterCode(code) {
  const isCrpc = code === 'crpc_bnss';
  $('code-ipc-bns').classList.toggle('active', !isCrpc);
  $('code-crpc-bnss').classList.toggle('active', isCrpc);
  $('panel-ipc-bns').style.display = isCrpc ? 'none' : 'block';
  $('panel-crpc-bnss').style.display = isCrpc ? 'block' : 'none';
}

function setBnsDirection(direction) {
  state.bnsDirection = direction;

  $('toggle-ipc-bns').classList.toggle('active', direction === 'ipc_to_bns');
  $('toggle-bns-ipc').classList.toggle('active', direction === 'bns_to_ipc');

  // Re-search if there's input
  searchBns();
}

function searchBns() {
  clearTimeout(state.bnsSearchTimeout);
  state.bnsSearchTimeout = setTimeout(doSearchBns, 400);
}

async function doSearchBns() {
  const query = $('bns-search').value.trim();
  const resultsContainer = $('bns-results');
  const aiContainer = $('bns-ai-explanation');

  if (!query) {
    resultsContainer.innerHTML = '<div class="empty-state"><div class="empty-icon">🔍</div><p>Type a section number or offence name to search</p></div>';
    aiContainer.innerHTML = '';
    return;
  }

  resultsContainer.innerHTML = '<div class="loading"><div class="spinner"></div><span>Searching...</span></div>';
  aiContainer.innerHTML = '';

  try {
    const data = await apiCall('/api/bns-convert', {
      method: 'POST',
      body: JSON.stringify({
        query: query,
        direction: state.bnsDirection,
      }),
    });

    if (data.results && data.results.length > 0) {
      resultsContainer.innerHTML = data.results.map(r => `
        <div class="result-card">
          <div class="section-mapping">
            <span class="section-badge ipc">IPC ${escapeHtml(r.ipc_section)}</span>
            <span class="section-arrow">→</span>
            <span class="section-badge bns">BNS ${escapeHtml(r.bns_section)}</span>
          </div>
          <div class="offence-name">${escapeHtml(r.offence)}</div>
          <div class="description">${escapeHtml(r.description).slice(0, 200)}${r.description.length > 200 ? '...' : ''}</div>
          <div class="key-changes">
            <strong>⚡ Key Changes:</strong> ${escapeHtml(r.key_changes)}
          </div>
          <div class="punishment">⚖️ ${escapeHtml(r.punishment)}</div>
        </div>
      `).join('');
    } else {
      resultsContainer.innerHTML = '<div class="empty-state"><div class="empty-icon">🤷</div><p>No exact matches found. Try a different section number or offence name.</p></div>';
    }

    if (data.ai_explanation) {
      aiContainer.innerHTML = `
        <div class="ai-explanation">
          <h4>🤖 AI Explanation</h4>
          <div class="explanation-text markdown-body">${renderMarkdown(data.ai_explanation)}</div>
        </div>
      `;
    }
  } catch (error) {
    resultsContainer.innerHTML = '<div class="empty-state"><div class="empty-icon">⚠️</div><p>Could not search. Please check if the server is running.</p></div>';
  }
}

// ══════════════════════════════════════════════════════════════
// CrPC ↔ BNSS Converter
// ══════════════════════════════════════════════════════════════

function setCrpcDirection(direction) {
  state.crpcDirection = direction;
  $('toggle-crpc-bnss').classList.toggle('active', direction === 'crpc_to_bnss');
  $('toggle-bnss-crpc').classList.toggle('active', direction === 'bnss_to_crpc');
  searchCrpc();
}

function searchCrpc() {
  clearTimeout(state.crpcSearchTimeout);
  state.crpcSearchTimeout = setTimeout(doSearchCrpc, 400);
}

async function doSearchCrpc() {
  const query = $('crpc-search').value.trim();
  const resultsContainer = $('crpc-results');
  const aiContainer = $('crpc-ai-explanation');

  if (!query) {
    resultsContainer.innerHTML = '<div class="empty-state"><div class="empty-icon">🔍</div><p>Type a section number to search</p></div>';
    aiContainer.innerHTML = '';
    return;
  }

  resultsContainer.innerHTML = '<div class="loading"><div class="spinner"></div><span>Searching...</span></div>';
  aiContainer.innerHTML = '';

  try {
    const data = await apiCall('/api/crpc-convert', {
      method: 'POST',
      body: JSON.stringify({ query: query, direction: state.crpcDirection }),
    });

    if (data.results && data.results.length > 0) {
      resultsContainer.innerHTML = data.results.map(r => `
        <div class="result-card">
          <div class="section-mapping">
            <span class="section-badge ipc">CrPC ${escapeHtml(r.crpc_section)}</span>
            <span class="section-arrow">→</span>
            <span class="section-badge bns">BNSS ${escapeHtml(r.bnss_section)}</span>
          </div>
          <div class="offence-name">${escapeHtml(r.offence)}</div>
          <div class="description">${escapeHtml(r.description).slice(0, 220)}${r.description.length > 220 ? '...' : ''}</div>
          <div class="key-changes">
            <strong>⚡ Key Changes:</strong> ${escapeHtml(r.key_changes)}
          </div>
          <div class="punishment">📂 ${escapeHtml(r.category)}</div>
        </div>
      `).join('');
    } else {
      resultsContainer.innerHTML = '<div class="empty-state"><div class="empty-icon">🤷</div><p>No exact match found. Try another section number (e.g., 144, 154, 438).</p></div>';
    }

    if (data.ai_explanation) {
      aiContainer.innerHTML = `
        <div class="ai-explanation">
          <h4>🤖 AI Explanation</h4>
          <div class="explanation-text markdown-body">${renderMarkdown(data.ai_explanation)}</div>
        </div>
      `;
    }
  } catch (error) {
    resultsContainer.innerHTML = '<div class="empty-state"><div class="empty-icon">⚠️</div><p>Could not search. Please check if the server is running.</p></div>';
  }
}

// ══════════════════════════════════════════════════════════════
// Legal Aid Finder
// ══════════════════════════════════════════════════════════════

let legalAidData = null;

async function initLegalAid() {
  if (legalAidData) {
    renderHelplines();
    return;
  }

  try {
    legalAidData = await apiCall('/api/legal-aid?state=');

    // Populate state dropdown
    const stateSelect = $('state-select');
    stateSelect.innerHTML = '<option value="">-- Select State / राज्य चुनें --</option>';
    (legalAidData.states || []).forEach(s => {
      const opt = document.createElement('option');
      opt.value = s.name;
      opt.textContent = `${s.name} (${s.name_hi})`;
      stateSelect.appendChild(opt);
    });

    renderHelplines();
  } catch (error) {
    console.error('Failed to load legal aid data:', error);
  }
}

function renderHelplines() {
  if (!legalAidData || !legalAidData.helplines) return;

  const container = $('helpline-cards');
  container.innerHTML = legalAidData.helplines.map(h => `
    <div class="helpline-card">
      <div class="helpline-number">${escapeHtml(h.number)}</div>
      <div class="helpline-name">${escapeHtml(h.name)}</div>
      <div class="helpline-desc">${escapeHtml(h.description)}</div>
      <div class="helpline-hours">🕐 ${escapeHtml(h.hours)}</div>
    </div>
  `).join('');
}

async function onStateSelect() {
  const stateName = $('state-select').value;
  const districtSelect = $('district-select');
  const resultsContainer = $('legal-aid-results');

  districtSelect.innerHTML = '<option value="">-- Select District / जिला चुनें --</option>';
  resultsContainer.innerHTML = '';

  if (!stateName) return;

  try {
    const data = await apiCall(`/api/legal-aid?state=${encodeURIComponent(stateName)}`);

    if (data.states && data.states.length > 0) {
      const stateInfo = data.states[0];

      // Show state authority
      resultsContainer.innerHTML = `
        <div class="contact-card">
          <div class="contact-icon">🏛️</div>
          <div class="contact-info">
            <h4>${escapeHtml(stateInfo.slsa.name)}</h4>
            <p>${escapeHtml(stateInfo.slsa.address)}</p>
            <p><a href="${escapeHtml(stateInfo.slsa.website)}" target="_blank">${escapeHtml(stateInfo.slsa.website)}</a></p>
          </div>
          <div class="contact-phone">📞 ${escapeHtml(stateInfo.slsa.phone)}</div>
        </div>
      `;

      // Populate district dropdown
      (data.districts || []).forEach(d => {
        const opt = document.createElement('option');
        opt.value = d.name;
        opt.textContent = `${d.name} (${d.name_hi || ''})`;
        districtSelect.appendChild(opt);
      });
    }
  } catch (error) {
    resultsContainer.innerHTML = '<div class="empty-state"><p>⚠️ Could not load data. Please check server.</p></div>';
  }
}

function onDistrictSelect() {
  const stateName = $('state-select').value;
  const districtName = $('district-select').value;
  const resultsContainer = $('legal-aid-results');

  if (!districtName) return;

  // Find district info from already loaded data
  const districtSelect = $('district-select');
  const selectedOption = districtSelect.options[districtSelect.selectedIndex];

  apiCall(`/api/legal-aid?state=${encodeURIComponent(stateName)}&district=${encodeURIComponent(districtName)}`)
    .then(data => {
      let html = '';

      if (data.states && data.states.length > 0) {
        const stateInfo = data.states[0];
        html += `
          <div class="contact-card">
            <div class="contact-icon">🏛️</div>
            <div class="contact-info">
              <h4>${escapeHtml(stateInfo.slsa.name)}</h4>
              <p>${escapeHtml(stateInfo.slsa.address)}</p>
            </div>
            <div class="contact-phone">📞 ${escapeHtml(stateInfo.slsa.phone)}</div>
          </div>
        `;
      }

      if (data.districts && data.districts.length > 0) {
        data.districts.forEach(d => {
          html += `
            <div class="contact-card">
              <div class="contact-icon">📍</div>
              <div class="contact-info">
                <h4>DLSA — ${escapeHtml(d.name)}</h4>
                <p>${escapeHtml(d.dlsa_address)}</p>
              </div>
              <div class="contact-phone">📞 ${escapeHtml(d.phone)}</div>
            </div>
          `;
        });
      }

      resultsContainer.innerHTML = html;
    })
    .catch(error => {
      console.error('District load error:', error);
    });
}

// ══════════════════════════════════════════════════════════════
// Document Translator
// ══════════════════════════════════════════════════════════════

async function handleFileUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  const uploadArea = $('upload-area');
  uploadArea.innerHTML = `
    <div class="loading">
      <div class="spinner"></div>
      <span>Reading document... This may take a moment.</span>
    </div>
  `;

  try {
    // Use Tesseract.js for OCR
    if (typeof Tesseract === 'undefined') {
      throw new Error('OCR library not loaded yet. Please wait and try again.');
    }

    const result = await Tesseract.recognize(file, 'eng+hin', {
      logger: m => {
        if (m.status === 'recognizing text') {
          uploadArea.innerHTML = `
            <div class="loading">
              <div class="spinner"></div>
              <span>Reading document... ${Math.round(m.progress * 100)}%</span>
            </div>
          `;
        }
      },
    });

    const ocrText = result.data.text;

    // Show OCR result
    $('ocr-text').textContent = ocrText;
    $('ocr-result-section').style.display = 'block';

    // Reset upload area
    uploadArea.innerHTML = `
      <div class="upload-icon">📷</div>
      <h3>Tap to upload another document</h3>
      <p>Take a photo or select from gallery.</p>
      <input type="file" id="file-input" accept="image/*,.pdf" onchange="handleFileUpload(event)">
    `;
    uploadArea.onclick = () => document.getElementById('file-input').click();

  } catch (error) {
    console.error('OCR error:', error);
    uploadArea.innerHTML = `
      <div class="upload-icon">⚠️</div>
      <h3>Could not read document</h3>
      <p>${escapeHtml(error.message)}. Try pasting the text manually below.</p>
      <input type="file" id="file-input" accept="image/*,.pdf" onchange="handleFileUpload(event)">
    `;
    uploadArea.onclick = () => document.getElementById('file-input').click();
  }
}

async function translateOcrText() {
  const text = $('ocr-text').textContent;
  if (!text.trim()) return;

  await doTranslateDocument(text);
}

async function translateDocument() {
  const text = $('doc-text-input').value.trim();
  if (!text) {
    alert('Please paste the document text first.');
    return;
  }

  await doTranslateDocument(text);
}

async function doTranslateDocument(text) {
  const resultSection = $('translation-result-section');
  const resultDiv = $('translation-result');

  resultSection.style.display = 'block';
  resultDiv.innerHTML = '<div class="loading"><div class="spinner"></div><span>Translating and explaining...</span></div>';

  try {
    const data = await apiCall('/api/translate-document', {
      method: 'POST',
      body: JSON.stringify({
        text: text,
        language: state.language,
      }),
    });

    resultDiv.innerHTML = renderMarkdown(data.response);
  } catch (error) {
    resultDiv.innerHTML = '<p>⚠️ Could not translate document. Please check if the server is running.</p>';
  }
}

// Drag & drop support
function setupDragDrop() {
  const uploadArea = $('upload-area');
  if (!uploadArea) return;

  uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
  });

  uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragover');
  });

  uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileUpload({ target: { files: files } });
    }
  });
}

// ══════════════════════════════════════════════════════════════
// Modal
// ══════════════════════════════════════════════════════════════

function closeModal(id) {
  $(id).classList.remove('active');
}

// Close modal on overlay click
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('active');
  }
});

// ══════════════════════════════════════════════════════════════
// Initialization
// ══════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
  // Enforce single visible view on load
  document.querySelectorAll('.view').forEach(v => {
    v.style.display = v.classList.contains('active') ? 'flex' : 'none';
  });

  // Set initial language
  setLanguage(state.language);

  // Setup sidebar nav clicks
  document.querySelectorAll('.nav-item[data-view]').forEach(item => {
    item.addEventListener('click', () => {
      navigateTo(item.dataset.view);
    });
  });

  // Setup textarea auto-resize
  const chatInput = $('chat-input');
  if (chatInput) {
    chatInput.addEventListener('input', () => autoResizeTextarea(chatInput));
  }

  // Language select change
  const langSelect = $('language-select');
  if (langSelect) {
    langSelect.addEventListener('change', (e) => setLanguage(e.target.value));
  }

  // Initialize voice
  initVoice();

  // Setup drag & drop
  setupDragDrop();

  // Handle initial hash
  const hash = window.location.hash.slice(1);
  if (hash) {
    navigateTo(hash);
  }

  // Initialize BNS empty state
  const bnsResults = $('bns-results');
  if (bnsResults) {
    bnsResults.innerHTML = '<div class="empty-state"><div class="empty-icon"><i data-lucide="search"></i></div><p>Type a section number or offence name to search</p></div>';
  }

  // Render lucide icons (script is deferred, so lucide is loaded by now)
  refreshIcons();

  // Animated stat counters — count up when scrolled into view
  const statsRow = $('stats-row');
  if (statsRow && 'IntersectionObserver' in window) {
    const animateCount = (el) => {
      const target = parseInt(el.dataset.count, 10) || 0;
      const duration = 1200;
      const start = performance.now();
      const tick = (now) => {
        const progress = Math.min((now - start) / duration, 1);
        el.textContent = Math.round(target * (1 - Math.pow(1 - progress, 3)));
        if (progress < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    };
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.querySelectorAll('.stat-number').forEach(animateCount);
          observer.disconnect();
        }
      });
    }, { threshold: 0.3 });
    observer.observe(statsRow);
  }

  // Render case dashboard + re-render on nav
  renderCases();
  renderChatSidebar();
  document.querySelectorAll('[data-view="cases"]').forEach(el =>
    el.addEventListener('click', renderCases));
  document.querySelectorAll('[data-view="chat"]').forEach(el =>
    el.addEventListener('click', renderChatSidebar));
  document.querySelectorAll('[data-view="courtroom"]').forEach(el =>
    el.addEventListener('click', prefillCourtroom));
});

// ══════════════════════════════════════════════════════════════
// CASE WORKSPACE — private, stored on this device only
// ══════════════════════════════════════════════════════════════

function loadCases() {
  try {
    return JSON.parse(localStorage.getItem('adhikaar_cases')) || [];
  } catch (e) { return []; }
}

function saveCases(cases) {
  localStorage.setItem('adhikaar_cases', JSON.stringify(cases));
}

function getActiveCase() {
  const id = localStorage.getItem('adhikaar_active_case');
  return loadCases().find(c => c.id === id) || null;
}

function renderChatSidebar() {
  const listEl = $('chat-history-list');
  if (!listEl) return;

  const cases = loadCases();
  const activeId = localStorage.getItem('adhikaar_active_case');

  if (cases.length === 0) {
    listEl.innerHTML = '<div style="text-align: center; color: var(--text-tertiary); font-size: var(--font-size-xs); padding: var(--space-md);">No previous chats</div>';
    return;
  }

  listEl.innerHTML = cases.map(c => {
    const isActive = c.id === activeId;
    return `
      <div class="chat-history-item ${isActive ? 'active' : ''}" onclick="openCase('${c.id}')">
        <span class="chat-item-title">${escapeHtml(c.title)}</span>
        <button class="chat-item-delete" onclick="deleteCase('${c.id}', event)" title="Delete Chat">
          <i data-lucide="trash-2"></i>
        </button>
      </div>
    `;
  }).join('');

  refreshIcons();
}

function persistToActiveCase(role, content) {
  const cases = loadCases();
  let id = localStorage.getItem('adhikaar_active_case');
  let c = cases.find(x => x.id === id);
  
  if (!c && role === 'user') {
    // Automatically create a new case/chat
    const title = content.slice(0, 30) + (content.length > 30 ? '...' : '');
    const newCase = {
      id: generateId(),
      title: title.trim(),
      createdAt: Date.now(),
      updatedAt: Date.now(),
      sessionId: state.sessionId, // reuse the current sessionId
      summary: content.slice(0, 120),
      history: [],
      drafts: [],
      deadlines: [],
    };
    cases.unshift(newCase);
    saveCases(cases);
    localStorage.setItem('adhikaar_active_case', newCase.id);
    c = newCase;
    
    // Update UI
    updateCaseBanner();
  }
  
  if (!c) return;
  
  c.history.push({ role, content, time: Date.now() });
  c.updatedAt = Date.now();
  if (!c.summary && role === 'user') c.summary = content.slice(0, 120);
  saveCases(cases);
  
  renderChatSidebar();
  if (state.currentView === 'cases') renderCases();
}

function createCase() {
  const title = prompt('Give this case a name (e.g., "Salary dispute with ABC Pvt Ltd"):');
  if (!title) return;
  const cases = loadCases();
  const newCase = {
    id: generateId(),
    title: title.trim(),
    createdAt: Date.now(),
    updatedAt: Date.now(),
    sessionId: generateId(),
    summary: '',
    history: [],
    drafts: [],
    deadlines: [],
  };
  cases.unshift(newCase);
  saveCases(cases);
  openCase(newCase.id);
  renderChatSidebar();
}

function openCase(id) {
  const c = loadCases().find(x => x.id === id);
  if (!c) return;
  localStorage.setItem('adhikaar_active_case', id);

  // Bind chat to this case's session and restore its conversation
  state.sessionId = c.sessionId;
  localStorage.setItem('adhikaar_session', c.sessionId);
  state.chatHistory = [];
  state.lastSituation = '';
  state.lastAdvice = '';

  const container = $('chat-messages');
  container.innerHTML = '';
  if (c.history.length === 0) {
    clearChatWelcomeOnly(container);
  } else {
    c.history.forEach(m => renderStoredMessage(container, m));
    const lastUser = [...c.history].reverse().find(m => m.role === 'user');
    const lastAsst = [...c.history].reverse().find(m => m.role === 'assistant');
    if (lastUser) state.lastSituation = lastUser.content;
    if (lastAsst) state.lastAdvice = lastAsst.content;
    state.chatHistory = c.history.map(m => ({ role: m.role, content: m.content }));
  }
  updateCaseBanner();
  navigateTo('chat');
  renderCases();
  renderChatSidebar();
}

function clearChatWelcomeOnly(container) {
  container.innerHTML = `
    <div class="chat-welcome" id="chat-welcome">
      <div class="welcome-icon"><i data-lucide="scale"></i></div>
      <h3>New case started</h3>
      <p>Tell me about this legal problem in your own words.</p>
    </div>`;
  refreshIcons();
}

function renderStoredMessage(container, m) {
  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${m.role}`;
  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  avatar.innerHTML = m.role === 'user' ? '<i data-lucide="user"></i>' : '<i data-lucide="scale"></i>';
  const contentDiv = document.createElement('div');
  contentDiv.className = 'message-content markdown-body';
  if (m.role === 'assistant') contentDiv.innerHTML = renderMarkdown(m.content);
  else contentDiv.textContent = m.content;
  messageDiv.appendChild(avatar);
  messageDiv.appendChild(contentDiv);
  container.appendChild(messageDiv);
  refreshIcons();
  container.scrollTop = container.scrollHeight;
}

function deleteCase(id, event) {
  if (event) event.stopPropagation();
  if (!confirm('Delete this case and its saved conversation? This cannot be undone.')) return;
  saveCases(loadCases().filter(c => c.id !== id));
  if (localStorage.getItem('adhikaar_active_case') === id) {
    localStorage.removeItem('adhikaar_active_case');
    updateCaseBanner();
    clearChat();
  }
  renderCases();
  renderChatSidebar();
}

function addDeadline(id, event) {
  if (event) event.stopPropagation();
  const label = prompt('What is the deadline for? (e.g., "Reply to legal notice")');
  if (!label) return;
  const date = prompt('Deadline date (YYYY-MM-DD):');
  if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) { alert('Please use YYYY-MM-DD format.'); return; }
  const cases = loadCases();
  const c = cases.find(x => x.id === id);
  if (!c) return;
  c.deadlines.push({ label: label.trim(), date });
  c.updatedAt = Date.now();
  saveCases(cases);
  renderCases();
}

function nearestDeadline(c) {
  const today = new Date().toISOString().slice(0, 10);
  const future = (c.deadlines || []).filter(d => d.date >= today).sort((a, b) => a.date.localeCompare(b.date));
  return future[0] || null;
}

function renderCases() {
  const grid = $('cases-grid');
  if (!grid) return;
  const cases = loadCases();
  const activeId = localStorage.getItem('adhikaar_active_case');

  const toolbar = document.querySelector('.cases-toolbar');
  if (cases.length === 0) {
    if (toolbar) toolbar.style.display = 'none';
    grid.innerHTML = `<div class="cases-empty">
      <div class="cases-empty-icon"><i data-lucide="folder-open"></i></div>
      <h3>No cases yet</h3>
      <p>A case keeps one legal matter organized — its conversation, documents, and deadlines together, private on this device.</p>
      <button class="btn btn-primary" onclick="createCase()"><i data-lucide="plus"></i> ${t('ncase') || 'New Case'}</button>
    </div>`;
    refreshIcons();
    return;
  }
  if (toolbar) toolbar.style.display = '';

  grid.innerHTML = cases.map(c => {
    const dl = nearestDeadline(c);
    const today = new Date().toISOString().slice(0, 10);
    const soon = dl && (new Date(dl.date) - new Date(today)) / 86400000 <= 7;
    return `
    <div class="case-card ${c.id === activeId ? 'active-case' : ''}" onclick="openCase('${c.id}')">
      <div class="case-card-header">
        <h3>${escapeHtml(c.title)}</h3>
        ${c.id === activeId ? '<span class="case-badge">Active</span>' : ''}
      </div>
      <p class="case-summary">${escapeHtml(c.summary || 'No conversation yet')}</p>
      <div class="case-meta">
        <span><i data-lucide="message-circle"></i> ${c.history.length} messages</span>
        <span><i data-lucide="file-text"></i> ${(c.drafts || []).length} drafts</span>
      </div>
      ${dl ? `<div class="case-deadline ${soon ? 'deadline-soon' : ''}">
        <i data-lucide="alarm-clock"></i> ${escapeHtml(dl.label)} — ${dl.date}
      </div>` : ''}
      <div class="case-actions">
        <button class="btn btn-sm btn-secondary" onclick="addDeadline('${c.id}', event)"><i data-lucide="calendar-plus"></i> Deadline</button>
        <button class="btn btn-sm btn-secondary case-delete" onclick="deleteCase('${c.id}', event)"><i data-lucide="trash-2"></i></button>
      </div>
    </div>`;
  }).join('');
  refreshIcons();
}

function updateCaseBanner() {
  const c = getActiveCase();
  const statusEl = document.querySelector('.chat-status span:last-child');
  if (statusEl) statusEl.textContent = c ? `Case: ${c.title}` : 'Ready to help';
}

// ══════════════════════════════════════════════════════════════
// DOCUMENT DRAFTING ENGINE
// ══════════════════════════════════════════════════════════════

const DRAFT_TYPES = {
  legal_notice: {
    title: 'Legal Notice',
    fields: [
      ['sender_name', 'Your full name'],
      ['sender_address', 'Your full address'],
      ['recipient_name', 'Name of the person/company you are sending this to'],
      ['recipient_address', 'Their address'],
      ['dispute_details', 'What happened? (dates, amounts, promises broken)'],
      ['demand', 'What do you want them to do? (e.g., pay ₹50,000)'],
      ['deadline_days', 'Days to comply (usually 15 or 30)'],
    ],
  },
  consumer_complaint: {
    title: 'Consumer Complaint',
    fields: [
      ['complainant_name', 'Your full name'],
      ['complainant_address', 'Your full address'],
      ['opposite_party', 'Company/seller name and address'],
      ['purchase_details', 'What did you buy? (product/service, date, amount paid, receipt number)'],
      ['problem', 'What went wrong? (defect, deficiency, unfair practice)'],
      ['relief_sought', 'What do you want? (refund, replacement, compensation amount)'],
    ],
  },
  rti_application: {
    title: 'RTI Application',
    fields: [
      ['applicant_name', 'Your full name'],
      ['applicant_address', 'Your full address'],
      ['department', 'Which government office/department has the information?'],
      ['information_sought', 'What exact information do you want? (be specific)'],
      ['period', 'For what time period? (e.g., Jan 2025 to Dec 2025)'],
    ],
  },
  police_complaint: {
    title: 'Police Complaint',
    fields: [
      ['complainant_name', 'Your full name'],
      ['complainant_address', 'Your full address and phone number'],
      ['police_station', 'Police station name and area'],
      ['incident_details', 'What happened? (date, time, place, who was involved)'],
      ['accused_details', 'Who did it? (names/descriptions if known)'],
      ['evidence', 'Any evidence or witnesses?'],
    ],
  },
};

let currentDraftType = null;
let lastDraftText = '';

function selectDraftType(type) {
  currentDraftType = type;
  const def = DRAFT_TYPES[type];
  document.querySelectorAll('.draft-type-card').forEach(c =>
    c.classList.toggle('selected', c.dataset.doctype === type));
  $('draft-form-title').textContent = def.title + ' — fill in the details';
  $('draft-form').innerHTML = def.fields.map(([key, label]) => `
    <div class="draft-field">
      <label for="draft-${key}">${label}</label>
      ${key.includes('details') || key.includes('problem') || key.includes('sought') || key.includes('demand')
        ? `<textarea id="draft-${key}" rows="3"></textarea>`
        : `<input type="text" id="draft-${key}">`}
    </div>`).join('');
  $('draft-form-container').style.display = 'block';
  $('draft-result-container').style.display = 'none';
  $('draft-form-container').scrollIntoView({ behavior: 'smooth' });
}

async function generateDraft() {
  if (!currentDraftType) return;
  const def = DRAFT_TYPES[currentDraftType];
  const fields = {};
  let allFilled = true;
  def.fields.forEach(([key, label]) => {
    const el = $(`draft-${key}`);
    if (el && el.value.trim()) {
      fields[label] = el.value.trim();
    } else {
      allFilled = false;
    }
  });

  if (!allFilled) {
    alert("Please fill all options to generate the PDF/Document.");
    return;
  }

  const btn = $('draft-generate-btn');
  btn.disabled = true;
  btn.innerHTML = '<i data-lucide="loader-2"></i> Drafting… this can take a minute';
  refreshIcons();

  try {
    const data = await apiCall('/api/draft-document', {
      method: 'POST',
      body: JSON.stringify({
        doc_type: currentDraftType,
        fields: fields,
        situation: state.lastSituation,
        language: state.language,
      }),
    });
    lastDraftText = data.response;
    $('draft-result').innerHTML = renderMarkdown(data.response);
    $('draft-result-container').style.display = 'block';
    $('draft-result-container').scrollIntoView({ behavior: 'smooth' });
  } catch (e) {
    alert('Could not generate the document. Check that the server and Ollama are running.');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i data-lucide="sparkles"></i> Generate Document';
    refreshIcons();
  }
}

function downloadDraft() {
  if (!lastDraftText) return;
  const html = `<html><head><meta charset="utf-8"></head><body style="font-family: 'Times New Roman', serif; font-size: 12pt; line-height: 1.6;">${renderMarkdown(lastDraftText)}</body></html>`;
  const blob = new Blob([html], { type: 'application/msword' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `${DRAFT_TYPES[currentDraftType]?.title || 'document'}.doc`;
  a.click();
  URL.revokeObjectURL(a.href);
}

function printDraft() {
  if (!lastDraftText) return;
  const w = window.open('', '_blank');
  w.document.write(`<html><head><title>Print</title></head><body style="font-family: 'Times New Roman', serif; font-size: 12pt; line-height: 1.6; padding: 2cm;">${renderMarkdown(lastDraftText)}</body></html>`);
  w.document.close();
  w.print();
}

function saveDraftToCase() {
  if (!lastDraftText) return;
  const c = getActiveCase();
  if (!c) { alert('Open or create a case first (My Cases), then save the draft to it.'); return; }
  const cases = loadCases();
  const target = cases.find(x => x.id === c.id);
  target.drafts.push({ type: currentDraftType, text: lastDraftText, createdAt: Date.now() });
  target.updatedAt = Date.now();
  saveCases(cases);
  alert(`Draft saved to case: ${target.title}`);
  renderCases();
}

// ══════════════════════════════════════════════════════════════
// VIRTUAL COURTROOM
// ══════════════════════════════════════════════════════════════

const courtroom = { round: 0, situation: '', history: '' };

const COURT_EXAMPLES = [
  'My landlord in Delhi is refusing to return my ₹50,000 security deposit. I vacated the flat 3 months ago with proper notice and have photos showing the flat was in good condition. He claims I damaged the walls but has shown no proof or bills.',
  'I worked at a private company in Pune for 2 years. They have not paid my last 3 months of salary (₹45,000/month) and terminated me without notice. I have my appointment letter, salary slips, and WhatsApp messages where HR admits the dues.',
  'I lent ₹2 lakh to a friend for his business. He gave me a cheque which bounced twice due to insufficient funds. I have the cheque, the bank return memo, and a written loan agreement. It has been 20 days since the second bounce.',
];

function courtExample(i) {
  const ta = $('courtroom-situation');
  if (ta) { ta.value = COURT_EXAMPLES[i] || ''; ta.focus(); }
}

function prefillCourtroom() {
  const ta = $('courtroom-situation');
  if (ta && !ta.value.trim() && state.lastSituation) ta.value = state.lastSituation;
}

async function startCourtroom() {
  const situation = $('courtroom-situation').value.trim();
  if (!situation) { alert('Please describe your case first.'); return; }
  courtroom.situation = situation;
  $('courtroom-rounds').innerHTML = '';
  $('courtroom-setup').style.display = 'none';
  $('courtroom-stage').style.display = 'block';

  const roundDiv = document.createElement('div');
  roundDiv.className = 'court-round';
  roundDiv.innerHTML = `<div class="court-round-label">Hearing in Session</div>
    <div class="court-loading"><div class="typing-dots"><span></span><span></span><span></span></div> The court is deliberating…</div>`;
  $('courtroom-rounds').appendChild(roundDiv);
  roundDiv.scrollIntoView({ behavior: 'smooth' });

  try {
    const data = await apiCall('/api/courtroom', {
      method: 'POST',
      body: JSON.stringify({
        situation: courtroom.situation,
        language: state.language,
      }),
    });
    
    roundDiv.querySelector('.court-loading').remove();
    
    let html = '';
    if (data.messages && data.messages.length > 0) {
      data.messages.forEach(msg => {
        if (msg.role === 'YOUR_LAWYER') {
          html += courtBubble('your-lawyer', 'shield', 'Your Lawyer', msg.text);
        } else if (msg.role === 'OPPOSING_LAWYER') {
          html += courtBubble('opposing', 'swords', 'Opposing Lawyer', msg.text);
        } else if (msg.role === 'NEXT_STEPS') {
          html += courtBubble('judge', 'clipboard-list', 'Next Steps', msg.text);
        }
      });
    }
    
    roundDiv.innerHTML += html;
    refreshIcons();
  } catch (e) {
    let hint = e.message || 'Unknown error';
    roundDiv.querySelector('.court-loading').innerHTML = `⚠️ ${escapeHtml(hint)} Try again.`;
  }
}

function courtBubble(cls, icon, name, text) {
  return `<div class="court-bubble ${cls}">
    <div class="court-speaker"><i data-lucide="${icon}"></i> ${name}</div>
    <div class="markdown-body">${renderMarkdown(text)}</div>
  </div>`;
}

function resetCourtroom() {
  $('courtroom-rounds').innerHTML = '';
  $('courtroom-setup').style.display = 'block';
  $('courtroom-stage').style.display = 'none';
}

// ══════════════════════════════════════════════════════════════
// KIOSK / VOICE-FIRST MODE
// ══════════════════════════════════════════════════════════════

const kiosk = { active: false, recognition: null, lastAnswer: '', busy: false };

function enterKioskMode() {
  kiosk.active = true;
  $('kiosk-overlay').classList.add('active');
  document.documentElement.requestFullscreen?.().catch(() => {});
  const greeting = state.language === 'hi' || state.language === 'hinglish'
    ? 'नमस्ते! मैं आपकी कानूनी मदद के लिए हूँ। माइक दबाकर अपनी समस्या बताइए।'
    : 'Namaste! I am here to help you understand your legal rights. Press the mic and tell me your problem.';
  $('kiosk-text').textContent = greeting;
  $('kiosk-answer').innerHTML = '';
  $('kiosk-repeat-btn').style.display = 'none';
  refreshIcons();
  speak(greeting);
}

function exitKioskMode() {
  kiosk.active = false;
  $('kiosk-overlay').classList.remove('active');
  window.speechSynthesis?.cancel();
  if (kiosk.recognition) try { kiosk.recognition.stop(); } catch (e) {}
  document.exitFullscreen?.().catch(() => {});
}

function speechLang() {
  const lang = LANGUAGES.find(l => l.code === state.language);
  return lang ? (lang.speechCode || 'en-IN') : 'en-IN';
}

function stripForSpeech(text) {
  return text
    .replace(/[#*_`>|-]/g, ' ')
    .replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}]/gu, '')
    .replace(/\[.*?\]\(.*?\)/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

// getVoices() populates asynchronously — cache it and refresh on 'voiceschanged'.
let ttsVoices = [];
function loadVoices() {
  ttsVoices = window.speechSynthesis ? (window.speechSynthesis.getVoices() || []) : [];
}

// Find the best available voice for a BCP-47 code (exact match, then base language).
function pickVoice(langCode) {
  if (!ttsVoices.length) loadVoices();
  if (!ttsVoices.length) return null;
  const lc = langCode.toLowerCase();
  const base = lc.split('-')[0];
  return ttsVoices.find(v => v.lang && v.lang.toLowerCase() === lc)
      || ttsVoices.find(v => v.lang && v.lang.toLowerCase().startsWith(base))
      || null;
}

function speak(text, opts = {}) {
  if (!window.speechSynthesis) { opts.onDone && opts.onDone(); return false; }
  window.speechSynthesis.cancel();
  const clean = stripForSpeech(text);
  if (!clean) { opts.onDone && opts.onDone(); return false; }

  const lang = speechLang();
  const voice = pickVoice(lang);
  // If the OS has no voice for this language, warn — and (when the user
  // pressed Listen) tell them, instead of failing silently.
  if (!voice) {
    console.warn(`[tts] No installed voice for "${lang}". Speech may be silent or use a default voice.`);
    if (opts.notify) {
      showToast("Audio isn't available for this language on your device — showing the text instead.");
    }
  }

  // Chunk long text so speechSynthesis doesn't cut off mid-answer
  const chunks = (clean.match(/[^.।!?]+[.।!?]?/g) || [clean]).filter(c => c.trim());
  if (!chunks.length) { opts.onDone && opts.onDone(); return false; }
  chunks.forEach((chunk, idx) => {
    const u = new SpeechSynthesisUtterance(chunk.trim());
    u.lang = lang;
    if (voice) u.voice = voice;
    u.rate = 0.95;
    if (idx === chunks.length - 1 && opts.onDone) u.onend = opts.onDone;
    window.speechSynthesis.speak(u);
  });
  return true;
}

// ── Listen / Stop control for chat answers ──
let activeSpeakBtn = null;

function toggleSpeak(btn, text) {
  // Tapping the button that's currently speaking stops it
  if (activeSpeakBtn === btn) { stopSpeaking(); return; }
  stopSpeaking();   // stop any other answer being read
  const started = speak(text, { notify: true, onDone: resetSpeakBtn });
  if (started && btn) {
    activeSpeakBtn = btn;
    btn.innerHTML = '<i data-lucide="square"></i> Stop';
    refreshIcons();
  }
}

function stopSpeaking() {
  window.speechSynthesis?.cancel();
  resetSpeakBtn();
}

function resetSpeakBtn() {
  if (activeSpeakBtn) {
    activeSpeakBtn.innerHTML = '<i data-lucide="volume-2"></i> Listen';
    activeSpeakBtn = null;
    refreshIcons();
  }
}

// ── Auto-read-every-answer toggle ──
function toggleAutoSpeak() {
  state.autoSpeak = !state.autoSpeak;
  localStorage.setItem('adhikaar_autospeak', state.autoSpeak ? '1' : '0');
  updateAutoSpeakBtn();
  if (!state.autoSpeak) stopSpeaking();
  showToast(state.autoSpeak ? 'Answers will now be read aloud automatically.' : 'Auto-read turned off.');
}

function updateAutoSpeakBtn() {
  const btn = $('autospeak-btn');
  if (!btn) return;
  btn.classList.toggle('active', !!state.autoSpeak);
  btn.title = state.autoSpeak ? 'Auto-read answers: ON' : 'Auto-read answers: OFF';
}

// ── Approximate Devanagari → Latin transliteration (for Hinglish voice) ──
function transliterateHiToLatin(str) {
  if (!str) return str;
  const V = { 'अ':'a','आ':'aa','इ':'i','ई':'ee','उ':'u','ऊ':'oo','ऋ':'ri','ए':'e','ऐ':'ai','ओ':'o','औ':'au','ं':'n','ः':'h','ँ':'n' };
  const M = { 'ा':'aa','ि':'i','ी':'ee','ु':'u','ू':'oo','ृ':'ri','े':'e','ै':'ai','ो':'o','ौ':'au','्':'' };
  const C = { 'क':'k','ख':'kh','ग':'g','घ':'gh','ङ':'ng','च':'ch','छ':'chh','ज':'j','झ':'jh','ञ':'ny','ट':'t','ठ':'th','ड':'d','ढ':'dh','ण':'n','त':'t','थ':'th','द':'d','ध':'dh','न':'n','प':'p','फ':'ph','ब':'b','भ':'bh','म':'m','य':'y','र':'r','ल':'l','व':'v','श':'sh','ष':'sh','स':'s','ह':'h','ड़':'r','ढ़':'rh','फ़':'f','ज़':'z','ख़':'kh','ग़':'g','क़':'q' };
  const chars = Array.from(str);
  let out = '';
  for (let i = 0; i < chars.length; i++) {
    const ch = chars[i];
    if (C[ch] !== undefined) {
      out += C[ch];
      const next = chars[i + 1];
      if (M[next] !== undefined) { out += M[next]; i++; }      // matra follows
      else if (next === '्') { i++; }                          // halant: no inherent vowel
      else { out += 'a'; }                                     // inherent 'a'
    } else if (V[ch] !== undefined) {
      out += V[ch];
    } else if (M[ch] !== undefined) {
      out += M[ch];
    } else {
      out += ch;   // spaces, digits, punctuation, Latin pass through
    }
  }
  return out;
}

function kioskRepeat() {
  if (kiosk.lastAnswer) speak(kiosk.lastAnswer);
}

function kioskListen() {
  if (kiosk.busy) return;
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    $('kiosk-text').textContent = 'Voice is not supported in this browser. Please use Chrome.';
    return;
  }
  window.speechSynthesis?.cancel();

  kiosk.recognition = new SpeechRecognition();
  kiosk.recognition.lang = speechLang();
  kiosk.recognition.interimResults = true;

  const micBtn = $('kiosk-mic-btn');
  micBtn.classList.add('listening');
  $('kiosk-text').textContent = state.language === 'hi' ? 'सुन रहा हूँ…' : 'Listening…';

  kiosk.recognition.onresult = (event) => {
    const transcript = Array.from(event.results).map(r => r[0].transcript).join('');
    $('kiosk-text').textContent = transcript;
    kiosk.transcript = transcript;
  };

  kiosk.recognition.onend = async () => {
    micBtn.classList.remove('listening');
    const question = (kiosk.transcript || '').trim();
    kiosk.transcript = '';
    if (!question) return;

    kiosk.busy = true;
    $('kiosk-text').textContent = state.language === 'hi' ? 'सोच रहा हूँ… कृपया प्रतीक्षा करें' : 'Thinking… please wait';
    try {
      const data = await apiCall('/api/chat', {
        method: 'POST',
        body: JSON.stringify({ message: question, language: state.language, session_id: state.sessionId }),
      });
      kiosk.lastAnswer = data.response;
      $('kiosk-text').textContent = '';
      $('kiosk-answer').innerHTML = renderMarkdown(data.response);
      $('kiosk-repeat-btn').style.display = '';
      refreshIcons();
      speak(data.response);
      persistToActiveCase('user', question);
      persistToActiveCase('assistant', data.response);
    } catch (e) {
      const msg = state.language === 'hi' ? 'माफ़ कीजिए, कुछ गड़बड़ हुई। फिर कोशिश करें।' : 'Sorry, something went wrong. Please try again.';
      $('kiosk-text').textContent = msg;
      speak(msg);
    } finally {
      kiosk.busy = false;
    }
  };

  kiosk.recognition.onerror = () => {
    micBtn.classList.remove('listening');
    $('kiosk-text').textContent = state.language === 'hi' ? 'सुनाई नहीं दिया — फिर से माइक दबाएं' : "I couldn't hear you — press the mic and try again";
  };

  kiosk.recognition.start();
}

// ══════════════════════════════════════════════════════════════
// HOME PAGE MINI CHAT
// ══════════════════════════════════════════════════════════════

function homeChatAsk(text) {
  const input = $('home-chat-input');
  input.value = text;
  homeChatSend();
}

function homeChatVoice() {
  if (activeRecognition) { stopDictation(); return; }
  const input = $('home-chat-input');
  startDictation(input, $('home-chat-mic'), { onStop: () => { if (input) input.focus(); } });
}

// The home input is a doorway into the real chatbot: it navigates to the
// chat view and sends the question through the normal chat flow.
function homeChatSend() {
  const input = $('home-chat-input');
  const message = input.value.trim();
  if (!message) return;
  input.value = '';
  navigateTo('chat');
  const chatInput = $('chat-input');
  if (chatInput) {
    chatInput.value = message;
    sendMessage();
  }
}

// ── Global quick-ask bar (visible on all feature pages) ──

function quickAskSend() {
  const input = $('global-ask-input');
  const message = input.value.trim();
  if (!message) return;
  input.value = '';
  navigateTo('chat');
  const chatInput = $('chat-input');
  if (chatInput) {
    chatInput.value = message;
    sendMessage();
  }
}

function quickAskVoice() {
  if (activeRecognition) { stopDictation(); return; }
  const input = $('global-ask-input');
  startDictation(input, $('global-ask-mic'), { onStop: () => { if (input) input.focus(); } });
}

// ══════════════════════════════════════════════════════════════
// THEME (light default, dark opt-in)
// ══════════════════════════════════════════════════════════════

function initTheme() {
  const saved = localStorage.getItem('adhikaar_theme') || 'light';
  document.documentElement.dataset.theme = saved;
  updateThemeButton(saved);
}

function toggleTheme() {
  const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  localStorage.setItem('adhikaar_theme', next);
  updateThemeButton(next);
}

function updateThemeButton(theme) {
  const btn = $('theme-toggle');
  if (!btn) return;
  btn.innerHTML = theme === 'dark'
    ? '<i data-lucide="sun"></i> <span id="theme-label">Light mode</span>'
    : '<i data-lucide="moon"></i> <span id="theme-label">Dark mode</span>';
  refreshIcons();
}

initTheme();

// ══════════════════════════════════════════════════════════════
// I18N — Multi-language interface translations
// ══════════════════════════════════════════════════════════════

const I18N = {
en: { nav_home:'Home', nav_chat:'Talk to Legal Helper', nav_cases:'My Cases', nav_draft:'Draft a Document', nav_court:'Virtual Courtroom', nav_bns:'Section Converter', nav_crpc:'CrPC ↔ BNSS Converter', nav_aid:'Find Legal Aid', nav_doc:'Translate Legal Document',
badge:'100% private · runs on your device', hero_sub:'Salary not paid? Deposit stuck? Got a legal notice? Ask in Hindi, English, or 9 other languages — free, offline, nothing leaves your computer.', cta1:'Ask Your Question', cta2:'See How It Works',
tr1:'No signup', tr2:'Works offline', tr3:'11 languages', tr4:'Free forever',
st1:'IPC ↔ BNS sections mapped', st2:'Indian languages supported', st3:'Data sent to the cloud',
how:'How It Works', s1t:'Describe your problem', s1d:'Type or speak in any of 11 languages. No legal words needed.', s2t:'Confirm the summary', s2d:'The AI restates your situation — you verify it understood correctly.', s3t:'Get rights + next steps', s3d:'Clear guidance with BNS sections, deadlines, and helplines.',
feats:'Everything अधिKaar Can Do', open:'Open',
f1t:'Talk to Legal Helper', f1d:'Describe your problem in any of 11 languages — get rights, steps, and deadlines.', f2t:'My Cases', f2d:'Keep each legal matter organized — private on your device.', f3t:'Draft a Document', f3d:'Ready-to-print legal notices, complaints, and RTI applications.', f4t:'Virtual Courtroom', f4d:'Watch both sides argue your case before an AI judge.', f5t:'IPC ↔ BNS Converter', f5d:'Convert old IPC sections to new BNS sections instantly.', f6t:'Find Legal Aid', f6d:'Free legal aid offices and helplines in your district.', f7t:'Translate Legal Documents', f7d:'Upload a notice or summons — get it explained simply.', f8t:'Voice Mode', f8d:'Speak your question and hear the answer aloud.',
hg:'Hello, how can I help you today?', hc1:'What are tenant rights in India?', hc2:'How to file a consumer complaint?', hc3:'Explain Domestic Violence Act', hph:'Type your legal question...', hnote:'Free to use. Your conversations stay on your device.',
ct:'Legal Helper', cst:'Ready to help', cnew:'New Chat', wt:'Welcome to अधिKaar', wd:"Tell me about your legal problem in your own words. I'll help you understand your rights and options.",
c1:'Unpaid salary', c2:'Security deposit', c3:'Got a legal notice', c4:'FIR not filed', c5:'Domestic violence', c6:'Online fraud',
cph:'Describe your legal problem here...', chint:'Press Enter to send · Shift+Enter for new line · tap the mic for voice input', cdisc:'अधिKaar provides legal information, not legal advice. For complex matters, consult a qualified lawyer or call NALSA: 15100.',
bns_t:'IPC ↔ BNS Section Converter', bns_d:'India\'s criminal law changed on 1 July 2024. Search any IPC or BNS section to find its equivalent.', aid_t:'Find Legal Aid Near You', aid_d:'Free legal assistance is your right. Find DLSA offices, helplines, and Tele-Law services.', doc_t:'Translate Legal Document', doc_d:'Upload a photo of your legal notice, FIR, or court summons — we\'ll explain it in simple words.',
cases_t:'My Cases', cases_d:'Each case keeps its own conversation, documents, and deadlines — saved privately on this device.', draft_t:'Draft a Legal Document', draft_d:'Answer a few questions and get a ready-to-use document you can print and submit.', court_t:'Virtual Courtroom', court_d:'Watch both sides argue your case before an AI judge — and find your weak points before the other side does.',
ncase:'New Case', shear:'Start Hearing', nround:'Next Round', vmode:'Voice Mode / आवाज़ मोड' },

hi: { nav_home:'होम', nav_chat:'कानूनी सहायक से बात करें', nav_cases:'मेरे केस', nav_draft:'दस्तावेज़ बनाएं', nav_court:'वर्चुअल अदालत', nav_bns:'सेक्शन परिवर्तक', nav_crpc:'CrPC ↔ BNSS परिवर्तक', nav_aid:'कानूनी सहायता खोजें', nav_doc:'कानूनी दस्तावेज़ समझें',
badge:'100% निजी · आपके डिवाइस पर चलता है', hero_sub:'वेतन नहीं मिला? जमा राशि फंसी है? कानूनी नोटिस मिला? हिंदी, अंग्रेज़ी या 9 अन्य भाषाओं में पूछें — मुफ्त, ऑफलाइन, आपका डेटा बाहर नहीं जाता।', cta1:'अपना सवाल पूछें', cta2:'कैसे काम करता है देखें',
tr1:'साइनअप नहीं चाहिए', tr2:'ऑफलाइन चलता है', tr3:'11 भाषाएं', tr4:'हमेशा मुफ्त',
st1:'IPC ↔ BNS धाराएं जोड़ी गईं', st2:'भारतीय भाषाएं समर्थित', st3:'क्लाउड को भेजा गया डेटा',
how:'यह कैसे काम करता है', s1t:'अपनी समस्या बताएं', s1d:'11 भाषाओं में लिखें या बोलें। कानूनी शब्द ज़रूरी नहीं।', s2t:'सारांश की पुष्टि करें', s2d:'AI आपकी स्थिति दोहराता है — आप जांचें कि सही समझा।', s3t:'अधिकार और अगले कदम पाएं', s3d:'BNS धाराओं, समय-सीमाओं और हेल्पलाइन के साथ स्पष्ट मार्गदर्शन।',
feats:'अधिKaar की सभी सुविधाएं', open:'खोलें',
f1t:'कानूनी सहायक से बात करें', f1d:'11 भाषाओं में समस्या बताएं — अधिकार, कदम और समय-सीमा पाएं।', f2t:'मेरे केस', f2d:'हर कानूनी मामला व्यवस्थित — आपके डिवाइस पर निजी।', f3t:'दस्तावेज़ बनाएं', f3d:'छपने-योग्य कानूनी नोटिस, शिकायतें और RTI आवेदन।', f4t:'वर्चुअल अदालत', f4d:'AI जज के सामने दोनों पक्षों की बहस देखें।', f5t:'IPC ↔ BNS परिवर्तक', f5d:'पुरानी IPC धाराओं को नई BNS धाराओं में बदलें।', f6t:'कानूनी सहायता खोजें', f6d:'आपके जिले में मुफ्त कानूनी सहायता और हेल्पलाइन।', f7t:'कानूनी दस्तावेज़ समझें', f7d:'नोटिस या समन अपलोड करें — सरल भाषा में समझें।', f8t:'आवाज़ मोड', f8d:'बोलकर पूछें और जवाब सुनें।',
hg:'नमस्ते, मैं आपकी क्या मदद कर सकता हूँ?', hc1:'भारत में किरायेदार के अधिकार क्या हैं?', hc2:'उपभोक्ता शिकायत कैसे दर्ज करें?', hc3:'घरेलू हिंसा अधिनियम समझाएं', hph:'अपना कानूनी सवाल लिखें...', hnote:'उपयोग मुफ्त है। आपकी बातचीत आपके डिवाइस पर रहती है।',
ct:'कानूनी सहायक', cst:'मदद के लिए तैयार', cnew:'नई बातचीत', wt:'अधिKaar में आपका स्वागत है', wd:'अपनी कानूनी समस्या अपने शब्दों में बताइए। मैं आपके अधिकार और विकल्प समझने में मदद करूँगा।',
c1:'वेतन नहीं मिला', c2:'जमा राशि', c3:'कानूनी नोटिस मिला', c4:'FIR दर्ज नहीं हुई', c5:'घरेलू हिंसा', c6:'ऑनलाइन धोखाधड़ी',
cph:'अपनी कानूनी समस्या यहाँ लिखें...', chint:'भेजने के लिए Enter · नई पंक्ति के लिए Shift+Enter · आवाज़ के लिए माइक दबाएं', cdisc:'अधिKaar कानूनी जानकारी देता है, कानूनी सलाह नहीं। जटिल मामलों में वकील से मिलें या NALSA को कॉल करें: 15100।',
bns_t:'IPC ↔ BNS धारा परिवर्तक', bns_d:'1 जुलाई 2024 को आपराधिक कानून बदला। कोई भी IPC या BNS धारा खोजें।', aid_t:'नज़दीकी कानूनी सहायता खोजें', aid_d:'मुफ्त कानूनी सहायता आपका अधिकार है। DLSA कार्यालय, हेल्पलाइन और टेली-लॉ सेवाएं खोजें।', doc_t:'कानूनी दस्तावेज़ समझें', doc_d:'नोटिस, FIR या समन की फोटो अपलोड करें — हम सरल शब्दों में समझाएंगे।',
cases_t:'मेरे केस', cases_d:'हर केस की बातचीत, दस्तावेज़ और समय-सीमाएं — इसी डिवाइस पर निजी।', draft_t:'कानूनी दस्तावेज़ बनाएं', draft_d:'कुछ सवालों के जवाब दें और छापने-जमा करने योग्य दस्तावेज़ पाएं।', court_t:'वर्चुअल अदालत', court_d:'AI जज के सामने दोनों पक्षों की बहस देखें — अपनी कमजोरियां पहले जानें।',
ncase:'नया केस', shear:'सुनवाई शुरू करें', nround:'अगला दौर', vmode:'आवाज़ मोड' },

hinglish: { nav_home:'Home', nav_chat:'Legal Helper se baat karein', nav_cases:'Mere Cases', nav_draft:'Document banayein', nav_court:'Virtual Adalat', nav_bns:'Section Converter', nav_crpc:'CrPC ↔ BNSS Converter', nav_aid:'Legal Aid dhundein', nav_doc:'Legal Document samjhein',
badge:'100% private · aapke device par chalta hai', hero_sub:'Salary nahi mili? Deposit atka hai? Legal notice aaya? Hindi, English ya 9 aur bhashaon mein poochein — free, offline, data bahar nahi jaata.', cta1:'Apna sawaal poochein', cta2:'Kaise kaam karta hai dekhein',
tr1:'No signup', tr2:'Offline chalta hai', tr3:'11 bhashayein', tr4:'Hamesha free',
st1:'IPC ↔ BNS sections mapped', st2:'Bhartiya bhashayein', st3:'Cloud ko bheja gaya data',
how:'Yeh kaise kaam karta hai', s1t:'Apni problem batayein', s1d:'11 bhashaon mein likhein ya bolein.', s2t:'Summary confirm karein', s2d:'AI aapki baat dohrata hai — aap check karein.', s3t:'Rights aur agle kadam', s3d:'BNS sections, deadlines aur helplines ke saath.',
feats:'अधिKaar ke saare features', open:'Kholein',
f1t:'Legal Helper se baat karein', f1d:'11 bhashaon mein problem batayein — rights aur steps paayein.', f2t:'Mere Cases', f2d:'Har case organized — device par private.', f3t:'Document banayein', f3d:'Print-ready notices, complaints aur RTI.', f4t:'Virtual Adalat', f4d:'AI judge ke saamne dono taraf ki behas.', f5t:'IPC ↔ BNS Converter', f5d:'Purani IPC ko nayi BNS mein badlein.', f6t:'Legal Aid dhundein', f6d:'Aapke zile mein free legal aid.', f7t:'Legal Document samjhein', f7d:'Notice ya summons upload karein — simple mein samjhein.', f8t:'Voice Mode', f8d:'Bolkar poochein, jawab sunein.',
hg:'Namaste, main aapki kya madad kar sakta hoon?', hc1:'India mein tenant rights kya hain?', hc2:'Consumer complaint kaise file karein?', hc3:'Domestic Violence Act samjhaayein', hph:'Apna legal sawaal likhein...', hnote:'Free hai. Aapki baatcheet device par rehti hai.',
ct:'Legal Helper', cst:'Madad ke liye taiyaar', cnew:'Nayi Chat', wt:'अधिKaar mein swagat hai', wd:'Apni legal problem apne shabdon mein batayein.',
c1:'Salary nahi mili', c2:'Security deposit', c3:'Legal notice aaya', c4:'FIR nahi hui', c5:'Gharelu hinsa', c6:'Online fraud',
cph:'Apni legal problem yahan likhein...', chint:'Enter se bhejein · Shift+Enter nayi line · mic se bolein', cdisc:'अधिKaar legal information deta hai, advice nahi. Complex cases mein vakil se milein ya NALSA: 15100.',
bns_t:'IPC ↔ BNS Section Converter', bns_d:'1 July 2024 ko criminal law badla. Koi bhi section search karein.', aid_t:'Nazdeeki Legal Aid', aid_d:'Free legal aid aapka haq hai. DLSA, helplines aur Tele-Law dhundein.', doc_t:'Legal Document samjhein', doc_d:'Notice, FIR ya summons ki photo upload karein.',
cases_t:'Mere Cases', cases_d:'Har case ki baatcheet aur deadlines — device par private.', draft_t:'Legal Document banayein', draft_d:'Kuch sawaal, ready document.', court_t:'Virtual Adalat', court_d:'AI judge ke saamne behas dekhein — kamzori pehle jaanein.',
ncase:'Naya Case', shear:'Sunwai shuru karein', nround:'Agla Round', vmode:'Voice Mode' },

ta: { nav_home:'முகப்பு', nav_chat:'சட்ட உதவியாளரிடம் பேசுங்கள்', nav_cases:'என் வழக்குகள்', nav_draft:'ஆவணம் உருவாக்கு', nav_court:'மெய்நிகர் நீதிமன்றம்', nav_bns:'IPC ↔ BNS மாற்றி', nav_aid:'சட்ட உதவி தேடு', nav_doc:'சட்ட ஆவணம் விளக்கு',
badge:'100% தனிப்பட்டது · உங்கள் சாதனத்தில் இயங்குகிறது', hero_sub:'சம்பளம் வரவில்லையா? வைப்புத்தொகை சிக்கியதா? சட்ட நோட்டீஸ் வந்ததா? 11 மொழிகளில் கேளுங்கள் — இலவசம், ஆஃப்லைன்.', cta1:'உங்கள் கேள்வியைக் கேளுங்கள்', cta2:'எப்படி வேலை செய்கிறது',
tr1:'பதிவு தேவையில்லை', tr2:'ஆஃப்லைனில் இயங்கும்', tr3:'11 மொழிகள்', tr4:'எப்போதும் இலவசம்',
st1:'IPC ↔ BNS பிரிவுகள்', st2:'இந்திய மொழிகள்', st3:'கிளவுடுக்கு அனுப்பிய தரவு',
how:'இது எப்படி வேலை செய்கிறது', s1t:'உங்கள் பிரச்சனையை சொல்லுங்கள்', s1d:'11 மொழிகளில் எழுதுங்கள் அல்லது பேசுங்கள்.', s2t:'சுருக்கத்தை உறுதிசெய்யுங்கள்', s2d:'AI உங்கள் நிலையை மீண்டும் கூறும் — நீங்கள் சரிபார்க்கவும்.', s3t:'உரிமைகள் + அடுத்த படிகள்', s3d:'BNS பிரிவுகள், காலக்கெடுக்கள், உதவி எண்களுடன்.',
feats:'அధிKaar செய்யக்கூடியவை', open:'திற',
f1t:'சட்ட உதவியாளரிடம் பேசுங்கள்', f1d:'11 மொழிகளில் பிரச்சனையை சொல்லுங்கள்.', f2t:'என் வழக்குகள்', f2d:'ஒவ்வொரு வழக்கும் ஒழுங்காக — தனிப்பட்டதாக.', f3t:'ஆவணம் உருவாக்கு', f3d:'அச்சிடத் தயாரான நோட்டீஸ்கள் மற்றும் RTI.', f4t:'மெய்நிகர் நீதிமன்றம்', f4d:'AI நீதிபதி முன் இரு தரப்பு வாதம்.', f5t:'IPC ↔ BNS மாற்றி', f5d:'பழைய IPC பிரிவுகளை புதிய BNS ஆக மாற்றுங்கள்.', f6t:'சட்ட உதவி தேடு', f6d:'உங்கள் மாவட்டத்தில் இலவச சட்ட உதவி.', f7t:'சட்ட ஆவணம் விளக்கு', f7d:'நோட்டீஸை பதிவேற்றுங்கள் — எளிமையாக புரிந்துகொள்ளுங்கள்.', f8t:'குரல் முறை', f8d:'பேசிக் கேளுங்கள், பதிலைக் கேளுங்கள்.',
hg:'வணக்கம், நான் எப்படி உதவலாம்?', hc1:'இந்தியாவில் குடியிருப்பாளர் உரிமைகள் என்ன?', hc2:'நுகர்வோர் புகார் எப்படி அளிப்பது?', hc3:'குடும்ப வன்முறை சட்டத்தை விளக்குங்கள்', hph:'உங்கள் சட்டக் கேள்வியை எழுதுங்கள்...', hnote:'இலவசம். உங்கள் உரையாடல்கள் உங்கள் சாதனத்திலேயே இருக்கும்.',
ct:'சட்ட உதவியாளர்', cst:'உதவத் தயார்', cnew:'புதிய உரையாடல்', wt:'அధிKaar-க்கு வரவேற்கிறோம்', wd:'உங்கள் சட்டப் பிரச்சனையை உங்கள் வார்த்தைகளில் சொல்லுங்கள்.',
c1:'சம்பளம் வரவில்லை', c2:'வைப்புத்தொகை', c3:'சட்ட நோட்டீஸ்', c4:'FIR பதிவாகவில்லை', c5:'குடும்ப வன்முறை', c6:'ஆன்லைன் மோசடி',
cph:'உங்கள் சட்டப் பிரச்சனையை இங்கே எழுதுங்கள்...', chint:'அனுப்ப Enter · புதிய வரிக்கு Shift+Enter · பேச மைக்', cdisc:'அధிKaar சட்டத் தகவல் தருகிறது, ஆலோசனை அல்ல. சிக்கலான விஷயங்களுக்கு வழக்கறிஞரை அணுகவும் அல்லது NALSA: 15100.',
bns_t:'IPC ↔ BNS பிரிவு மாற்றி', bns_d:'1 ஜூலை 2024 அன்று குற்றவியல் சட்டம் மாறியது. எந்த பிரிவையும் தேடுங்கள்.', aid_t:'அருகிலுள்ள சட்ட உதவி', aid_d:'இலவச சட்ட உதவி உங்கள் உரிமை. DLSA, உதவி எண்கள் தேடுங்கள்.', doc_t:'சட்ட ஆவணம் விளக்கு', doc_d:'நோட்டீஸ், FIR புகைப்படத்தை பதிவேற்றுங்கள்.',
cases_t:'என் வழக்குகள்', cases_d:'ஒவ்வொரு வழக்கின் உரையாடலும் இந்த சாதனத்தில் தனிப்பட்டதாக.', draft_t:'சட்ட ஆவணம் உருவாக்கு', draft_d:'சில கேள்விகள் — தயார் ஆவணம்.', court_t:'மெய்நிகர் நீதிமன்றம்', court_d:'AI நீதிபதி முன் வாதம் — பலவீனங்களை முன்பே அறியுங்கள்.',
ncase:'புதிய வழக்கு', shear:'விசாரணை தொடங்கு', nround:'அடுத்த சுற்று', vmode:'குரல் முறை' },

te: { nav_home:'హోమ్', nav_chat:'లీగల్ హెల్పర్‌తో మాట్లాడండి', nav_cases:'నా కేసులు', nav_draft:'పత్రం రూపొందించండి', nav_court:'వర్చువల్ కోర్టు', nav_bns:'IPC ↔ BNS మార్పిడి', nav_aid:'న్యాయ సహాయం వెతకండి', nav_doc:'చట్ట పత్రం వివరించండి',
badge:'100% ప్రైవేట్ · మీ పరికరంలో నడుస్తుంది', hero_sub:'జీతం రాలేదా? డిపాజిట్ ఇరుక్కుందా? లీగల్ నోటీసు వచ్చిందా? 11 భాషల్లో అడగండి — ఉచితం, ఆఫ్‌లైన్.', cta1:'మీ ప్రశ్న అడగండి', cta2:'ఎలా పనిచేస్తుందో చూడండి',
tr1:'సైన్అప్ అవసరం లేదు', tr2:'ఆఫ్‌లైన్‌లో పనిచేస్తుంది', tr3:'11 భాషలు', tr4:'ఎప్పటికీ ఉచితం',
st1:'IPC ↔ BNS సెక్షన్లు', st2:'భారతీయ భాషలు', st3:'క్లౌడ్‌కు పంపిన డేటా',
how:'ఇది ఎలా పనిచేస్తుంది', s1t:'మీ సమస్య చెప్పండి', s1d:'11 భాషల్లో రాయండి లేదా మాట్లాడండి.', s2t:'సారాంశం నిర్ధారించండి', s2d:'AI మీ పరిస్థితిని మళ్లీ చెబుతుంది — మీరు సరిచూడండి.', s3t:'హక్కులు + తదుపరి అడుగులు', s3d:'BNS సెక్షన్లు, గడువులు, హెల్ప్‌లైన్లతో.',
feats:'అధిKaar చేయగలిగినవన్నీ', open:'తెరవండి',
f1t:'లీగల్ హెల్పర్‌తో మాట్లాడండి', f1d:'11 భాషల్లో సమస్య చెప్పండి — హక్కులు పొందండి.', f2t:'నా కేసులు', f2d:'ప్రతి కేసు క్రమంగా — మీ పరికరంలో ప్రైవేట్.', f3t:'పత్రం రూపొందించండి', f3d:'ప్రింట్-రెడీ నోటీసులు, ఫిర్యాదులు, RTI.', f4t:'వర్చువల్ కోర్టు', f4d:'AI న్యాయమూర్తి ముందు రెండు వైపుల వాదన.', f5t:'IPC ↔ BNS మార్పిడి', f5d:'పాత IPC సెక్షన్లను కొత్త BNSగా మార్చండి.', f6t:'న్యాయ సహాయం వెతకండి', f6d:'మీ జిల్లాలో ఉచిత న్యాయ సహాయం.', f7t:'చట్ట పత్రం వివరించండి', f7d:'నోటీసు అప్‌లోడ్ చేయండి — సరళంగా అర్థం చేసుకోండి.', f8t:'వాయిస్ మోడ్', f8d:'మాట్లాడి అడగండి, జవాబు వినండి.',
hg:'నమస్తే, నేను మీకు ఎలా సహాయం చేయగలను?', hc1:'భారతదేశంలో అద్దెదారు హక్కులు ఏమిటి?', hc2:'వినియోగదారు ఫిర్యాదు ఎలా చేయాలి?', hc3:'గృహ హింస చట్టం వివరించండి', hph:'మీ చట్ట ప్రశ్న రాయండి...', hnote:'ఉచితం. మీ సంభాషణలు మీ పరికరంలోనే ఉంటాయి.',
ct:'లీగల్ హెల్పర్', cst:'సహాయానికి సిద్ధం', cnew:'కొత్త సంభాషణ', wt:'అధిKaar కు స్వాగతం', wd:'మీ చట్టపరమైన సమస్యను మీ మాటల్లో చెప్పండి.',
c1:'జీతం రాలేదు', c2:'సెక్యూరిటీ డిపాజిట్', c3:'లీగల్ నోటీసు', c4:'FIR నమోదు కాలేదు', c5:'గృహ హింస', c6:'ఆన్‌లైన్ మోసం',
cph:'మీ చట్టపరమైన సమస్యను ఇక్కడ రాయండి...', chint:'పంపడానికి Enter · కొత్త లైన్ Shift+Enter · మాట్లాడటానికి మైక్', cdisc:'అధిKaar చట్ట సమాచారం ఇస్తుంది, సలహా కాదు. క్లిష్ట విషయాలకు న్యాయవాదిని కలవండి లేదా NALSA: 15100.',
bns_t:'IPC ↔ BNS సెక్షన్ మార్పిడి', bns_d:'1 జూలై 2024న నేర చట్టం మారింది. ఏ సెక్షన్ అయినా వెతకండి.', aid_t:'సమీప న్యాయ సహాయం', aid_d:'ఉచిత న్యాయ సహాయం మీ హక్కు. DLSA, హెల్ప్‌లైన్లు వెతకండి.', doc_t:'చట్ట పత్రం వివరించండి', doc_d:'నోటీసు, FIR ఫోటో అప్‌లోడ్ చేయండి.',
cases_t:'నా కేసులు', cases_d:'ప్రతి కేసు సంభాషణ ఈ పరికరంలో ప్రైవేట్‌గా.', draft_t:'చట్ట పత్రం రూపొందించండి', draft_d:'కొన్ని ప్రశ్నలు — సిద్ధమైన పత్రం.', court_t:'వర్చువల్ కోర్టు', court_d:'AI న్యాయమూర్తి ముందు వాదన — బలహీనతలు ముందే తెలుసుకోండి.',
ncase:'కొత్త కేసు', shear:'విచారణ ప్రారంభించండి', nround:'తదుపరి రౌండ్', vmode:'వాయిస్ మోడ్' },

bn: { nav_home:'হোম', nav_chat:'আইনি সহায়কের সাথে কথা বলুন', nav_cases:'আমার মামলা', nav_draft:'নথি তৈরি করুন', nav_court:'ভার্চুয়াল আদালত', nav_bns:'IPC ↔ BNS রূপান্তর', nav_aid:'আইনি সহায়তা খুঁজুন', nav_doc:'আইনি নথি বুঝুন',
badge:'100% ব্যক্তিগত · আপনার ডিভাইসে চলে', hero_sub:'বেতন পাননি? জামানত আটকে আছে? আইনি নোটিশ পেয়েছেন? 11টি ভাষায় জিজ্ঞাসা করুন — বিনামূল্যে, অফলাইন।', cta1:'আপনার প্রশ্ন করুন', cta2:'কীভাবে কাজ করে দেখুন',
tr1:'সাইনআপ লাগে না', tr2:'অফলাইনে চলে', tr3:'11টি ভাষা', tr4:'চিরকাল বিনামূল্যে',
st1:'IPC ↔ BNS ধারা', st2:'ভারতীয় ভাষা', st3:'ক্লাউডে পাঠানো ডেটা',
how:'এটি কীভাবে কাজ করে', s1t:'আপনার সমস্যা বলুন', s1d:'11টি ভাষায় লিখুন বা বলুন।', s2t:'সারাংশ নিশ্চিত করুন', s2d:'AI আপনার পরিস্থিতি পুনরায় বলে — আপনি যাচাই করুন।', s3t:'অধিকার + পরবর্তী পদক্ষেপ', s3d:'BNS ধারা, সময়সীমা ও হেল্পলাইনসহ।',
feats:'অধিKaar যা যা করতে পারে', open:'খুলুন',
f1t:'আইনি সহায়কের সাথে কথা বলুন', f1d:'11টি ভাষায় সমস্যা বলুন — অধিকার জানুন।', f2t:'আমার মামলা', f2d:'প্রতিটি মামলা গোছানো — ডিভাইসে ব্যক্তিগত।', f3t:'নথি তৈরি করুন', f3d:'প্রিন্ট-রেডি নোটিশ, অভিযোগ ও RTI।', f4t:'ভার্চুয়াল আদালত', f4d:'AI বিচারকের সামনে দুই পক্ষের যুক্তি।', f5t:'IPC ↔ BNS রূপান্তর', f5d:'পুরনো IPC ধারা নতুন BNS-এ বদলান।', f6t:'আইনি সহায়তা খুঁজুন', f6d:'আপনার জেলায় বিনামূল্যে আইনি সহায়তা।', f7t:'আইনি নথি বুঝুন', f7d:'নোটিশ আপলোড করুন — সহজ ভাষায় বুঝুন।', f8t:'ভয়েস মোড', f8d:'বলে জিজ্ঞাসা করুন, উত্তর শুনুন।',
hg:'নমস্কার, আমি কীভাবে সাহায্য করতে পারি?', hc1:'ভারতে ভাড়াটিয়ার অধিকার কী?', hc2:'ভোক্তা অভিযোগ কীভাবে করবেন?', hc3:'গার্হস্থ্য হিংসা আইন ব্যাখ্যা করুন', hph:'আপনার আইনি প্রশ্ন লিখুন...', hnote:'বিনামূল্যে। আপনার কথোপকথন আপনার ডিভাইসেই থাকে।',
ct:'আইনি সহায়ক', cst:'সাহায্যের জন্য প্রস্তুত', cnew:'নতুন কথোপকথন', wt:'অধিKaar-এ স্বাগতম', wd:'আপনার আইনি সমস্যা নিজের ভাষায় বলুন।',
c1:'বেতন পাইনি', c2:'জামানত', c3:'আইনি নোটিশ', c4:'FIR হয়নি', c5:'গার্হস্থ্য হিংসা', c6:'অনলাইন প্রতারণা',
cph:'আপনার আইনি সমস্যা এখানে লিখুন...', chint:'পাঠাতে Enter · নতুন লাইনে Shift+Enter · বলতে মাইক', cdisc:'অধিKaar আইনি তথ্য দেয়, পরামর্শ নয়। জটিল বিষয়ে আইনজীবীর সাথে দেখা করুন বা NALSA: 15100।',
bns_t:'IPC ↔ BNS ধারা রূপান্তর', bns_d:'1 জুলাই 2024-এ ফৌজদারি আইন বদলেছে। যেকোনো ধারা খুঁজুন।', aid_t:'কাছের আইনি সহায়তা', aid_d:'বিনামূল্যে আইনি সহায়তা আপনার অধিকার। DLSA, হেল্পলাইন খুঁজুন।', doc_t:'আইনি নথি বুঝুন', doc_d:'নোটিশ, FIR-এর ছবি আপলোড করুন।',
cases_t:'আমার মামলা', cases_d:'প্রতিটি মামলার কথোপকথন এই ডিভাইসে ব্যক্তিগত।', draft_t:'আইনি নথি তৈরি করুন', draft_d:'কয়েকটি প্রশ্ন — প্রস্তুত নথি।', court_t:'ভার্চুয়াল আদালত', court_d:'AI বিচারকের সামনে যুক্তি — দুর্বলতা আগে জানুন।',
ncase:'নতুন মামলা', shear:'শুনানি শুরু করুন', nround:'পরবর্তী রাউন্ড', vmode:'ভয়েস মোড' },

mr: { nav_home:'होम', nav_chat:'कायदेशीर मदतनीसाशी बोला', nav_cases:'माझी प्रकरणे', nav_draft:'दस्तऐवज तयार करा', nav_court:'व्हर्च्युअल न्यायालय', nav_bns:'IPC ↔ BNS रूपांतर', nav_aid:'कायदेशीर मदत शोधा', nav_doc:'कायदेशीर दस्तऐवज समजून घ्या',
badge:'100% खाजगी · तुमच्या डिव्हाइसवर चालते', hero_sub:'पगार मिळाला नाही? डिपॉझिट अडकले? कायदेशीर नोटीस आली? 11 भाषांमध्ये विचारा — मोफत, ऑफलाइन.', cta1:'तुमचा प्रश्न विचारा', cta2:'कसे काम करते ते पहा',
tr1:'साइनअप नको', tr2:'ऑफलाइन चालते', tr3:'11 भाषा', tr4:'कायम मोफत',
st1:'IPC ↔ BNS कलमे', st2:'भारतीय भाषा', st3:'क्लाउडला पाठवलेला डेटा',
how:'हे कसे काम करते', s1t:'तुमची समस्या सांगा', s1d:'11 भाषांमध्ये लिहा किंवा बोला.', s2t:'सारांश निश्चित करा', s2d:'AI तुमची परिस्थिती पुन्हा सांगते — तुम्ही तपासा.', s3t:'हक्क + पुढील पावले', s3d:'BNS कलमे, मुदती आणि हेल्पलाइनसह.',
feats:'अधिKaar काय काय करू शकते', open:'उघडा',
f1t:'कायदेशीर मदतनीसाशी बोला', f1d:'11 भाषांमध्ये समस्या सांगा — हक्क जाणून घ्या.', f2t:'माझी प्रकरणे', f2d:'प्रत्येक प्रकरण व्यवस्थित — डिव्हाइसवर खाजगी.', f3t:'दस्तऐवज तयार करा', f3d:'छापण्यायोग्य नोटीस, तक्रारी आणि RTI.', f4t:'व्हर्च्युअल न्यायालय', f4d:'AI न्यायाधीशासमोर दोन्ही बाजूंचा युक्तिवाद.', f5t:'IPC ↔ BNS रूपांतर', f5d:'जुनी IPC कलमे नवीन BNS मध्ये बदला.', f6t:'कायदेशीर मदत शोधा', f6d:'तुमच्या जिल्ह्यात मोफत कायदेशीर मदत.', f7t:'कायदेशीर दस्तऐवज समजून घ्या', f7d:'नोटीस अपलोड करा — सोप्या भाषेत समजून घ्या.', f8t:'व्हॉइस मोड', f8d:'बोलून विचारा, उत्तर ऐका.',
hg:'नमस्कार, मी तुमची कशी मदत करू?', hc1:'भारतात भाडेकरूचे हक्क काय आहेत?', hc2:'ग्राहक तक्रार कशी दाखल करावी?', hc3:'घरगुती हिंसाचार कायदा समजावून सांगा', hph:'तुमचा कायदेशीर प्रश्न लिहा...', hnote:'मोफत. तुमचे संभाषण तुमच्या डिव्हाइसवरच राहते.',
ct:'कायदेशीर मदतनीस', cst:'मदतीसाठी तयार', cnew:'नवीन संभाषण', wt:'अधिKaar मध्ये स्वागत आहे', wd:'तुमची कायदेशीर समस्या तुमच्या शब्दांत सांगा.',
c1:'पगार मिळाला नाही', c2:'डिपॉझिट', c3:'कायदेशीर नोटीस', c4:'FIR नोंदवली नाही', c5:'घरगुती हिंसाचार', c6:'ऑनलाइन फसवणूक',
cph:'तुमची कायदेशीर समस्या इथे लिहा...', chint:'पाठवण्यासाठी Enter · नवीन ओळ Shift+Enter · बोलण्यासाठी माइक', cdisc:'अधिKaar कायदेशीर माहिती देते, सल्ला नाही. गुंतागुंतीच्या प्रकरणांसाठी वकिलांना भेटा किंवा NALSA: 15100.',
bns_t:'IPC ↔ BNS कलम रूपांतर', bns_d:'1 जुलै 2024 रोजी फौजदारी कायदा बदलला. कोणतेही कलम शोधा.', aid_t:'जवळची कायदेशीर मदत', aid_d:'मोफत कायदेशीर मदत तुमचा हक्क आहे. DLSA, हेल्पलाइन शोधा.', doc_t:'कायदेशीर दस्तऐवज समजून घ्या', doc_d:'नोटीस, FIR चा फोटो अपलोड करा.',
cases_t:'माझी प्रकरणे', cases_d:'प्रत्येक प्रकरणाचे संभाषण या डिव्हाइसवर खाजगी.', draft_t:'कायदेशीर दस्तऐवज तयार करा', draft_d:'काही प्रश्न — तयार दस्तऐवज.', court_t:'व्हर्च्युअल न्यायालय', court_d:'AI न्यायाधीशासमोर युक्तिवाद — कमकुवतपणा आधी जाणा.',
ncase:'नवीन प्रकरण', shear:'सुनावणी सुरू करा', nround:'पुढील फेरी', vmode:'व्हॉइस मोड' },

gu: { nav_home:'હોમ', nav_chat:'કાનૂની સહાયક સાથે વાત કરો', nav_cases:'મારા કેસ', nav_draft:'દસ્તાવેજ બનાવો', nav_court:'વર્ચ્યુઅલ કોર્ટ', nav_bns:'IPC ↔ BNS રૂપાંતર', nav_aid:'કાનૂની સહાય શોધો', nav_doc:'કાનૂની દસ્તાવેજ સમજો',
badge:'100% ખાનગી · તમારા ડિવાઇસ પર ચાલે છે', hero_sub:'પગાર નથી મળ્યો? ડિપોઝિટ અટકી છે? કાનૂની નોટિસ મળી? 11 ભાષાઓમાં પૂછો — મફત, ઑફલાઇન.', cta1:'તમારો પ્રશ્ન પૂછો', cta2:'કેવી રીતે કામ કરે છે જુઓ',
tr1:'સાઇનઅપ નહીં', tr2:'ઑફલાઇન ચાલે છે', tr3:'11 ભાષાઓ', tr4:'હંમેશા મફત',
st1:'IPC ↔ BNS કલમો', st2:'ભારતીય ભાષાઓ', st3:'ક્લાઉડને મોકલેલો ડેટા',
how:'આ કેવી રીતે કામ કરે છે', s1t:'તમારી સમસ્યા કહો', s1d:'11 ભાષાઓમાં લખો અથવા બોલો.', s2t:'સારાંશ ખાતરી કરો', s2d:'AI તમારી પરિસ્થિતિ ફરી કહે છે — તમે ચકાસો.', s3t:'હક્કો + આગળનાં પગલાં', s3d:'BNS કલમો, સમયમર્યાદા અને હેલ્પલાઇન સાથે.',
feats:'અધિKaar શું શું કરી શકે', open:'ખોલો',
f1t:'કાનૂની સહાયક સાથે વાત કરો', f1d:'11 ભાષાઓમાં સમસ્યા કહો — હક્કો જાણો.', f2t:'મારા કેસ', f2d:'દરેક કેસ વ્યવસ્થિત — ડિવાઇસ પર ખાનગી.', f3t:'દસ્તાવેજ બનાવો', f3d:'પ્રિન્ટ-રેડી નોટિસ, ફરિયાદો અને RTI.', f4t:'વર્ચ્યુઅલ કોર્ટ', f4d:'AI ન્યાયાધીશ સામે બંને પક્ષોની દલીલ.', f5t:'IPC ↔ BNS રૂપાંતર', f5d:'જૂની IPC કલમો નવી BNS માં બદલો.', f6t:'કાનૂની સહાય શોધો', f6d:'તમારા જિલ્લામાં મફત કાનૂની સહાય.', f7t:'કાનૂની દસ્તાવેજ સમજો', f7d:'નોટિસ અપલોડ કરો — સરળ ભાષામાં સમજો.', f8t:'વૉઇસ મોડ', f8d:'બોલીને પૂછો, જવાબ સાંભળો.',
hg:'નમસ્તે, હું તમારી કેવી રીતે મદદ કરી શકું?', hc1:'ભારતમાં ભાડૂતના હક્કો શું છે?', hc2:'ગ્રાહક ફરિયાદ કેવી રીતે કરવી?', hc3:'ઘરેલુ હિંસા કાયદો સમજાવો', hph:'તમારો કાનૂની પ્રશ્ન લખો...', hnote:'મફત. તમારી વાતચીત તમારા ડિવાઇસ પર જ રહે છે.',
ct:'કાનૂની સહાયક', cst:'મદદ માટે તૈયાર', cnew:'નવી વાતચીત', wt:'અધિKaar માં આપનું સ્વાગત છે', wd:'તમારી કાનૂની સમસ્યા તમારા શબ્દોમાં કહો.',
c1:'પગાર નથી મળ્યો', c2:'ડિપોઝિટ', c3:'કાનૂની નોટિસ', c4:'FIR નોંધાઈ નથી', c5:'ઘરેલુ હિંસા', c6:'ઑનલાઇન છેતરપિંડી',
cph:'તમારી કાનૂની સમસ્યા અહીં લખો...', chint:'મોકલવા Enter · નવી લાઇન Shift+Enter · બોલવા માઇક', cdisc:'અધિKaar કાનૂની માહિતી આપે છે, સલાહ નહીં. જટિલ બાબતો માટે વકીલને મળો અથવા NALSA: 15100.',
bns_t:'IPC ↔ BNS કલમ રૂપાંતર', bns_d:'1 જુલાઈ 2024ના રોજ ફોજદારી કાયદો બદલાયો. કોઈપણ કલમ શોધો.', aid_t:'નજીકની કાનૂની સહાય', aid_d:'મફત કાનૂની સહાય તમારો હક છે. DLSA, હેલ્પલાઇન શોધો.', doc_t:'કાનૂની દસ્તાવેજ સમજો', doc_d:'નોટિસ, FIR નો ફોટો અપલોડ કરો.',
cases_t:'મારા કેસ', cases_d:'દરેક કેસની વાતચીત આ ડિવાઇસ પર ખાનગી.', draft_t:'કાનૂની દસ્તાવેજ બનાવો', draft_d:'થોડા પ્રશ્નો — તૈયાર દસ્તાવેજ.', court_t:'વર્ચ્યુઅલ કોર્ટ', court_d:'AI ન્યાયાધીશ સામે દલીલ — નબળાઈઓ પહેલા જાણો.',
ncase:'નવો કેસ', shear:'સુનાવણી શરૂ કરો', nround:'આગળનો રાઉન્ડ', vmode:'વૉઇસ મોડ' },

kn: { nav_home:'ಹೋಮ್', nav_chat:'ಕಾನೂನು ಸಹಾಯಕರೊಂದಿಗೆ ಮಾತನಾಡಿ', nav_cases:'ನನ್ನ ಪ್ರಕರಣಗಳು', nav_draft:'ದಾಖಲೆ ರಚಿಸಿ', nav_court:'ವರ್ಚುವಲ್ ನ್ಯಾಯಾಲಯ', nav_bns:'IPC ↔ BNS ಪರಿವರ್ತಕ', nav_aid:'ಕಾನೂನು ನೆರವು ಹುಡುಕಿ', nav_doc:'ಕಾನೂನು ದಾಖಲೆ ವಿವರಿಸಿ',
badge:'100% ಖಾಸಗಿ · ನಿಮ್ಮ ಸಾಧನದಲ್ಲಿ ಚಲಿಸುತ್ತದೆ', hero_sub:'ಸಂಬಳ ಬಂದಿಲ್ಲವೇ? ಠೇವಣಿ ಸಿಲುಕಿದೆಯೇ? ಕಾನೂನು ನೋಟಿಸ್ ಬಂದಿದೆಯೇ? 11 ಭಾಷೆಗಳಲ್ಲಿ ಕೇಳಿ — ಉಚಿತ, ಆಫ್‌ಲೈನ್.', cta1:'ನಿಮ್ಮ ಪ್ರಶ್ನೆ ಕೇಳಿ', cta2:'ಹೇಗೆ ಕೆಲಸ ಮಾಡುತ್ತದೆ ನೋಡಿ',
tr1:'ಸೈನ್ಅಪ್ ಬೇಡ', tr2:'ಆಫ್‌ಲೈನ್ ಚಲಿಸುತ್ತದೆ', tr3:'11 ಭಾಷೆಗಳು', tr4:'ಶಾಶ್ವತ ಉಚಿತ',
st1:'IPC ↔ BNS ವಿಭಾಗಗಳು', st2:'ಭಾರತೀಯ ಭಾಷೆಗಳು', st3:'ಕ್ಲೌಡ್‌ಗೆ ಕಳುಹಿಸಿದ ಡೇಟಾ',
how:'ಇದು ಹೇಗೆ ಕೆಲಸ ಮಾಡುತ್ತದೆ', s1t:'ನಿಮ್ಮ ಸಮಸ್ಯೆ ಹೇಳಿ', s1d:'11 ಭಾಷೆಗಳಲ್ಲಿ ಬರೆಯಿರಿ ಅಥವಾ ಮಾತನಾಡಿ.', s2t:'ಸಾರಾಂಶ ದೃಢೀಕರಿಸಿ', s2d:'AI ನಿಮ್ಮ ಪರಿಸ್ಥಿತಿಯನ್ನು ಮತ್ತೆ ಹೇಳುತ್ತದೆ — ನೀವು ಪರಿಶೀಲಿಸಿ.', s3t:'ಹಕ್ಕುಗಳು + ಮುಂದಿನ ಹೆಜ್ಜೆಗಳು', s3d:'BNS ವಿಭಾಗಗಳು, ಗಡುವುಗಳು, ಸಹಾಯವಾಣಿಗಳೊಂದಿಗೆ.',
feats:'ಅಧಿKaar ಮಾಡಬಹುದಾದದ್ದೆಲ್ಲ', open:'ತೆರೆಯಿರಿ',
f1t:'ಕಾನೂನು ಸಹಾಯಕರೊಂದಿಗೆ ಮಾತನಾಡಿ', f1d:'11 ಭಾಷೆಗಳಲ್ಲಿ ಸಮಸ್ಯೆ ಹೇಳಿ — ಹಕ್ಕುಗಳನ್ನು ತಿಳಿಯಿರಿ.', f2t:'ನನ್ನ ಪ್ರಕರಣಗಳು', f2d:'ಪ್ರತಿ ಪ್ರಕರಣ ವ್ಯವಸ್ಥಿತ — ಸಾಧನದಲ್ಲಿ ಖಾಸಗಿ.', f3t:'ದಾಖಲೆ ರಚಿಸಿ', f3d:'ಪ್ರಿಂಟ್-ರೆಡಿ ನೋಟಿಸ್, ದೂರುಗಳು ಮತ್ತು RTI.', f4t:'ವರ್ಚುವಲ್ ನ್ಯಾಯಾಲಯ', f4d:'AI ನ್ಯಾಯಾಧೀಶರ ಮುಂದೆ ಎರಡೂ ಕಡೆಯ ವಾದ.', f5t:'IPC ↔ BNS ಪರಿವರ್ತಕ', f5d:'ಹಳೆಯ IPC ವಿಭಾಗಗಳನ್ನು ಹೊಸ BNS ಗೆ ಬದಲಿಸಿ.', f6t:'ಕಾನೂನು ನೆರವು ಹುಡುಕಿ', f6d:'ನಿಮ್ಮ ಜಿಲ್ಲೆಯಲ್ಲಿ ಉಚಿತ ಕಾನೂನು ನೆರವು.', f7t:'ಕಾನೂನು ದಾಖಲೆ ವಿವರಿಸಿ', f7d:'ನೋಟಿಸ್ ಅಪ್‌ಲೋಡ್ ಮಾಡಿ — ಸರಳವಾಗಿ ಅರ್ಥಮಾಡಿಕೊಳ್ಳಿ.', f8t:'ಧ್ವನಿ ಮೋಡ್', f8d:'ಮಾತನಾಡಿ ಕೇಳಿ, ಉತ್ತರ ಕೇಳಿ.',
hg:'ನಮಸ್ತೆ, ನಾನು ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಹುದು?', hc1:'ಭಾರತದಲ್ಲಿ ಬಾಡಿಗೆದಾರರ ಹಕ್ಕುಗಳೇನು?', hc2:'ಗ್ರಾಹಕ ದೂರು ಹೇಗೆ ಸಲ್ಲಿಸುವುದು?', hc3:'ಗೃಹ ಹಿಂಸೆ ಕಾಯ್ದೆ ವಿವರಿಸಿ', hph:'ನಿಮ್ಮ ಕಾನೂನು ಪ್ರಶ್ನೆ ಬರೆಯಿರಿ...', hnote:'ಉಚಿತ. ನಿಮ್ಮ ಸಂಭಾಷಣೆಗಳು ನಿಮ್ಮ ಸಾಧನದಲ್ಲಿಯೇ ಇರುತ್ತವೆ.',
ct:'ಕಾನೂನು ಸಹಾಯಕ', cst:'ಸಹಾಯಕ್ಕೆ ಸಿದ್ಧ', cnew:'ಹೊಸ ಸಂಭಾಷಣೆ', wt:'ಅಧಿKaar ಗೆ ಸ್ವಾಗತ', wd:'ನಿಮ್ಮ ಕಾನೂನು ಸಮಸ್ಯೆಯನ್ನು ನಿಮ್ಮ ಮಾತಿನಲ್ಲಿ ಹೇಳಿ.',
c1:'ಸಂಬಳ ಬಂದಿಲ್ಲ', c2:'ಠೇವಣಿ', c3:'ಕಾನೂನು ನೋಟಿಸ್', c4:'FIR ದಾಖಲಾಗಿಲ್ಲ', c5:'ಗೃಹ ಹಿಂಸೆ', c6:'ಆನ್‌ಲೈನ್ ವಂಚನೆ',
cph:'ನಿಮ್ಮ ಕಾನೂನು ಸಮಸ್ಯೆಯನ್ನು ಇಲ್ಲಿ ಬರೆಯಿರಿ...', chint:'ಕಳುಹಿಸಲು Enter · ಹೊಸ ಸಾಲಿಗೆ Shift+Enter · ಮಾತನಾಡಲು ಮೈಕ್', cdisc:'ಅಧಿKaar ಕಾನೂನು ಮಾಹಿತಿ ನೀಡುತ್ತದೆ, ಸಲಹೆ ಅಲ್ಲ. ಸಂಕೀರ್ಣ ವಿಷಯಗಳಿಗೆ ವಕೀಲರನ್ನು ಭೇಟಿ ಮಾಡಿ ಅಥವಾ NALSA: 15100.',
bns_t:'IPC ↔ BNS ವಿಭಾಗ ಪರಿವರ್ತಕ', bns_d:'1 ಜುಲೈ 2024 ರಂದು ಅಪರಾಧ ಕಾನೂನು ಬದಲಾಯಿತು. ಯಾವುದೇ ವಿಭಾಗ ಹುಡುಕಿ.', aid_t:'ಹತ್ತಿರದ ಕಾನೂನು ನೆರವು', aid_d:'ಉಚಿತ ಕಾನೂನು ನೆರವು ನಿಮ್ಮ ಹಕ್ಕು. DLSA, ಸಹಾಯವಾಣಿ ಹುಡುಕಿ.', doc_t:'ಕಾನೂನು ದಾಖಲೆ ವಿವರಿಸಿ', doc_d:'ನೋಟಿಸ್, FIR ಫೋಟೋ ಅಪ್‌ಲೋಡ್ ಮಾಡಿ.',
cases_t:'ನನ್ನ ಪ್ರಕರಣಗಳು', cases_d:'ಪ್ರತಿ ಪ್ರಕರಣದ ಸಂಭಾಷಣೆ ಈ ಸಾಧನದಲ್ಲಿ ಖಾಸಗಿ.', draft_t:'ಕಾನೂನು ದಾಖಲೆ ರಚಿಸಿ', draft_d:'ಕೆಲವು ಪ್ರಶ್ನೆಗಳು — ಸಿದ್ಧ ದಾಖಲೆ.', court_t:'ವರ್ಚುವಲ್ ನ್ಯಾಯಾಲಯ', court_d:'AI ನ್ಯಾಯಾಧೀಶರ ಮುಂದೆ ವಾದ — ದೌರ್ಬಲ್ಯ ಮೊದಲೇ ತಿಳಿಯಿರಿ.',
ncase:'ಹೊಸ ಪ್ರಕರಣ', shear:'ವಿಚಾರಣೆ ಪ್ರಾರಂಭಿಸಿ', nround:'ಮುಂದಿನ ಸುತ್ತು', vmode:'ಧ್ವನಿ ಮೋಡ್' },

ml: { nav_home:'ഹോം', nav_chat:'നിയമ സഹായിയോട് സംസാരിക്കുക', nav_cases:'എന്റെ കേസുകൾ', nav_draft:'രേഖ തയ്യാറാക്കുക', nav_court:'വെർച്വൽ കോടതി', nav_bns:'IPC ↔ BNS മാറ്റം', nav_aid:'നിയമ സഹായം കണ്ടെത്തുക', nav_doc:'നിയമ രേഖ വിശദീകരിക്കുക',
badge:'100% സ്വകാര്യം · നിങ്ങളുടെ ഉപകരണത്തിൽ പ്രവർത്തിക്കുന്നു', hero_sub:'ശമ്പളം കിട്ടിയില്ലേ? ഡെപ്പോസിറ്റ് കുടുങ്ങിയോ? നിയമ നോട്ടീസ് വന്നോ? 11 ഭാഷകളിൽ ചോദിക്കൂ — സൗജന്യം, ഓഫ്‌ലൈൻ.', cta1:'നിങ്ങളുടെ ചോദ്യം ചോദിക്കുക', cta2:'എങ്ങനെ പ്രവർത്തിക്കുന്നു കാണുക',
tr1:'സൈൻഅപ്പ് വേണ്ട', tr2:'ഓഫ്‌ലൈനിൽ പ്രവർത്തിക്കുന്നു', tr3:'11 ഭാഷകൾ', tr4:'എന്നും സൗജന്യം',
st1:'IPC ↔ BNS വകുപ്പുകൾ', st2:'ഇന്ത്യൻ ഭാഷകൾ', st3:'ക്ലൗഡിലേക്ക് അയച്ച ഡാറ്റ',
how:'ഇത് എങ്ങനെ പ്രവർത്തിക്കുന്നു', s1t:'നിങ്ങളുടെ പ്രശ്നം പറയുക', s1d:'11 ഭാഷകളിൽ എഴുതുകയോ സംസാരിക്കുകയോ ചെയ്യുക.', s2t:'സംഗ്രഹം സ്ഥിരീകരിക്കുക', s2d:'AI നിങ്ങളുടെ സാഹചര്യം വീണ്ടും പറയുന്നു — നിങ്ങൾ പരിശോധിക്കുക.', s3t:'അവകാശങ്ങൾ + അടുത്ത ഘട്ടങ്ങൾ', s3d:'BNS വകുപ്പുകൾ, സമയപരിധികൾ, ഹെൽപ്പ്‌ലൈനുകൾ സഹിതം.',
feats:'അധിKaar ചെയ്യാവുന്നതെല്ലാം', open:'തുറക്കുക',
f1t:'നിയമ സഹായിയോട് സംസാരിക്കുക', f1d:'11 ഭാഷകളിൽ പ്രശ്നം പറയുക — അവകാശങ്ങൾ അറിയുക.', f2t:'എന്റെ കേസുകൾ', f2d:'ഓരോ കേസും ക്രമീകൃതം — ഉപകരണത്തിൽ സ്വകാര്യം.', f3t:'രേഖ തയ്യാറാക്കുക', f3d:'പ്രിന്റ്-റെഡി നോട്ടീസുകൾ, പരാതികൾ, RTI.', f4t:'വെർച്വൽ കോടതി', f4d:'AI ജഡ്ജിക്ക് മുന്നിൽ ഇരുവശത്തിന്റെയും വാദം.', f5t:'IPC ↔ BNS മാറ്റം', f5d:'പഴയ IPC വകുപ്പുകൾ പുതിയ BNS ആക്കുക.', f6t:'നിയമ സഹായം കണ്ടെത്തുക', f6d:'നിങ്ങളുടെ ജില്ലയിൽ സൗജന്യ നിയമ സഹായം.', f7t:'നിയമ രേഖ വിശദീകരിക്കുക', f7d:'നോട്ടീസ് അപ്‌ലോഡ് ചെയ്യുക — ലളിതമായി മനസ്സിലാക്കുക.', f8t:'വോയ്സ് മോഡ്', f8d:'സംസാരിച്ച് ചോദിക്കുക, ഉത്തരം കേൾക്കുക.',
hg:'നമസ്തേ, ഞാൻ എങ്ങനെ സഹായിക്കാം?', hc1:'ഇന്ത്യയിൽ വാടകക്കാരുടെ അവകാശങ്ങൾ എന്തൊക്കെ?', hc2:'ഉപഭോക്തൃ പരാതി എങ്ങനെ നൽകാം?', hc3:'ഗാർഹിക പീഡന നിയമം വിശദീകരിക്കുക', hph:'നിങ്ങളുടെ നിയമ ചോദ്യം എഴുതുക...', hnote:'സൗജന്യം. നിങ്ങളുടെ സംഭാഷണങ്ങൾ ഉപകരണത്തിൽ തന്നെ.',
ct:'നിയമ സഹായി', cst:'സഹായത്തിന് തയ്യാർ', cnew:'പുതിയ സംഭാഷണം', wt:'അധിKaar ലേക്ക് സ്വാഗതം', wd:'നിങ്ങളുടെ നിയമ പ്രശ്നം സ്വന്തം വാക്കുകളിൽ പറയുക.',
c1:'ശമ്പളം കിട്ടിയില്ല', c2:'ഡെപ്പോസിറ്റ്', c3:'നിയമ നോട്ടീസ്', c4:'FIR രജിസ്റ്റർ ചെയ്തില്ല', c5:'ഗാർഹിക പീഡനം', c6:'ഓൺലൈൻ തട്ടിപ്പ്',
cph:'നിങ്ങളുടെ നിയമ പ്രശ്നം ഇവിടെ എഴുതുക...', chint:'അയയ്ക്കാൻ Enter · പുതിയ വരിക്ക് Shift+Enter · സംസാരിക്കാൻ മൈക്ക്', cdisc:'അധിKaar നിയമ വിവരങ്ങൾ നൽകുന്നു, ഉപദേശമല്ല. സങ്കീർണ്ണ വിഷയങ്ങൾക്ക് അഭിഭാഷകനെ കാണുക അല്ലെങ്കിൽ NALSA: 15100.',
bns_t:'IPC ↔ BNS വകുപ്പ് മാറ്റം', bns_d:'1 ജൂലൈ 2024ന് ക്രിമിനൽ നിയമം മാറി. ഏത് വകുപ്പും തിരയുക.', aid_t:'അടുത്തുള്ള നിയമ സഹായം', aid_d:'സൗജന്യ നിയമ സഹായം നിങ്ങളുടെ അവകാശം. DLSA, ഹെൽപ്പ്‌ലൈനുകൾ തിരയുക.', doc_t:'നിയമ രേഖ വിശദീകരിക്കുക', doc_d:'നോട്ടീസ്, FIR ഫോട്ടോ അപ്‌ലോഡ് ചെയ്യുക.',
cases_t:'എന്റെ കേസുകൾ', cases_d:'ഓരോ കേസിന്റെയും സംഭാഷണം ഈ ഉപകരണത്തിൽ സ്വകാര്യം.', draft_t:'നിയമ രേഖ തയ്യാറാക്കുക', draft_d:'കുറച്ച് ചോദ്യങ്ങൾ — തയ്യാറായ രേഖ.', court_t:'വെർച്വൽ കോടതി', court_d:'AI ജഡ്ജിക്ക് മുന്നിൽ വാദം — ദൗർബല്യങ്ങൾ മുൻകൂട്ടി അറിയുക.',
ncase:'പുതിയ കേസ്', shear:'വിചാരണ ആരംഭിക്കുക', nround:'അടുത്ത റൗണ്ട്', vmode:'വോയ്സ് മോഡ്' },

pa: { nav_home:'ਹੋਮ', nav_chat:'ਕਾਨੂੰਨੀ ਸਹਾਇਕ ਨਾਲ ਗੱਲ ਕਰੋ', nav_cases:'ਮੇਰੇ ਕੇਸ', nav_draft:'ਦਸਤਾਵੇਜ਼ ਬਣਾਓ', nav_court:'ਵਰਚੁਅਲ ਅਦਾਲਤ', nav_bns:'IPC ↔ BNS ਬਦਲੋ', nav_aid:'ਕਾਨੂੰਨੀ ਮਦਦ ਲੱਭੋ', nav_doc:'ਕਾਨੂੰਨੀ ਦਸਤਾਵੇਜ਼ ਸਮਝੋ',
badge:'100% ਨਿੱਜੀ · ਤੁਹਾਡੀ ਡਿਵਾਈਸ ਤੇ ਚੱਲਦਾ ਹੈ', hero_sub:'ਤਨਖਾਹ ਨਹੀਂ ਮਿਲੀ? ਡਿਪਾਜ਼ਿਟ ਫਸਿਆ ਹੈ? ਕਾਨੂੰਨੀ ਨੋਟਿਸ ਆਇਆ? 11 ਭਾਸ਼ਾਵਾਂ ਵਿੱਚ ਪੁੱਛੋ — ਮੁਫ਼ਤ, ਔਫਲਾਈਨ.', cta1:'ਆਪਣਾ ਸਵਾਲ ਪੁੱਛੋ', cta2:'ਕਿਵੇਂ ਕੰਮ ਕਰਦਾ ਹੈ ਵੇਖੋ',
tr1:'ਸਾਈਨਅੱਪ ਨਹੀਂ', tr2:'ਔਫਲਾਈਨ ਚੱਲਦਾ ਹੈ', tr3:'11 ਭਾਸ਼ਾਵਾਂ', tr4:'ਹਮੇਸ਼ਾ ਮੁਫ਼ਤ',
st1:'IPC ↔ BNS ਧਾਰਾਵਾਂ', st2:'ਭਾਰਤੀ ਭਾਸ਼ਾਵਾਂ', st3:'ਕਲਾਉਡ ਨੂੰ ਭੇਜਿਆ ਡੇਟਾ',
how:'ਇਹ ਕਿਵੇਂ ਕੰਮ ਕਰਦਾ ਹੈ', s1t:'ਆਪਣੀ ਸਮੱਸਿਆ ਦੱਸੋ', s1d:'11 ਭਾਸ਼ਾਵਾਂ ਵਿੱਚ ਲਿਖੋ ਜਾਂ ਬੋਲੋ.', s2t:'ਸਾਰ ਦੀ ਪੁਸ਼ਟੀ ਕਰੋ', s2d:'AI ਤੁਹਾਡੀ ਸਥਿਤੀ ਦੁਹਰਾਉਂਦਾ ਹੈ — ਤੁਸੀਂ ਜਾਂਚੋ.', s3t:'ਹੱਕ + ਅਗਲੇ ਕਦਮ', s3d:'BNS ਧਾਰਾਵਾਂ, ਸਮਾਂ-ਸੀਮਾਵਾਂ ਅਤੇ ਹੈਲਪਲਾਈਨਾਂ ਨਾਲ.',
feats:'ਅਧਿKaar ਜੋ ਕੁਝ ਕਰ ਸਕਦਾ ਹੈ', open:'ਖੋਲ੍ਹੋ',
f1t:'ਕਾਨੂੰਨੀ ਸਹਾਇਕ ਨਾਲ ਗੱਲ ਕਰੋ', f1d:'11 ਭਾਸ਼ਾਵਾਂ ਵਿੱਚ ਸਮੱਸਿਆ ਦੱਸੋ — ਹੱਕ ਜਾਣੋ.', f2t:'ਮੇਰੇ ਕੇਸ', f2d:'ਹਰ ਕੇਸ ਵਿਵਸਥਿਤ — ਡਿਵਾਈਸ ਤੇ ਨਿੱਜੀ.', f3t:'ਦਸਤਾਵੇਜ਼ ਬਣਾਓ', f3d:'ਪ੍ਰਿੰਟ-ਤਿਆਰ ਨੋਟਿਸ, ਸ਼ਿਕਾਇਤਾਂ ਅਤੇ RTI.', f4t:'ਵਰਚੁਅਲ ਅਦਾਲਤ', f4d:'AI ਜੱਜ ਸਾਹਮਣੇ ਦੋਵਾਂ ਪੱਖਾਂ ਦੀ ਬਹਿਸ.', f5t:'IPC ↔ BNS ਬਦਲੋ', f5d:'ਪੁਰਾਣੀਆਂ IPC ਧਾਰਾਵਾਂ ਨਵੀਂ BNS ਵਿੱਚ ਬਦਲੋ.', f6t:'ਕਾਨੂੰਨੀ ਮਦਦ ਲੱਭੋ', f6d:'ਤੁਹਾਡੇ ਜ਼ਿਲ੍ਹੇ ਵਿੱਚ ਮੁਫ਼ਤ ਕਾਨੂੰਨੀ ਮਦਦ.', f7t:'ਕਾਨੂੰਨੀ ਦਸਤਾਵੇਜ਼ ਸਮਝੋ', f7d:'ਨੋਟਿਸ ਅੱਪਲੋਡ ਕਰੋ — ਸੌਖੀ ਭਾਸ਼ਾ ਵਿੱਚ ਸਮਝੋ.', f8t:'ਆਵਾਜ਼ ਮੋਡ', f8d:'ਬੋਲ ਕੇ ਪੁੱਛੋ, ਜਵਾਬ ਸੁਣੋ.',
hg:'ਸਤ ਸ੍ਰੀ ਅਕਾਲ, ਮੈਂ ਕਿਵੇਂ ਮਦਦ ਕਰ ਸਕਦਾ ਹਾਂ?', hc1:'ਭਾਰਤ ਵਿੱਚ ਕਿਰਾਏਦਾਰ ਦੇ ਹੱਕ ਕੀ ਹਨ?', hc2:'ਖਪਤਕਾਰ ਸ਼ਿਕਾਇਤ ਕਿਵੇਂ ਦਰਜ ਕਰੀਏ?', hc3:'ਘਰੇਲੂ ਹਿੰਸਾ ਕਾਨੂੰਨ ਸਮਝਾਓ', hph:'ਆਪਣਾ ਕਾਨੂੰਨੀ ਸਵਾਲ ਲਿਖੋ...', hnote:'ਮੁਫ਼ਤ। ਤੁਹਾਡੀ ਗੱਲਬਾਤ ਤੁਹਾਡੀ ਡਿਵਾਈਸ ਤੇ ਹੀ ਰਹਿੰਦੀ ਹੈ.',
ct:'ਕਾਨੂੰਨੀ ਸਹਾਇਕ', cst:'ਮਦਦ ਲਈ ਤਿਆਰ', cnew:'ਨਵੀਂ ਗੱਲਬਾਤ', wt:'ਅਧਿKaar ਵਿੱਚ ਜੀ ਆਇਆਂ ਨੂੰ', wd:'ਆਪਣੀ ਕਾਨੂੰਨੀ ਸਮੱਸਿਆ ਆਪਣੇ ਸ਼ਬਦਾਂ ਵਿੱਚ ਦੱਸੋ.',
c1:'ਤਨਖਾਹ ਨਹੀਂ ਮਿਲੀ', c2:'ਡਿਪਾਜ਼ਿਟ', c3:'ਕਾਨੂੰਨੀ ਨੋਟਿਸ', c4:'FIR ਦਰਜ ਨਹੀਂ ਹੋਈ', c5:'ਘਰੇਲੂ ਹਿੰਸਾ', c6:'ਆਨਲਾਈਨ ਧੋਖਾਧੜੀ',
cph:'ਆਪਣੀ ਕਾਨੂੰਨੀ ਸਮੱਸਿਆ ਇੱਥੇ ਲਿਖੋ...', chint:'ਭੇਜਣ ਲਈ Enter · ਨਵੀਂ ਲਾਈਨ Shift+Enter · ਬੋਲਣ ਲਈ ਮਾਈਕ', cdisc:'ਅਧਿKaar ਕਾਨੂੰਨੀ ਜਾਣਕਾਰੀ ਦਿੰਦਾ ਹੈ, ਸਲਾਹ ਨਹੀਂ। ਗੁੰਝਲਦਾਰ ਮਾਮਲਿਆਂ ਲਈ ਵਕੀਲ ਨੂੰ ਮਿਲੋ ਜਾਂ NALSA: 15100.',
bns_t:'IPC ↔ BNS ਧਾਰਾ ਬਦਲੋ', bns_d:'1 ਜੁਲਾਈ 2024 ਨੂੰ ਫੌਜਦਾਰੀ ਕਾਨੂੰਨ ਬਦਲਿਆ। ਕੋਈ ਵੀ ਧਾਰਾ ਲੱਭੋ.', aid_t:'ਨੇੜੇ ਦੀ ਕਾਨੂੰਨੀ ਮਦਦ', aid_d:'ਮੁਫ਼ਤ ਕਾਨੂੰਨੀ ਮਦਦ ਤੁਹਾਡਾ ਹੱਕ ਹੈ। DLSA, ਹੈਲਪਲਾਈਨਾਂ ਲੱਭੋ.', doc_t:'ਕਾਨੂੰਨੀ ਦਸਤਾਵੇਜ਼ ਸਮਝੋ', doc_d:'ਨੋਟਿਸ, FIR ਦੀ ਫੋਟੋ ਅੱਪਲੋਡ ਕਰੋ.',
cases_t:'ਮੇਰੇ ਕੇਸ', cases_d:'ਹਰ ਕੇਸ ਦੀ ਗੱਲਬਾਤ ਇਸ ਡਿਵਾਈਸ ਤੇ ਨਿੱਜੀ.', draft_t:'ਕਾਨੂੰਨੀ ਦਸਤਾਵੇਜ਼ ਬਣਾਓ', draft_d:'ਕੁਝ ਸਵਾਲ — ਤਿਆਰ ਦਸਤਾਵੇਜ਼.', court_t:'ਵਰਚੁਅਲ ਅਦਾਲਤ', court_d:'AI ਜੱਜ ਸਾਹਮਣੇ ਬਹਿਸ — ਕਮਜ਼ੋਰੀਆਂ ਪਹਿਲਾਂ ਜਾਣੋ.',
ncase:'ਨਵਾਂ ਕੇਸ', shear:'ਸੁਣਵਾਈ ਸ਼ੁਰੂ ਕਰੋ', nround:'ਅਗਲਾ ਦੌਰ', vmode:'ਆਵਾਜ਼ ਮੋਡ' },
};

function t(key) {
  return (I18N[state.language] || {})[key] || I18N.en[key] || '';
}

function applyTranslations() {
  const setText = (sel, key) => {
    const el = document.querySelector(sel);
    if (el && t(key)) el.textContent = t(key);
  };
  const setAll = (sel, keys) => {
    document.querySelectorAll(sel).forEach((el, i) => {
      if (keys[i] && t(keys[i])) el.textContent = t(keys[i]);
    });
  };
  const setWithIcon = (sel, icon, key) => {
    const el = document.querySelector(sel);
    if (el && t(key)) el.innerHTML = `<i data-lucide="${icon}" class="inline-icon"></i> ${t(key)}`;
  };

  // Sidebar nav
  [['home','nav_home'],['chat','nav_chat'],['cases','nav_cases'],['draft','nav_draft'],['courtroom','nav_court'],['bns','nav_bns'],['legal-aid','nav_aid'],['document','nav_doc']]
    .forEach(([v, k]) => setText(`.nav-item[data-view="${v}"] .nav-label`, k));
  setWithIcon('.kiosk-launch-btn', 'accessibility', 'vmode');

  // Hero
  setWithIcon('.hero-badge', 'shield-check', 'badge');
  setText('.hero-subtitle', 'hero_sub');
  setWithIcon('.hero-cta .btn-primary', 'message-circle', 'cta1');
  setText('.hero-cta .btn-secondary', 'cta2');
  const trustIcons = ['user-x', 'wifi-off', 'languages', 'badge-indian-rupee'];
  document.querySelectorAll('.trust-strip span').forEach((el, i) => {
    const k = `tr${i + 1}`;
    if (t(k)) el.innerHTML = `<i data-lucide="${trustIcons[i]}"></i> ${t(k)}`;
  });
  setAll('.stat-card .stat-label', ['st1', 'st2', 'st3']);

  // How it works
  setText('.how-it-works .section-title', 'how');
  setAll('.how-it-works .step-card h3', ['s1t', 's2t', 's3t']);
  setAll('.how-it-works .step-card p', ['s1d', 's2d', 's3d']);

  // Feature cards
  setText('.features-title', 'feats');
  setAll('.features-grid .feature-card h3', ['f1t','f2t','f3t','f4t','f5t','f6t','f7t','f8t']);
  setAll('.features-grid .feature-card p', ['f1d','f2d','f3d','f4d','f5d','f6d','f7d','f8d']);
  document.querySelectorAll('.features-grid .card-go').forEach(el => {
    el.innerHTML = `${t('open')} <i data-lucide="arrow-right"></i>`;
  });

  // Home chat panel
  setText('.home-chat-greeting h2', 'hg');
  setAll('.home-chat-chips button', ['hc1', 'hc2', 'hc3']);
  const hInput = $('home-chat-input');
  if (hInput && t('hph')) hInput.placeholder = t('hph');
  setText('.home-chat-note', 'hnote');

  // Global quick-ask bar
  const gInput = $('global-ask-input');
  if (gInput && t('cph')) gInput.placeholder = t('cph');

  // Chat view
  setWithIcon('.chat-header-left h2', 'message-circle', 'ct');
  setText('.chat-status span:last-child', 'cst');
  setWithIcon('.chat-actions .btn', 'plus', 'cnew');
  setText('#chat-welcome h3', 'wt');
  setText('#chat-welcome > p', 'wd');
  setAll('#chat-welcome .suggestion-chip', ['c1', 'c2', 'c3', 'c4', 'c5', 'c6']);
  const cInput = $('chat-input');
  if (cInput && t('cph')) cInput.placeholder = t('cph');
  setText('.chat-input-hint', 'chint');
  setText('.chat-disclaimer', 'cdisc');

  // View headers
  setText('#view-bns .view-header h2', 'bns_t');
  setText('#view-bns .view-header p', 'bns_d');
  setText('#view-legal-aid .view-header h2', 'aid_t');
  setText('#view-legal-aid .view-header p', 'aid_d');
  setText('#view-document .view-header h2', 'doc_t');
  setText('#view-document .view-header p', 'doc_d');
  setWithIcon('#view-cases .view-header h2', 'folder-open', 'cases_t');
  setText('#view-cases .view-header p', 'cases_d');
  setWithIcon('.cases-toolbar .btn', 'plus', 'ncase');
  setWithIcon('#view-draft .view-header h2', 'file-pen-line', 'draft_t');
  setText('#view-draft .view-header p', 'draft_d');
  setWithIcon('#view-courtroom .view-header h2', 'gavel', 'court_t');
  setText('#view-courtroom .view-header p', 'court_d');
  setWithIcon('#courtroom-setup .btn-primary', 'gavel', 'shear');
  const nextBtn = $('courtroom-next-btn');
  if (nextBtn && !nextBtn.disabled && t('nround')) nextBtn.textContent = t('nround');

  refreshIcons();
}
