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
    pipelineStageFlow: document.getElementById('pipeline-stage-flow'),
    
    // Middle Pane
    viewList: document.getElementById('view-account-list'),
    viewDetail: document.getElementById('view-account-detail'),
    listContainer: document.getElementById('account-list-container'),
    searchInput: document.querySelector('#view-account-list input[type="text"]'),
    
    // Detail View
    detailName: document.getElementById('detail-name'),
    detailIndustry: document.getElementById('detail-industry'),
    detailTerritory: document.getElementById('detail-territory'),
    detailTier: document.getElementById('detail-tier'),
    detailStageText: document.getElementById('detail-stage-text'),
    detailRevenue: document.getElementById('detail-revenue'),
    detailHealthBar: document.getElementById('detail-health-bar'),
    detailHealthScore: document.getElementById('detail-health-score'),
    detailContacts: document.getElementById('detail-contacts'),
    detailQuotes: document.getElementById('detail-quotes'),
    detailEdds: document.getElementById('detail-edds'),
    detailActivities: document.getElementById('detail-activities'),
    
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

function daysSince(dateStr) {
    if (!dateStr) return 999;
    const d = new Date(dateStr);
    const now = new Date();
    return Math.floor((now - d) / (1000 * 60 * 60 * 24));
}

function contactDotColor(lastContactDate) {
    const days = daysSince(lastContactDate);
    if (days <= 30) return { color: 'bg-emerald-500', border: 'border-emerald-400', label: `${days}d ago` };
    if (days <= 60) return { color: 'bg-amber-500', border: 'border-amber-400', label: `${days}d ago` };
    return { color: 'bg-red-500', border: 'border-red-400', label: days < 999 ? `${days}d ago` : 'Never' };
}

function healthColor(score) {
    if (score >= 80) return { bg: 'bg-emerald-500', text: 'text-emerald-400' };
    if (score >= 60) return { bg: 'bg-amber-500', text: 'text-amber-400' };
    return { bg: 'bg-red-500', text: 'text-red-400' };
}

function activityIcon(type) {
    const icons = {
        'call': { icon: 'ph-phone', color: 'border-sky-500', bg: 'text-sky-400' },
        'email': { icon: 'ph-envelope', color: 'border-violet-500', bg: 'text-violet-400' },
        'site_visit': { icon: 'ph-map-pin', color: 'border-emerald-500', bg: 'text-emerald-400' },
        'quote': { icon: 'ph-file-text', color: 'border-amber-500', bg: 'text-amber-400' },
        'note': { icon: 'ph-note-pencil', color: 'border-slate-500', bg: 'text-slate-400' },
        'meeting': { icon: 'ph-video-camera', color: 'border-teal-500', bg: 'text-teal-400' },
    };
    return icons[type] || { icon: 'ph-circle', color: 'border-slate-500', bg: 'text-slate-400' };
}

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    fetchTerritoryHealth();
    fetchAccounts();

    // Wire search input
    if (el.searchInput) {
        el.searchInput.addEventListener('input', (e) => {
            const q = e.target.value.toLowerCase();
            if (!q) {
                renderAccountsList(accountsList);
                return;
            }
            const filtered = accountsList.filter(a =>
                (a.name || '').toLowerCase().includes(q) ||
                (a.industry || '').toLowerCase().includes(q) ||
                (a.territory || '').toLowerCase().includes(q)
            );
            renderAccountsList(filtered);
        });
    }
});

// --- Actions ---

