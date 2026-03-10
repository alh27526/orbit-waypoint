// app.js — Frontend logic for Orbit Prototype

// State
let currentAccount = null;
let currentPersona = 'Andrew';
let accountsList = [];

// DOM Elements
const el = {
    personaAndrew: document.getElementById('btn-persona-andrew'),
    personaAshley: document.getElementById('btn-persona-ashley'),
    userInitials: document.getElementById('user-initials'),
    
    // Left Pane
    metricRevenue: document.getElementById('metric-revenue'),
    metricAccounts: document.getElementById('metric-accounts'),
    metricRisk: document.getElementById('metric-risk'),
    pipelineStages: document.getElementById('pipeline-stages'),
    
    // Middle Pane
    viewList: document.getElementById('view-account-list'),
    viewDetail: document.getElementById('view-account-detail'),
    listContainer: document.getElementById('account-list-container'),
    
    // Detail View
    detailName: document.getElementById('detail-name'),
    detailIndustry: document.getElementById('detail-industry'),
    detailTerritory: document.getElementById('detail-territory'),
    detailTier: document.getElementById('detail-tier'),
    detailRevenue: document.getElementById('detail-revenue'),
    detailContacts: document.getElementById('detail-contacts'),
    detailQuotes: document.getElementById('detail-quotes'),
    detailEdds: document.getElementById('detail-edds'),
    
    // Right Pane (Wizard)
    chatHistory: document.getElementById('chat-history'),
    chatInput: document.getElementById('chat-input'),
    typingIndicator: document.getElementById('typing-indicator'),
    wizardBadge: document.getElementById('wizard-context-badge'),
    wizardText: document.getElementById('wizard-context-text'),
};

// Utils
const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(amount || 0);
};

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    fetchTerritoryHealth();
    fetchAccounts();
});

// --- Actions ---

function switchPersona(persona) {
    currentPersona = persona;
    if (persona === 'Andrew') {
        el.personaAndrew.className = "px-3 py-1 text-sm font-medium rounded-full bg-brand-500 text-white transition-colors";
        el.personaAshley.className = "px-3 py-1 text-sm font-medium rounded-full text-slate-400 hover:text-white transition-colors";
        el.userInitials.textContent = "AH";
    } else {
        el.personaAshley.className = "px-3 py-1 text-sm font-medium rounded-full bg-purple-600 text-white transition-colors";
        el.personaAndrew.className = "px-3 py-1 text-sm font-medium rounded-full text-slate-400 hover:text-white transition-colors";
        el.userInitials.textContent = "AM";
    }
}

function showAccountList() {
    el.viewDetail.style.transform = 'translateX(100%)';
    el.viewList.style.transform = 'translateX(0)';
    currentAccount = null;
    el.wizardBadge.classList.add('hidden');
}

