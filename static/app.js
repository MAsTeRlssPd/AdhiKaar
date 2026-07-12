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
  lastSituation: '',
  lastAdvice: '',
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

  try {
    const data = await apiCall('/api/chat', {
      method: 'POST',
      body: JSON.stringify({
        message: message,
        language: state.language,
        session_id: state.sessionId,
      }),
    });

    hideTyping();
    state.lastAdvice = data.response;

    // Add assistant message with action buttons
    addMessage('assistant', data.response, {
      powerImbalance: data.power_imbalance,
      showActions: true,
    });

  } catch (error) {
    hideTyping();
    addMessage('assistant', '⚠️ Sorry, I could not connect to the AI model. Please make sure:\n\n1. **Ollama is running** (`ollama serve`)\n2. **Gemma 4 is installed** (`ollama pull gemma4`)\n3. **The server is running** (`python app.py`)\n\nThen try again.');
  }
}

function addMessage(role, content, options = {}) {
  const container = $('chat-messages');

  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${role}`;

  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  avatar.textContent = role === 'user' ? '👤' : '⚖️';

  const contentDiv = document.createElement('div');
  contentDiv.className = 'message-content markdown-body';

  if (role === 'assistant') {
    contentDiv.innerHTML = renderMarkdown(content);

    // Add action buttons after assistant responses
    if (options.showActions) {
      const actionsDiv = document.createElement('div');
      actionsDiv.className = 'message-actions';

      const actions = [
        { label: '👿 Devil\'s Advocate', cls: 'devil', fn: () => runDevilAdvocate() },
        { label: '⏰ What If I Do Nothing?', cls: '', fn: () => runConsequenceSimulator() },
        { label: '🏘️ Explain to Elder', cls: '', fn: () => runPanchayatBridge() },
        { label: '🪪 Rights Card', cls: '', fn: () => generateRightsCard() },
        { label: '📋 Checklist', cls: '', fn: () => generateChecklist() },
      ];

      actions.forEach(action => {
        const btn = document.createElement('button');
        btn.className = `message-action-btn ${action.cls}`;
        btn.textContent = action.label;
        btn.onclick = action.fn;
        actionsDiv.appendChild(btn);
      });

      contentDiv.appendChild(actionsDiv);
    }
  } else {
    contentDiv.textContent = content;
  }

  messageDiv.appendChild(avatar);
  messageDiv.appendChild(contentDiv);
  container.appendChild(messageDiv);

  // Scroll to bottom
  container.scrollTop = container.scrollHeight;

  // Store in history
  state.chatHistory.push({ role, content });
}

function showTyping() {
  const container = $('chat-messages');
  const typingDiv = document.createElement('div');
  typingDiv.id = 'typing-indicator';
  typingDiv.className = 'typing-indicator';
  typingDiv.innerHTML = `
    <div class="message-avatar" style="background: var(--primary-subtle);">⚖️</div>
    <div class="typing-dots"><span></span><span></span><span></span></div>
    <span style="color: var(--text-tertiary); font-size: var(--font-size-sm);">Thinking...</span>
  `;
  container.appendChild(typingDiv);
  container.scrollTop = container.scrollHeight;
}

function hideTyping() {
  const typing = $('typing-indicator');
  if (typing) typing.remove();
}

function clearChat() {
  state.sessionId = generateId();
  localStorage.setItem('adhikaar_session', state.sessionId);
  state.chatHistory = [];
  state.lastSituation = '';
  state.lastAdvice = '';

  const container = $('chat-messages');
  container.innerHTML = `
    <div class="chat-welcome" id="chat-welcome">
      <div class="welcome-icon">⚖️</div>
      <h3>Welcome to अधिKaar</h3>
      <p>Tell me about your legal problem in your own words. I'll help you understand your rights and options.</p>
      <div class="suggestions">
        <button class="suggestion-chip" onclick="sendSuggestion('My employer has not paid my salary for 3 months')">💼 Unpaid salary</button>
        <button class="suggestion-chip" onclick="sendSuggestion('My landlord is not returning my security deposit')">🏠 Security deposit</button>
        <button class="suggestion-chip" onclick="sendSuggestion('I received a legal notice and I don\\'t understand it')">📄 Got a legal notice</button>
        <button class="suggestion-chip" onclick="sendSuggestion('Police refused to file my FIR')">👮 FIR not filed</button>
        <button class="suggestion-chip" onclick="sendSuggestion('I am facing domestic violence from my husband and in-laws')">🏠 Domestic violence</button>
        <button class="suggestion-chip" onclick="sendSuggestion('Someone cheated me online and took my money')">💻 Online fraud</button>
      </div>
    </div>
  `;
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
// Voice Input (Web Speech API)
// ══════════════════════════════════════════════════════════════

function initVoice() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    console.log('Speech Recognition not supported');
    return;
  }

  state.recognition = new SpeechRecognition();
  state.recognition.interimResults = true;
  state.recognition.continuous = false;

  state.recognition.onresult = (event) => {
    const transcript = Array.from(event.results)
      .map(r => r[0].transcript)
      .join('');

    $('chat-input').value = transcript;
    autoResizeTextarea($('chat-input'));
  };

  state.recognition.onend = () => {
    state.isRecording = false;
    $('voice-btn').classList.remove('recording');
    $('voice-btn').textContent = '🎤';

    // Auto-send if we got text
    const input = $('chat-input');
    if (input.value.trim()) {
      sendMessage();
    }
  };

  state.recognition.onerror = (event) => {
    console.error('Speech recognition error:', event.error);
    state.isRecording = false;
    $('voice-btn').classList.remove('recording');
    $('voice-btn').textContent = '🎤';
  };
}

function toggleVoice() {
  if (!state.recognition) {
    initVoice();
    if (!state.recognition) {
      alert('Voice input is not supported in your browser. Please use Chrome or Edge.');
      return;
    }
  }

  if (state.isRecording) {
    state.recognition.stop();
    state.isRecording = false;
    $('voice-btn').classList.remove('recording');
    $('voice-btn').textContent = '🎤';
  } else {
    // Set language for recognition
    const lang = LANGUAGES.find(l => l.code === state.language);
    state.recognition.lang = lang ? lang.speechCode : 'en-IN';

    state.recognition.start();
    state.isRecording = true;
    $('voice-btn').classList.add('recording');
    $('voice-btn').textContent = '⏹️';
  }
}

// ══════════════════════════════════════════════════════════════
// BNS Converter
// ══════════════════════════════════════════════════════════════

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
    bnsResults.innerHTML = '<div class="empty-state"><div class="empty-icon">🔍</div><p>Type a section number or offence name to search</p></div>';
  }
});