function switchPersona(persona) {
    currentPersona = persona;
    if (persona === 'Andrew') {
        el.personaAndrew.className = "px-3 py-1 text-sm font-medium rounded-full bg-brand-500 text-white transition-colors";
        el.personaAshley.className = "px-3 py-1 text-sm font-medium rounded-full text-slate-400 hover:text-white transition-colors";
        el.userInitials.textContent = "AH";
    } else {
        el.personaAshley.className = "px-3 py-1 text-sm font-medium rounded-full bg-brand-400 text-white transition-colors";
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
        const responses = await Promise.all([
            fetch(`/api/accounts/${accountId}`),
            fetch(`/api/accounts/${accountId}/contacts`),
            fetch(`/api/accounts/${accountId}/quotes`),
            fetch(`/api/accounts/${accountId}/edd`),
            fetch(`/api/accounts/${accountId}/activities`),
            fetch(`/api/accounts/${accountId}/tasks`)
        ]);
        
        if (responses.some(r => r.status === 429)) {
            console.error("Rate limit exceeded while loading account details.");
            alert("Rate limit exceeded. Please wait a moment and try again.");
            return;
        }
        
        const [accRes, contactsRes, quotesRes, eddsRes, activitiesRes, tasksRes] = responses;
        
        const acc = await accRes.json();
        const contacts = await contactsRes.json();
        const quotes = await quotesRes.json();
        const edds = await eddsRes.json();
        const activities = await activitiesRes.json();
        const tasks = await tasksRes.json();
        
        // Populate Header
        el.detailName.textContent = acc.name;
        el.detailIndustry.innerHTML = `<i class="ph ph-briefcase"></i> ${acc.industry || 'Unknown'}`;
        el.detailTerritory.innerHTML = `<i class="ph ph-map-pin"></i> ${acc.territory || 'Unassigned'}`;
        el.detailTier.textContent = acc.regulatory_tier || 'Standard';
        el.detailStageText.textContent = acc.pipeline_stage || 'Unknown';
        el.detailRevenue.textContent = formatCurrency(acc.ytd_revenue);
    
        // TAT and Incumbent Logic
        const tatBadge = document.getElementById('detail-tat');
        const tatText = document.getElementById('detail-tat-text');
        if (acc.avg_tat_days > 0) {
            tatText.textContent = `${acc.avg_tat_days}d TAT`;
            tatBadge.classList.remove('hidden');
            if (acc.avg_tat_days >= 7) {
                tatBadge.classList.replace('text-slate-300', 'text-amber-400');
                tatBadge.classList.replace('bg-slate-800', 'bg-amber-900/30');
                tatBadge.classList.replace('border-slate-700', 'border-amber-500/30');
            } else {
                tatBadge.className = 'px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 text-xs border border-slate-700 flex items-center gap-1';
            }
        } else {
            tatBadge.classList.add('hidden');
        }
        
        const incBadge = document.getElementById('detail-incumbent');
        const incText = document.getElementById('detail-incumbent-text');
        if (acc.incumbent_lab) {
            incText.textContent = `Incumbent: ${acc.incumbent_lab}`;
            incBadge.classList.remove('hidden');
        } else {
            incBadge.classList.add('hidden');
        }

        // Health Score Bar
        const hs = acc.health_score || 0;
        const hc = healthColor(hs);
        el.detailHealthBar.className = `h-full rounded-full transition-all duration-500 ${hc.bg}`;
        el.detailHealthBar.style.width = `${hs}%`;
        el.detailHealthScore.textContent = hs;
        el.detailHealthScore.className = `text-sm font-semibold ${hc.text}`;
        
        // Source & Channel badges
        const sourceEl = document.getElementById('detailSource');
        if (sourceEl) {
            if (acc.source) {
                sourceEl.innerHTML = `<span class="text-xs px-2 py-0.5 rounded-full bg-slate-700 text-slate-300"><i class="ph ph-broadcast"></i> ${acc.source}</span>`;
                if (acc.channel) sourceEl.innerHTML += ` <span class="text-xs px-2 py-0.5 rounded-full bg-slate-700/60 text-slate-400">${acc.channel}</span>`;
            } else {
                sourceEl.innerHTML = '';
            }
        }
        
        // Account Tags
        const tagsEl = document.getElementById('detailTags');
        if (tagsEl) {
            tagsEl.innerHTML = (acc.tags || []).map(t =>
                `<span class="text-[10px] px-2 py-0.5 rounded-full bg-brand-500/20 text-brand-accent border border-brand-500/30">${t}</span>`
            ).join('');
        }
        
        // Populate Contacts (with color dots)
        el.detailContacts.innerHTML = '';
        if (contacts.length === 0) {
            el.detailContacts.innerHTML = '<div class="text-sm text-slate-500 italic">No contacts found.</div>';
        } else {
            contacts.forEach(c => {
                const dot = contactDotColor(c.last_contact_date);
                el.detailContacts.innerHTML += `
                    <div class="bg-slate-800/50 p-3 rounded-lg border border-slate-700 hover:border-slate-500 transition-colors">
                        <div class="flex items-center gap-2 mb-1">
                            <div class="h-2.5 w-2.5 rounded-full ${dot.color} shrink-0" title="Last contact: ${dot.label}"></div>
                            <div class="font-medium text-white text-sm">${c.name}</div>
                        </div>
                        <div class="text-xs text-brand-accent mb-2 pl-[18px]">${c.title || 'Contact'}</div>
                        ${c.email ? `<div class="text-xs text-slate-400 flex items-center gap-1 pl-[18px]"><i class="ph ph-envelope-simple"></i> ${c.email}</div>` : ''}
                        ${c.phone ? `<div class="text-xs text-slate-400 flex items-center gap-1 mt-1 pl-[18px]"><i class="ph ph-phone"></i> ${c.phone}</div>` : ''}
                        <div class="text-[10px] text-slate-500 mt-1 pl-[18px]">${dot.label}</div>
                        ${(c.tags || []).length ? `<div class="flex flex-wrap gap-1 mt-1.5 pl-[18px]">${c.tags.map(t => `<span class="text-[9px] px-1.5 py-0.5 rounded-full bg-slate-700 text-slate-400">${t}</span>`).join('')}</div>` : ''}
                    </div>
                `;
            });
        }
        
        // Populate Activity Timeline
        el.detailActivities.innerHTML = '';
        if (activities.length === 0) {
            el.detailActivities.innerHTML = '<div class="text-sm text-slate-500 italic">No activities found.</div>';
        } else {
            activities.forEach((a, idx) => {
                const ai = activityIcon(a.activity_type);
                const isLast = idx === activities.length - 1;
                el.detailActivities.innerHTML += `
                    <div class="relative pl-10 pb-4 ${!isLast ? '' : ''}">
                        ${!isLast ? '<div class="absolute left-[15px] top-[28px] bottom-0 w-0.5 bg-slate-700/50"></div>' : ''}
                        <div class="absolute left-[10px] top-[6px] w-[12px] h-[12px] rounded-full border-2 ${ai.color} bg-slate-900"></div>
                        <div class="bg-slate-800/40 border border-slate-700/50 rounded-lg p-3 hover:bg-slate-800/70 transition-colors">
                            <div class="flex items-center justify-between mb-1">
                                <div class="flex items-center gap-2">
                                    <i class="ph ${ai.icon} ${ai.bg} text-sm"></i>
                                    <span class="text-xs font-medium text-slate-300 capitalize">${(a.activity_type || 'note').replace('_', ' ')}</span>
                                </div>
                                <span class="text-[10px] text-slate-500">${a.activity_date || 'Unknown date'}</span>
                            </div>
                            <p class="text-sm text-slate-300 leading-relaxed">${a.summary || 'No summary'}</p>
                            ${a.outcome ? `<div class="text-xs text-slate-500 mt-1 italic">→ ${a.outcome}</div>` : ''}
                        </div>
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
                        <div class="text-right flex items-center gap-2">
                            <div>
                                <div class="font-semibold text-white">${formatCurrency(q.amount)}</div>
                                <span class="text-[10px] px-1.5 py-0.5 rounded ${badgeClass}">${q.status}</span>
                            </div>
                            <a href="/api/quotes/${q.id}/pdf" target="_blank" class="text-slate-400 hover:text-brand-accent transition-colors" title="Export PDF">
                                <i class="ph ph-file-pdf text-lg"></i>
                            </a>
                        </div>
                    </div>
                `;
            });
        }
        
        // Populate EDDs
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
        
        // Populate Tasks
        const tasksContainer = document.getElementById('detailTasks');
        if (tasksContainer) {
            tasksContainer.innerHTML = '';
            if (tasks.length === 0) {
                tasksContainer.innerHTML = '<div class="text-sm text-slate-500 italic">No tasks.</div>';
            } else {
                const priorityColors = { Urgent: 'border-red-500 text-red-400', High: 'border-amber-500 text-amber-400', Medium: 'border-brand-accent text-brand-accent', Low: 'border-slate-500 text-slate-400' };
                tasks.forEach(t => {
                    const pc = priorityColors[t.priority] || priorityColors.Medium;
                    const isDone = t.status === 'Done';
                    tasksContainer.innerHTML += `
                        <div class="bg-slate-800/60 border-l-2 ${pc.split(' ')[0]} p-2.5 rounded text-sm ${isDone ? 'opacity-50' : ''}">
                            <div class="flex items-center gap-2">
                                <i class="ph ${isDone ? 'ph-check-circle text-emerald-400' : 'ph-circle-dashed'} ${pc.split(' ')[1]}"></i>
                                <span class="text-slate-200 ${isDone ? 'line-through' : ''}">${t.title}</span>
                            </div>
                            <div class="flex justify-between mt-1 pl-6">
                                <span class="text-[10px] text-slate-500">${t.due_date || 'No due date'}</span>
                                <span class="text-[10px] px-1.5 py-0.5 rounded ${t.priority === 'Urgent' ? 'bg-red-500/20 text-red-400' : t.priority === 'High' ? 'bg-amber-500/20 text-amber-400' : 'bg-slate-700 text-slate-400'}">${t.priority}</span>
                            </div>
                        </div>
                    `;
                });
            }
        }
        
        // Transition panes
        el.viewList.style.transform = 'translateX(-100%)';
        el.viewDetail.style.transform = 'translateX(0)';
        
    } catch (err) {
        console.error("Error loading account details:", err);
    }
}