async function showAccountDetail(accountId) {
    currentAccount = accountId;
    
    try {
        const [accRes, contactsRes, quotesRes, eddsRes] = await Promise.all([
            fetch(`/api/accounts/${accountId}`),
            fetch(`/api/accounts/${accountId}/contacts`),
            fetch(`/api/accounts/${accountId}/quotes`),
            fetch(`/api/accounts/${accountId}/edd`)
        ]);
        
        const acc = await accRes.json();
        const contacts = await contactsRes.json();
        const quotes = await quotesRes.json();
        const edds = await eddsRes.json();
        
        // Populate Header
        el.detailName.textContent = acc.name;
        el.detailIndustry.innerHTML = `<i class="ph ph-briefcase"></i> ${acc.industry || 'Unknown'}`;
        el.detailTerritory.innerHTML = `<i class="ph ph-map-pin"></i> ${acc.territory || 'Unassigned'}`;
        el.detailTier.textContent = acc.regulatory_tier || 'N/A';
        el.detailRevenue.textContent = formatCurrency(acc.ytd_revenue);
        
        // Populate Contacts
        el.detailContacts.innerHTML = '';
        if (contacts.length === 0) {
            el.detailContacts.innerHTML = '<div class="text-sm text-slate-500 italic">No contacts found.</div>';
        } else {
            contacts.forEach(c => {
                el.detailContacts.innerHTML += `
                    <div class="bg-slate-800/50 p-3 rounded-lg border border-slate-700 hover:border-slate-500 transition-colors">
                        <div class="font-medium text-white text-sm">${c.name}</div>
                        <div class="text-xs text-brand-accent mb-2">${c.title || 'Contact'}</div>
                        ${c.email ? `<div class="text-xs text-slate-400 flex items-center gap-1"><i class="ph ph-envelope-simple"></i> ${c.email}</div>` : ''}
                        ${c.phone ? `<div class="text-xs text-slate-400 flex items-center gap-1 mt-1"><i class="ph ph-phone"></i> ${c.phone}</div>` : ''}
                    </div>
                `;
            });
        }
        
        // Populate Quotes
        el.detailQuotes.innerHTML = '';
        if (quotes.length === 0) {
            el.detailQuotes.innerHTML = '<div class="text-sm text-slate-500 italic">No quotes found.</div>';
        } else {
            quotes.forEach(q => {
                let badgeClass = q.status === 'Accepted' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400';
                el.detailQuotes.innerHTML += `
                    <div class="bg-slate-800 border-l-2 border-slate-600 p-3 rounded flex justify-between items-center text-sm">
                        <div>
                            <div class="font-medium font-mono text-slate-300">${q.quote_number}</div>
                            <div class="text-slate-500 text-xs mt-0.5">${q.sent_date || 'Draft'}</div>
                        </div>
                        <div class="text-right">
                            <div class="font-semibold text-white">${formatCurrency(q.amount)}</div>
                            <span class="text-[10px] px-1.5 py-0.5 rounded ${badgeClass}">${q.status}</span>
                        </div>
                    </div>
                `;
            });
        }
        
        // Popoulate EDDs
        el.detailEdds.innerHTML = '';
        if (edds.length === 0) {
            el.detailEdds.innerHTML = '<div class="text-sm text-slate-500 italic">No EDD submissions found.</div>';
        } else {
            edds.forEach(e => {
                let badgeClass = e.status === 'Accepted' ? 'text-emerald-400' : 'text-amber-400';
                let iconClass = e.status === 'Accepted' ? 'ph-check-circle' : 'ph-warning-circle';
                el.detailEdds.innerHTML += `
                    <div class="bg-slate-800 p-3 rounded border border-slate-700 text-sm">
                        <div class="flex justify-between items-start mb-1">
                            <div class="font-medium text-slate-200 truncate pr-2">${e.project_name}</div>
                            <i class="ph-fill ${iconClass} ${badgeClass}"></i>
                        </div>
                        <div class="flex justify-between text-xs text-slate-500">
                            <span>${e.format_type}</span>
                            <span>${e.submission_date}</span>
                        </div>
                    </div>
                `;
            });
        }
        
        // Update Wizard badge
        el.wizardText.textContent = acc.name;
        el.wizardBadge.classList.remove('hidden');
        
        // Transition panes
        el.viewList.style.transform = 'translateX(-100%)';
        el.viewDetail.style.transform = 'translateX(0)';
        
    } catch (err) {
        console.error("Error loading account details:", err);
    }
}

// --- API Calls ---

async function fetchTerritoryHealth() {
    try {
        const res = await fetch('/api/territory/health');
        const data = await res.json();
        
        el.metricRevenue.textContent = formatCurrency(data.ytd_revenue);
        el.metricAccounts.textContent = data.total_accounts;
        el.metricRisk.textContent = data.at_risk_accounts;
        
        // Also fetch pipeline summary
        const pipeRes = await fetch('/api/pipeline/summary');
        const pipeData = await pipeRes.json();
        
        el.pipelineStages.innerHTML = '';
        
        // Sort by value desc
        pipeData.sort((a, b) => b.value - a.value);
        
        let totalValue = pipeData.reduce((sum, item) => sum + item.value, 0);
        
        pipeData.forEach(item => {
            if (!item.pipeline_stage) return;
            const percentage = totalValue > 0 ? (item.value / totalValue) * 100 : 0;
            
            el.pipelineStages.innerHTML += `
                <div>
                    <div class="flex justify-between text-xs mb-1">
                        <span class="text-slate-300">${item.pipeline_stage} <span class="text-slate-500">(${item.count})</span></span>
                        <span class="font-medium text-brand-accent">${formatCurrency(item.value)}</span>
                    </div>
                    <div class="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                        <div class="h-full bg-brand-500 rounded-full" style="width: ${percentage}%"></div>
                    </div>
                </div>
            `;
        });
        
    } catch (err) {
        console.error("Error loading territory health:", err);
    }
}

async function fetchAccounts() {
    try {
        const res = await fetch('/api/accounts');
        accountsList = await res.json();
        renderAccountsList(accountsList);
    } catch (err) {
        console.error("Error loading accounts list:", err);
    }
}

function renderAccountsList(accounts) {
    el.listContainer.innerHTML = '';
    
    // Default to show top 50 to avoid massive DOM
    const displayList = accounts.slice(0, 50);
    
    displayList.forEach(acc => {
        let riskIndicator = acc.health_score < 60 ? '<div class="h-2 w-2 rounded-full bg-amber-500 mt-1.5 shrink-0"></div>' : '';
        
        el.listContainer.innerHTML += `
            <div class="bg-slate-800/60 hover:bg-slate-700/80 p-3 rounded-lg border border-slate-700/50 cursor-pointer transition-colors hover-lift flex gap-3" onclick="showAccountDetail(${acc.id})">
                ${riskIndicator}
                <div class="flex-1 min-w-0">
                    <div class="flex justify-between items-start mb-0.5">
                        <h3 class="font-semibold text-white truncate pr-2 text-sm">${acc.name}</h3>
                        <div class="text-brand-accent font-medium text-sm shrink-0">${formatCurrency(acc.ytd_revenue)}</div>
                    </div>
                    <div class="flex items-center justify-between text-xs text-slate-400">
                        <span class="truncate pr-2">${acc.industry || 'Unknown Industry'}</span>
                        <span class="shrink-0 px-1.5 py-0.5 rounded bg-slate-800 border border-slate-600">${acc.territory || 'Unassigned'}</span>
                    </div>
                </div>
            </div>
        `;
    });
}

// --- Wizard Chat ---

function submitChat() {
    const query = el.chatInput.value.trim();
    if (!query) return;
    
    // Append User Message
    appendMessage('user', query);
    el.chatInput.value = '';
    
    // Show typing
    el.typingIndicator.classList.remove('hidden');
    scrollToBottom();
    
    // Prepare API call
    const payload = {
        query: query,
        user_persona: currentPersona,
        account_id: currentAccount
    };
    
    // We use fetch to stream the SSE manually
    fetch('/api/wizard/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    }).then(response => {
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        
        el.typingIndicator.classList.add('hidden');
        
        // Create an empty assistant message DOM element
        const msgId = `msg-${Date.now()}`;
        appendEmptyAssistantMessage(msgId);
        const msgContainer = document.getElementById(msgId);
        
        let fullText = "";
        
        function readStream() {
            reader.read().then(({ done, value }) => {
                if (done) {
                    // Final render with marked to ensure lists/links resolve properly
                    msgContainer.innerHTML = marked.parse(fullText);
                    return;
                }
                
                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');
                
                for (let line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.substring(6));
                            if (data.done) break;
                            if (data.text) {
                                fullText += data.text;
                                // Fast DOM update during streaming
                                msgContainer.innerHTML = marked.parse(fullText);
                                scrollToBottom();
                            }
                        } catch (e) {
                            // Ignored — partial chunk parse error
                        }
                    }
                }
                
                readStream();
            });
        }
        
        readStream();
        
    }).catch(err => {
        console.error("Chat error:", err);
        el.typingIndicator.classList.add('hidden');
        appendMessage('assistant', `*Error communicating with Wizard. Is the backend running?*`);
    });
}

function appendMessage(role, content) {
    const isUser = role === 'user';
    const icon = isUser ? `<div class="h-8 w-8 rounded-full bg-slate-700 flex items-center justify-center shrink-0 border border-slate-600 font-bold text-xs">${el.userInitials.textContent}</div>` 
                        : `<div class="h-8 w-8 rounded-full bg-slate-800 flex items-center justify-center shrink-0 border border-slate-700"><i class="ph-fill ph-magic-wand text-brand-accent text-sm"></i></div>`;
                        
    const html = `
        <div class="flex gap-3 max-w-[90%] ${isUser ? 'ml-auto flex-row-reverse' : ''}">
            ${icon}
            <div class="${isUser ? 'bg-brand-600 text-white rounded-tr-none' : 'bg-slate-800 border border-slate-700 text-white rounded-tl-none'} p-3 rounded-2xl text-sm leading-relaxed prose prose-invert max-w-none">
                ${isUser ? escapeHtml(content) : marked.parse(content)}
            </div>
        </div>
    `;
    
    el.chatHistory.insertAdjacentHTML('beforeend', html);
    scrollToBottom();
}

function appendEmptyAssistantMessage(id) {
    const html = `
        <div class="flex gap-3 max-w-[90%]">
            <div class="h-8 w-8 rounded-full bg-slate-800 flex items-center justify-center shrink-0 border border-slate-700">
                <i class="ph-fill ph-magic-wand text-brand-accent text-sm"></i>
            </div>
            <div id="${id}" class="bg-slate-800 border border-slate-700 text-white p-3 rounded-2xl rounded-tl-none text-sm leading-relaxed prose prose-invert max-w-none">
                ... 
            </div>
        </div>
    `;
    el.chatHistory.insertAdjacentHTML('beforeend', html);
    scrollToBottom();
}

function scrollToBottom() {
    el.chatHistory.scrollTop = el.chatHistory.scrollHeight;
}

function escapeHtml(unsafe) {
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}