// --- Quick Actions (demo-ready stubs) ---

function openQuickAction(type) {
    const labels = { quote: 'New Quote', note: 'Add Note', activity: 'Log Activity', edd: 'EDD Formatter' };
    const label = labels[type] || type;
    
    // For the demo: If Wizard is available, send a contextual query
    if (currentAccount) {
        const queries = {
            quote: 'Help me draft a new quote for this account. What services should I recommend based on their history?',
            note: 'What key observations should I document about this account right now?',
            activity: 'Log a follow-up call with this account. What talking points should I cover?',
            edd: 'What fields are missing or flagged on the EDD submission for this account?'
        };
        el.chatInput.value = queries[type] || `Help me with ${label} for this account.`;
        submitChat();
    }
}

// --- API Calls ---

async function fetchTerritoryHealth() {
    try {
        const res = await fetch('/api/territory/health');
        if (res.status === 429) {
            console.error("Rate limit exceeded while fetching territory health.");
            return;
        }
        if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
        const data = await res.json();
        
        el.metricRevenue.textContent = formatCurrency(data.ytd_revenue);
        el.metricAccounts.textContent = data.total_accounts;
        el.metricRisk.textContent = data.at_risk_accounts;
        
        // Also fetch pipeline summary
        const pipeRes = await fetch('/api/pipeline/summary');
        if (pipeRes.status === 429) {
            console.error("Rate limit exceeded while fetching pipeline summary.");
            return;
        }
        if (!pipeRes.ok) throw new Error(`HTTP error: ${pipeRes.status}`);
        const pipeData = await pipeRes.json();
        
        el.pipelineStages.innerHTML = '';
        
        // Sort by value desc
        pipeData.sort((a, b) => b.value - a.value);
        
        let totalValue = pipeData.reduce((sum, item) => sum + item.value, 0);
        
        // Update stage flow indicators — highlight stages that have accounts
        if (el.pipelineStageFlow) {
            const activeStages = new Set(pipeData.map(p => p.pipeline_stage));
            el.pipelineStageFlow.querySelectorAll('[data-stage]').forEach(span => {
                const stage = span.getAttribute('data-stage');
                if (activeStages.has(stage)) {
                    span.className = 'px-2 py-1 rounded bg-brand-500/20 text-brand-accent border border-brand-500/30 transition-all';
                } else {
                    span.className = 'px-2 py-1 rounded bg-slate-800 text-slate-500 border border-slate-700 transition-all';
                }
            });
        }
        
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
        if (res.status === 429) {
            console.error("Rate limit exceeded while fetching accounts.");
            return;
        }
        if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
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
        const hs = acc.health_score || 0;
        const hc = healthColor(hs);
        const days = daysSince(acc.last_contact_date);
        const daysLabel = days < 999 ? `${days}d ago` : 'Never';
        
        el.listContainer.innerHTML += `
            <div class="bg-slate-800/60 hover:bg-slate-700/80 p-3 rounded-lg border border-slate-700/50 cursor-pointer transition-colors hover-lift flex gap-3" onclick="showAccountDetail(${acc.id})">
                <div class="flex flex-col items-center gap-1 shrink-0 pt-0.5">
                    <div class="w-8 h-8 rounded-lg ${hc.bg}/20 flex items-center justify-center border ${hc.bg === 'bg-emerald-500' ? 'border-emerald-500/30' : hc.bg === 'bg-amber-500' ? 'border-amber-500/30' : 'border-red-500/30'}">
                        <span class="text-xs font-bold ${hc.text}">${hs}</span>
                    </div>
                </div>
                <div class="flex-1 min-w-0">
                    <div class="flex justify-between items-start mb-0.5">
                        <h3 class="font-semibold text-white truncate pr-2 text-sm">${acc.name}</h3>
                        <div class="text-brand-accent font-medium text-sm shrink-0">${formatCurrency(acc.ytd_revenue)}</div>
                    </div>
                    <div class="flex items-center justify-between text-xs text-slate-400">
                        <span class="truncate pr-2">${acc.industry || 'Unknown Industry'}</span>
                        <div class="flex items-center gap-2 shrink-0">
                            <span class="text-slate-500">${daysLabel}</span>
                            <span class="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-600 text-[10px]">${acc.pipeline_stage || 'Unknown'}</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    });
}

// --- Wizard Chat ---

function sendChipQuery(queryText) {
    el.chatInput.value = queryText;
    submitChat();
}

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
        if (response.status === 429) {
            el.typingIndicator.classList.add('hidden');
            appendMessage('assistant', `*Rate limit exceeded. Please wait a moment before sending another query.*`);
            return;
        }
        if (!response.ok) {
            throw new Error(`HTTP Error ${response.status}`);
        }
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
    const msgDiv = document.createElement('div');
    msgDiv.className = `flex gap-3 max-w-[90%] ${isUser ? 'ml-auto flex-row-reverse' : ''} animate-fade-in-up`;
    
    // Icon
    const iconDiv = document.createElement('div');
    iconDiv.className = `h-8 w-8 rounded-full flex items-center justify-center shrink-0 border shadow-sm ${
        isUser ? 'bg-brand-600 border-brand-500 shadow-brand-500/20' : 'bg-slate-800 border-slate-600 shadow-black/20'
    }`;
    iconDiv.innerHTML = isUser 
        ? `<span class="text-xs font-bold text-white">${document.getElementById('user-initials').textContent || 'U'}</span>`
        : `<i class="ph-fill ph-magic-wand text-brand-accent text-sm"></i>`;
    
    // Bubble
    const bubbleDiv = document.createElement('div');
    bubbleDiv.className = `border p-3.5 text-sm leading-relaxed shadow-md ${
        isUser 
            ? 'bg-gradient-to-br from-brand-600 to-brand-700 border-brand-500 text-white rounded-2xl rounded-tr-sm' 
            : 'bg-gradient-to-br from-slate-800 to-slate-900 border-slate-700/80 text-white rounded-2xl rounded-tl-sm prose prose-invert max-w-none'
    }`;
    
    if (isUser) {
        bubbleDiv.textContent = content;
    } else {
        const mdDiv = document.createElement('div');
        mdDiv.classList.add('markdown-body');
        mdDiv.innerHTML = marked.parse(content);
        bubbleDiv.appendChild(mdDiv);
    }
    
    msgDiv.appendChild(iconDiv);
    msgDiv.appendChild(bubbleDiv);
    
    el.chatHistory.appendChild(msgDiv);
    scrollToBottom();
    
    return bubbleDiv; // Return bubble so we can update it during stream
}

function appendEmptyAssistantMessage(id) {
    const html = `
        <div class="flex gap-3 max-w-[90%] animate-fade-in-up">
            <div class="h-8 w-8 rounded-full bg-slate-800 flex items-center justify-center shrink-0 border border-slate-600 shadow-sm shadow-black/20">
                <i class="ph-fill ph-magic-wand text-brand-accent text-sm"></i>
            </div>
            <div id="${id}" class="bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700/80 text-white p-3.5 rounded-2xl rounded-tl-sm text-sm leading-relaxed prose prose-invert max-w-none shadow-md">
                <div class="dot-flashing"></div>
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
