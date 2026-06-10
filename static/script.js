
let dashboardAbortController = null;

async function safeFetch(url, options) {
    const res = await fetch(url, options);
    if (!res.ok) {
        let msg = 'Erro no servidor';
        try {
            const data = await res.json();
            if(data.erro) msg = data.erro;
        } catch(e) {}
        throw new Error(msg);
    }
    return res.json();
}
function escapeHTML(str) {
    if (str === null || str === undefined) return '';
    return String(str).replace(/[&<>'"`/]/g, function (s) {
        return {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;',
            '`': '&#x60;',
            '/': '&#x2F;'
        }[s];
    });
}

// ─── ESTADO ────────────────────────────────────────────────────
let deleteTargetId = null;
let allUsersCache = [];
let returnViewAfterEdit = "listar";
let currentLookupUserId = null;
let currentLookupUserName = null;

// ─── NAVEGAÇÃO ─────────────────────────────────────────────────
document.querySelectorAll(".nav-item").forEach((item) => {
    item.addEventListener("click", (e) => {
        e.preventDefault();
        const view = item.dataset.view;
        if (view === "cadastrar") {
            cancelEdit();
        }
        switchView(view);
    });
});

function switchView(viewName) {
    if (!document.startViewTransition) {
        doSwitchView(viewName);
        return;
    }
    // Usa View Transitions nativo do navegador!
    document.startViewTransition(() => doSwitchView(viewName));
}

function doSwitchView(viewName) {
    document.querySelectorAll(".nav-item").forEach((n) => n.classList.remove("active"));
    const activeNav = document.querySelector(`.nav-item[data-view="${viewName}"]`);
    if(activeNav) activeNav.classList.add("active");

    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    const targetView = document.getElementById(`view-${viewName}`);
    if(targetView) targetView.classList.add("active");

    const titles = { dashboard: "Dashboard", cadastrar: "Cadastrar", listar: "Diretório" };
    const pageTitle = document.getElementById("page-title");
    if(pageTitle) pageTitle.textContent = titles[viewName];

    // Clear lookup details and suggestions when switching views
    clearLookupDetail();
    closeLookupDropdown();

    if (viewName === "dashboard") loadDashboard();
    if (viewName === "listar") {
        const searchInput = document.getElementById("search-input");
        const query = searchInput ? searchInput.value.trim() : "";
        loadUsers(query);
    }
}

// ─── TOAST ─────────────────────────────────────────────────────
function showToast(message, type = "success") {
    const toast = document.getElementById("toast");
    toast.innerHTML = type === "error" 
        ? `<span style="color:var(--color-danger); margin-right:8px;">⚠️</span> ${message}`
        : `<span style="color:var(--color-success); margin-right:8px;">✓</span> ${message}`;
    toast.className = `apple-toast ${type} show`;
    setTimeout(() => {
        toast.classList.remove("show");
    }, 3500);
}

// ─── TEMA (DARK / LIGHT) ────────────────────────────────────────
function toggleTheme() {
    const current = document.documentElement.getAttribute("data-theme");
    const next = current === "light" ? null : "light";
    
    if (next) {
        document.documentElement.setAttribute("data-theme", "light");
        localStorage.setItem("autoPing_theme", "light");
    } else {
        document.documentElement.removeAttribute("data-theme");
        localStorage.setItem("autoPing_theme", "dark");
    }
    
    // Atualizar texto do botão
    const btn = document.querySelector(".theme-toggle-btn");
    if (btn) {
        const isLight = next === "light";
        btn.innerHTML = isLight
            ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg> Modo Escuro'
            : '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg> Modo Claro';
    }
}

function initTheme() {
    const saved = localStorage.getItem("autoPing_theme");
    if (saved === "light") {
        document.documentElement.setAttribute("data-theme", "light");
        const btn = document.querySelector(".theme-toggle-btn");
        if (btn) {
            btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg> Modo Escuro';
        }
    } else {
        document.documentElement.removeAttribute("data-theme");
    }
}

// ─── UTILS ─────────────────────────────────────────────────────
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast("IP Copiado: " + text, "success");
    }).catch(err => {
        showToast("Erro ao copiar: " + err, "error");
    });
}

// ─── FAVORITOS E RECENTES (LOCALSTORAGE) ───────────────────────
function getFavorites() {
    return (JSON.parse(localStorage.getItem('autoPing_favorites')) || []).map(Number).filter(id => !isNaN(id) && id > 0);
}

function getRecents() {
    return (JSON.parse(localStorage.getItem('autoPing_recents')) || []).map(Number).filter(id => !isNaN(id) && id > 0);
}

function toggleFavorite(userId) {
    let favs = getFavorites();
    userId = Number(userId);
    if (favs.includes(userId)) {
        favs = favs.filter(id => id !== userId);
        showToast("Removido dos favoritos", "success");
    } else {
        favs.push(userId);
        showToast("Adicionado aos favoritos", "success");
    }
    localStorage.setItem('autoPing_favorites', JSON.stringify(favs));
    
    if (document.getElementById("view-dashboard").classList.contains("active")) {
        safeFetch("/usuarios").then(users => renderDashboardLists(users));
        const btn = document.getElementById(`fav-btn-${userId}`);
        if (btn) {
            btn.classList.toggle("active");
            btn.innerHTML = favs.includes(userId) 
                ? '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>'
                : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>';
        }
    }
}

function addRecent(userId) {
    let recents = getRecents();
    userId = Number(userId);
    recents = recents.filter(id => id !== userId);
    recents.unshift(userId);
    if (recents.length > 5) recents.pop();
    localStorage.setItem('autoPing_recents', JSON.stringify(recents));
}

// ─── MODAL ─────────────────────────────────────────────────────
let modalCallback = null;

function openConfirmModal(title, message, confirmText, confirmClass, callback) {
    document.getElementById("modal-title").textContent = title;
    document.getElementById("modal-message").innerHTML = message;
    
    const confirmBtn = document.getElementById("btn-confirm-action");
    confirmBtn.textContent = confirmText;
    confirmBtn.className = `modal-btn ${confirmClass}`;
    
    modalCallback = callback;
    document.getElementById("modal-overlay").classList.add("active");
}

function closeModal() {
    document.getElementById("modal-overlay").classList.remove("active");
    modalCallback = null;
}

function openModal(userId) {
    openConfirmModal(
        "Confirmar Exclusão",
        "Tem certeza que deseja excluir este registro? Esta ação não poderá ser desfeita.",
        "Excluir",
        "destructive",
        async () => {
            try {
                const data = await safeFetch(`/usuarios/${userId}`, { method: "DELETE" });
                showToast(data?.mensagem, "success");
                loadUsers();
                loadDashboard();
            } catch {
                showToast("Erro de conexão com o servidor.", "error");
            }
        }
    );
}

document.getElementById("btn-confirm-action").addEventListener("click", async () => {
    if (modalCallback) {
        await modalCallback();
    }
    closeModal();
});

// ─── GESTÃO DINÂMICA DE MÁQUINAS NO FORMULÁRIO ──────────────────
function addMachineField(machineData = null) {
    const container = document.getElementById("machines-container");
    if (!container) return;

    const idx = container.children.length + 1;
    const card = document.createElement("div");
    card.className = "machine-item-card";
    card.innerHTML = `
        <div class="form-group-section" style="margin-bottom: 16px; border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); overflow: hidden; background: var(--bg-surface);">
            <div class="form-group" style="background: var(--bg-surface-hover); padding: 12px 16px; display: flex; align-items: center; border-bottom: 1px solid var(--border-subtle);">
                <label style="font-weight: 600; width: auto;" class="machine-item-title">Máquina #${idx}</label>
                <div style="flex:1;"></div>
                <button type="button" class="pill-btn danger btn-remove-machine" title="Remover esta máquina">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>
                    Remover
                </button>
            </div>
            <div class="form-group" style="padding: 12px 16px; display: flex; align-items: center;">
                <label style="width: 120px;">Tipo</label>
                <select class="apple-input machine-tipo" style="cursor:pointer; appearance:none; flex: 1;">
                    <option value="Notebook">Notebook</option>
                    <option value="Desktop">Desktop</option>
                    <option value="Minidesk">Minidesk</option>
                </select>
            </div>
            <div class="form-divider" style="margin-left: 136px; height: 1px; background: var(--border-subtle);"></div>
            <div class="form-group" style="padding: 12px 16px; display: flex; align-items: center;">
                <label style="width: 120px;">Hostname</label>
                <input type="text" class="apple-input machine-hostname" placeholder="Ex: BRA-PC-JSILVA" style="flex: 1;" required>
                <button type="button" class="pill-btn machine-ping-btn" title="Pingar máquina" style="margin-left: 8px;">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
                    </svg>
                    Ping
                </button>
            </div>
            <div class="form-divider" style="margin-left: 136px; height: 1px; background: var(--border-subtle);"></div>
            <div class="form-group" style="padding: 12px 16px; display: flex; align-items: center;">
                <label style="width: 120px;">Serial</label>
                <input type="text" class="apple-input machine-serial" placeholder="Ex: 5CD1234XYZ" style="flex: 1;">
            </div>
            <div class="form-divider" style="margin-left: 136px; height: 1px; background: var(--border-subtle);"></div>
            <div class="form-group" style="padding: 12px 16px; display: flex; align-items: center;">
                <label style="width: 120px;">IP</label>
                <input type="text" class="apple-input machine-ip" placeholder="Ex: 10.0.0.15" style="flex: 1;">
            </div>
            <div class="machine-ping-result ping-result" style="display:none; margin: 12px 16px;"></div>
        </div>
    `;

    if (machineData) {
        card.querySelector(".machine-tipo").value = machineData.Tipo || "Notebook";
        card.querySelector(".machine-hostname").value = machineData.Hostname || "";
        card.querySelector(".machine-serial").value = machineData.Serial || "";
        card.querySelector(".machine-ip").value = machineData.IP || "";
    }

    card.querySelector(".btn-remove-machine").addEventListener("click", () => {
        card.remove();
        updateMachineTitles();
    });

    const pingBtn = card.querySelector(".machine-ping-btn");
    const hostnameInput = card.querySelector(".machine-hostname");
    const ipInput = card.querySelector(".machine-ip");
    const pingResult = card.querySelector(".machine-ping-result");

    pingBtn.addEventListener("click", async () => {
        const hostname = hostnameInput.value.trim();
        if (!hostname) {
            showToast("Preencha o hostname antes de pingar.", "error");
            return;
        }

        pingBtn.disabled = true;
        pingBtn.innerHTML = `<span class="spinner"></span>...`;
        pingResult.style.display = "none";

        try {
            const data = await safeFetch(`/ping/${encodeURIComponent(hostname)}`);
            ipInput.value = data.ip;
            pingResult.style.display = "flex";
            pingResult.className = `ping-result ${data.online ? "online" : "offline"}`;
            pingResult.innerHTML = `
                <span class="ping-dot ${data.online ? "dot-online" : "dot-offline"}"></span>
                <span><strong>${escapeHTML(hostname)}</strong> — IP: <strong>${escapeHTML(data.ip)}</strong> — ${data.online ? "Online" : "Offline"}</span>
            `;
            showToast(`IP resolvido: ${escapeHTML(data.ip)}`, "success");
        } catch (e) {
            pingResult.style.display = "flex";
            pingResult.className = "ping-result offline";
            pingResult.innerHTML = `
                <span class="ping-dot dot-offline"></span>
                <span>${escapeHTML(e.message)}</span>
            `;
            showToast(e.message || "Erro ao tentar pingar a máquina.", "error");
        }

        pingBtn.disabled = false;
        pingBtn.innerHTML = `
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
            </svg>
            Ping`;
    });

    container.appendChild(card);
}

function updateMachineTitles() {
    const container = document.getElementById("machines-container");
    if (!container) return;
    Array.from(container.children).forEach((card, idx) => {
        card.querySelector(".machine-item-title").textContent = `Máquina #${idx + 1}`;
    });
}

document.getElementById("btn-add-machine").addEventListener("click", () => {
    addMachineField();
});

// Helper para renderizar tags das máquinas nas tabelas
function renderMachineTags(maquinas) {
    if (!maquinas || maquinas.length === 0) return 'Sem máquinas';
    return maquinas.map(m => {
        const typeIcon = m.Tipo === 'Desktop' ? '🖥️' : (m.Tipo === 'Minidesk' ? '📟' : '💻');
        return `${typeIcon} ${escapeHTML(m.Hostname)}`;
    }).join(", ");
}

// ─── DASHBOARD ─────────────────────────────────────────────────
async function loadDashboard() {
    if (dashboardAbortController) {
        dashboardAbortController.abort();
    }
    dashboardAbortController = new AbortController();

    try {
        const users = await safeFetch("/usuarios");
        
        const total = users.length;
        
        let maquinasTotal = 0;
        users.forEach(u => {
            if (u.maquinas) maquinasTotal += u.maquinas.length;
        });

        const statTotal = document.getElementById("stat-total");
        const statMaquinas = document.getElementById("stat-maquinas");

        if (statTotal) statTotal.textContent = total;
        if (statMaquinas) statMaquinas.textContent = maquinasTotal;

        renderDashboardLists(users);

        // Tabela removida do dashboard no novo design
    } catch (error) {
        console.error("Erro ao carregar dashboard", error);
    }
}

function renderDashboardLists(allUsers) {
    const favIds = getFavorites();
    const recentIds = getRecents();

    const favList = document.getElementById("favorites-list");
    const recList = document.getElementById("recents-list");

    const renderMiniCard = (u) => {
        const hostsText = u.maquinas && u.maquinas.length > 0 
            ? u.maquinas.map(m => escapeHTML(m.Hostname)).join(", ") 
            : "Sem máquinas";
        const displayName = (u.RACF || u.Nome).replace(/"/g, '&quot;');
        return `
            <div class="mini-card" data-name="${escapeHTML(displayName)}" onclick="event.stopPropagation(); selectUserForLookup(${u.ID}, this.dataset.name)">
                <div class="mini-card-info">
                    <span class="mini-card-name">${escapeHTML(u.Nome)}</span>
                    <span class="mini-card-meta">RACF: ${escapeHTML(u.RACF || "-")} | Maqs: ${hostsText}</span>
                </div>
                <button class="btn-favorite ${favIds.includes(u.ID) ? 'active' : ''}" onclick="event.stopPropagation(); toggleFavorite(${u.ID})" title="Favoritar">
                    ${favIds.includes(u.ID) 
                        ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>'
                        : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>'}
                </button>
            </div>
        `;
    };

    const favUsers = favIds.map(id => allUsers.find(u => u.ID === id)).filter(Boolean);
    const recUsers = recentIds.map(id => allUsers.find(u => u.ID === id)).filter(Boolean);

    favList.innerHTML = favUsers.length > 0 
        ? favUsers.map(renderMiniCard).join("") 
        : '<div class="rich-empty-state"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg><div>Nenhum favorito salvo.<br><span style="font-size:0.8rem;opacity:0.7;">Busque um colaborador e clique na estrela.</span></div></div>';
    
    recList.innerHTML = recUsers.length > 0 
        ? recUsers.map(renderMiniCard).join("") 
        : '<div class="rich-empty-state"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg><div>Nenhuma busca recente.<br><span style="font-size:0.8rem;opacity:0.7;">Os últimos pesquisados aparecerão aqui.</span></div></div>';
}

// ─── PAGINAÇÃO ────────────────────────────────────────────────
const USERS_PER_PAGE = 15;
let currentPage = 1;

function renderPagination(totalUsers) {
    const totalPages = Math.ceil(totalUsers / USERS_PER_PAGE);
    const container = document.getElementById("pagination-controls");
    if (!container) return;

    if (totalPages <= 1) {
        container.innerHTML = "";
        return;
    }

    let html = '<div class="pagination">';
    html += `<button class="btn-page ${currentPage === 1 ? 'disabled' : ''}" 
        ${currentPage === 1 ? 'disabled' : ''} onclick="goToPage(${currentPage - 1})">
        ← Anterior
    </button>`;

    const maxVisiblePages = 7;
    if (totalPages <= maxVisiblePages) {
        for (let i = 1; i <= totalPages; i++) {
            html += `<button class="btn-page ${i === currentPage ? 'active' : ''}" onclick="goToPage(${i})">${i}</button>`;
        }
    } else {
        html += `<button class="btn-page ${1 === currentPage ? 'active' : ''}" onclick="goToPage(1)">1</button>`;
        let start = Math.max(2, currentPage - 1);
        let end = Math.min(totalPages - 1, currentPage + 1);
        
        if (currentPage <= 3) {
            end = 4;
        } else if (currentPage >= totalPages - 2) {
            start = totalPages - 3;
        }
        
        if (start > 2) {
            html += '<span class="page-dots">...</span>';
        }
        for (let i = start; i <= end; i++) {
            html += `<button class="btn-page ${i === currentPage ? 'active' : ''}" onclick="goToPage(${i})">${i}</button>`;
        }
        if (end < totalPages - 1) {
            html += '<span class="page-dots">...</span>';
        }
        html += `<button class="btn-page ${totalPages === currentPage ? 'active' : ''}" onclick="goToPage(${totalPages})">${totalPages}</button>`;
    }

    html += `<button class="btn-page ${currentPage === totalPages ? 'disabled' : ''}" 
        ${currentPage === totalPages ? 'disabled' : ''} onclick="goToPage(${currentPage + 1})">
        Próximo →
    </button>`;

    html += '</div>';
    html += `<span class="pagination-info">${totalUsers} registro${totalUsers !== 1 ? 's' : ''} — Página ${currentPage} de ${totalPages}</span>`;
    container.innerHTML = html;
}

function goToPage(page) {
    const totalPages = Math.ceil(allUsersCache.length / USERS_PER_PAGE);
    if (page < 1 || page > totalPages) return;
    currentPage = page;
    renderUsersPage();
}

function renderUsersPage() {
    const start = (currentPage - 1) * USERS_PER_PAGE;
    const end = start + USERS_PER_PAGE;
    const pageUsers = allUsersCache.slice(start, end);

    const ul = document.getElementById("users-grouped-list");
    ul.innerHTML = pageUsers.map((u) => `
        <li class="grouped-list-item stagger-item">
            <div class="list-avatar">${u.Nome ? escapeHTML(u.Nome.charAt(0).toUpperCase()) : "?"}</div>
            <div class="list-content">
                <span class="list-title">${escapeHTML(u.Nome) || "—"}</span>
                <span class="list-subtitle">RACF: ${escapeHTML(u.RACF || "—")} | Funcional: ${escapeHTML(u.Funcional || "—")} | ${renderMachineTags(u.maquinas)}</span>
            </div>
            <div class="list-actions">
                <button class="pill-btn" onclick="editUser(${u.ID})">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                    Editar
                </button>
                <button class="pill-btn danger" onclick="openModal(${u.ID})">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                    Apagar
                </button>
            </div>
        </li>
    `).join("");

    renderPagination(allUsersCache.length);
}

// ─── LISTAR USUÁRIOS ───────────────────────────────────────────
async function loadUsers(searchValue) {
    try {
        let url = "/usuarios";
        if (searchValue) {
            url += `?busca=${encodeURIComponent(searchValue)}`;
        }
        const users = await safeFetch(url);
        

        allUsersCache = users;
        currentPage = 1;

        const updateList = () => {
            const ul = document.getElementById("users-grouped-list");
            if (users.length === 0) {
                ul.innerHTML = '<div class="empty-state"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>Nenhum usuário encontrado.</div>';
                const pag = document.getElementById("pagination-controls");
                if (pag) pag.innerHTML = "";
                return;
            }
            renderUsersPage();
        };

        updateList();
    } catch {
        showToast("Erro ao carregar a lista de usuários.", "error");
    }
}

let searchTimeout;
document.getElementById("search-input").addEventListener("input", (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => loadUsers(e.target.value.trim()), 350);
});

// ─── CADASTRAR / EDITAR ────────────────────────────────────────
document.getElementById("user-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const editId = document.getElementById("edit-id").value;
    
    // Coleta dados das máquinas dinamicamente
    const machines = [];
    const container = document.getElementById("machines-container");
    if (container) {
        Array.from(container.children).forEach(card => {
            const tipo = card.querySelector(".machine-tipo").value;
            const hostname = card.querySelector(".machine-hostname").value.trim();
            const serial = card.querySelector(".machine-serial").value.trim();
            const ip = card.querySelector(".machine-ip").value.trim();
            
            if (hostname) {
                machines.push({ Tipo: tipo, Hostname: hostname, Serial: serial, IP: ip });
            }
        });
    }
    const payload = {
        RACF: document.getElementById("racf").value.trim(),
        Funcional: document.getElementById("funcional").value.trim(),
        Nome: document.getElementById("nome").value.trim(),
        Email: document.getElementById("email").value.trim(),
        Status: document.getElementById("status").value,
        maquinas: machines
    };

    try {
        let res;
        if (editId) {
            res = await fetch(`/usuarios/${editId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
        } else {
            res = await fetch("/cadastrar", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
        }

        const data = await res.json();
        if (res.ok) {
            showToast(data?.mensagem, "success");
            
            // Fix BUG #6: save name before cancelEdit()
            const nameValue = document.getElementById("nome").value.trim();
            cancelEdit();
            loadDashboard();
            loadUsers();
            if (editId) {
                switchView(returnViewAfterEdit);
                if (returnViewAfterEdit === "dashboard" && currentLookupUserId == editId) {
                    selectUserForLookup(editId, nameValue);
                }
            }
        } else {
            showToast(escapeHTML(data.erro), "error");
        }
    } catch (e) {
        console.error(e);
        showToast("Erro de conexão com o servidor.", "error");
    }
});

async function editUser(userId) {
    try {
        const user = await safeFetch(`/usuarios/${userId}`);


        const activeNav = document.querySelector(".nav-item.active");
        if (activeNav) {
            returnViewAfterEdit = activeNav.dataset.view;
        } else {
            returnViewAfterEdit = "listar";
        }

        switchView("cadastrar");

        document.getElementById("edit-id").value = user.ID;
        document.getElementById("racf").value = user.RACF || "";
        document.getElementById("funcional").value = user.Funcional || "";
        document.getElementById("nome").value = user.Nome || "";
        document.getElementById("email").value = user.Email || "";
        document.getElementById("status").value = user.Status || "Ativo";

        const container = document.getElementById("machines-container");
        if (container) {
            container.innerHTML = "";
            if (user.maquinas && user.maquinas.length > 0) {
                user.maquinas.forEach(maq => addMachineField(maq));
            } else {
                addMachineField();
            }
        }

        document.getElementById("form-title").textContent = "Editar Registro";
        document.getElementById("btn-submit").innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
                <polyline points="17 21 17 13 7 13 7 21"/>
                <polyline points="7 3 7 8 15 8"/>
            </svg>
            Salvar Alterações`;
        document.getElementById("btn-cancel").style.display = "inline-flex";
    } catch {
        showToast("Erro ao carregar os dados do usuário.", "error");
    }
}

function cancelEdit() {
    document.getElementById("edit-id").value = "";
    document.getElementById("user-form").reset();
    
    const container = document.getElementById("machines-container");
    if (container) {
        container.innerHTML = "";
        addMachineField();
    }

    document.getElementById("form-title").textContent = "Novo Registro";
    document.getElementById("btn-submit").innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
            <polyline points="17 21 17 13 7 13 7 21"/>
            <polyline points="7 3 7 8 15 8"/>
        </svg>
        Cadastrar`;
    document.getElementById("btn-cancel").style.display = "none";
}

function cancelEditBtnClicked() {
    cancelEdit();
    switchView(returnViewAfterEdit);
}

// ─── CONSULTAR COLABORADOR ─────────────────────────────────────
let lookupTimeout;
document.getElementById("lookup-input").addEventListener("input", (e) => {
    clearTimeout(lookupTimeout);
    lookupTimeout = setTimeout(() => {
        const query = e.target.value.trim();
        if (query.length > 0) {
            lookupUserSuggestions(query);
        } else {
            closeLookupDropdown();
            document.getElementById("lookup-results").style.display = "none";
            document.getElementById("lookup-empty").style.display = "none";
        }
    }, 300);
});

document.addEventListener("click", (e) => {
    const resultsDiv = document.getElementById("lookup-results");
    const input = document.getElementById("lookup-input");
    if (resultsDiv && !resultsDiv.contains(e.target) && e.target !== input) {
        closeLookupDropdown();
    }
});

async function lookupUserSuggestions(query) {
    const resultsDiv = document.getElementById("lookup-results");
    const emptyDiv = document.getElementById("lookup-empty");
    
    try {
        const users = await safeFetch(`/usuarios?busca=${encodeURIComponent(query)}`);
        
        
        if (users.length === 0) {
            resultsDiv.style.display = "none";
            emptyDiv.style.display = "block";
            emptyDiv.textContent = "Nenhum colaborador encontrado.";
            return;
        }
        
        resultsDiv.style.display = "block";
        emptyDiv.style.display = "none";
        resultsDiv.innerHTML = users.slice(0, 8).map((u) => {
            const hosts = u.maquinas && u.maquinas.length > 0 ? u.maquinas.map(m => escapeHTML(m.Hostname)).join(", ") : "Sem máquinas";
            const displayName = (u.RACF || u.Nome).replace(/"/g, '&quot;');
            return `
                <div class="mini-card" data-name="${escapeHTML(displayName)}" onclick="event.stopPropagation(); selectUserForLookup(${u.ID}, this.dataset.name)"
                     style="cursor:pointer;">
                    <div class="mini-card-info">
                        <span class="mini-card-name">${escapeHTML(u.Nome)}</span>
                        <span class="mini-card-meta">RACF: ${escapeHTML(u.RACF || "-")} | Maqs: ${hosts}</span>
                    </div>
                </div>
            `;
        }).join("");
        
    } catch {
        resultsDiv.style.display = "none";
        emptyDiv.style.display = "block";
        emptyDiv.textContent = "Erro ao carregar sugestões.";
    }
}

function closeLookupDropdown() {
    const resultsDiv = document.getElementById("lookup-results");
    const emptyDiv = document.getElementById("lookup-empty");
    if (resultsDiv) resultsDiv.style.display = "none";
    if (emptyDiv) emptyDiv.style.display = "none";
}

async function selectUserForLookup(userId, userDisplayValue) {
    const input = document.getElementById('lookup-input');
    if (input) input.value = userDisplayValue;
    
    // Hide the suggestions dropdown list
    closeLookupDropdown();
    
    currentLookupUserId = userId;
    currentLookupUserName = userDisplayValue;

    const detailDiv = document.getElementById("lookup-detail");
    if (detailDiv) {
        detailDiv.style.display = "block";
        detailDiv.style.animation = "none";
        // Force reflow
        void detailDiv.offsetWidth;
        detailDiv.style.animation = "modalSlideIn 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards";
        
        detailDiv.innerHTML = `<div class="apple-card" style="text-align: center; padding: 24px; margin-top: 16px; min-height: 200px; display: flex; align-items: center; justify-content: center;"><span class="spinner"></span> <span style="margin-left: 8px;">Carregando colaborador...</span></div>`;
    }
    
    try {
        const user = await safeFetch(`/usuarios/${userId}`);
        
        
        
        
        addRecent(user.ID);
        
        const favs = getFavorites();
        let machinesHtml = "";
        
        if (user.maquinas && user.maquinas.length > 0) {
            machinesHtml = user.maquinas.map((m, index) => {
                const typeIcon = m.Tipo === 'Desktop' ? '🖥️' : (m.Tipo === 'Minidesk' ? '📟' : '💻');
                return `
                    <div class="lookup-machine-block" style="border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); padding: 16px; background: var(--bg-surface-hover); margin-top: 16px;">
                        <div style="font-weight:600; font-size:0.95rem; margin-bottom:12px; display:flex; align-items:center; gap:8px;">
                            <span>${typeIcon}</span>
                            <span>${escapeHTML(m.Tipo)}</span>
                            <span class="mono" style="font-size:0.85rem; padding: 2px 6px; background:var(--bg-body); border-radius:var(--radius-sm);">${escapeHTML(m.Hostname)}</span>
                        </div>
                        <div class="lookup-card-body" style="border:none; padding:0; margin-bottom:16px; display:grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap:12px;">
                            <div class="lookup-field">
                                <span style="font-size: 0.75rem; color: var(--text-secondary); display:block;">Serial</span>
                                <span class="mono" style="font-size: 0.85rem;">${escapeHTML(m.Serial || '—')}</span>
                            </div>
                            <div class="lookup-field">
                                <span style="font-size: 0.75rem; color: var(--text-secondary); display:block;">IP Cadastrado</span>
                                <span class="mono" style="font-size: 0.85rem;">${escapeHTML(m.IP || '—')}</span>
                            </div>
                            <div class="lookup-field">
                                <span style="font-size: 0.75rem; color: var(--text-secondary); display:block;">IP Atual</span>
                                <span class="mono" style="font-size: 0.85rem; display:inline-flex; align-items:center; gap:4px;" id="live-ip-${user.ID}-${index}">
                                    <span class="spinner"></span> ...
                                </span>
                            </div>
                            <div class="lookup-field">
                                <span style="font-size: 0.75rem; color: var(--text-secondary); display:block;">Status</span>
                                <span style="font-size: 0.85rem; display:inline-flex; align-items:center; gap:4px;" id="live-status-${user.ID}-${index}">
                                    <span class="spinner"></span> ...
                                </span>
                            </div>
                        </div>
                        <div style="display: flex; gap: 8px;">
                            <button class="pill-btn primary" onclick="downloadCustomRdp('${escapeHTML(m.IP || m.Hostname)}')" title="Acessar Área de Trabalho Remota">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
                                    <line x1="8" y1="21" x2="16" y2="21"></line>
                                    <line x1="12" y1="17" x2="12" y2="21"></line>
                                </svg>
                                Acessar
                            </button>
                            <button class="pill-btn danger" onclick="confirmShutdownSpecific('${escapeHTML(m.Hostname)}', 'live-ip-${user.ID}-${index}', '${escapeHTML(m.IP)}', '${escapeHTML(user.Nome)} (${escapeHTML(m.Tipo)})')">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M18.36 6.64a9 9 0 1 1-12.73 0"></path>
                                    <line x1="12" y1="2" x2="12" y2="12"></line>
                                </svg>
                                Desligar
                            </button>
                            <button class="pill-btn" onclick="confirmRestartSpecific('${escapeHTML(m.Hostname)}', 'live-ip-${user.ID}-${index}', '${escapeHTML(m.IP)}', '${escapeHTML(user.Nome)} (${escapeHTML(m.Tipo)})')">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"></path>
                                </svg>
                                Reiniciar
                            </button>
                        </div>
                    </div>
                `;
            }).join("");
        } else {
            machinesHtml = `<div style="text-align:center; padding:20px; color:var(--text-muted); font-size:0.85rem;">Nenhuma máquina vinculada a este colaborador.</div>`;
        }

        const renderDetail = () => {
            if (detailDiv) {
                detailDiv.innerHTML = `
                    <div class="apple-card" id="lookup-card-${user.ID}" style="margin-top: 16px; padding: 24px; animation: fadeIn 0.3s ease-out forwards;">
                        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom: 1px solid var(--border-subtle); padding-bottom: 16px;">
                            <div style="display:flex; align-items:center; gap:16px;">
                                <div class="list-avatar">${escapeHTML(user.Nome.charAt(0).toUpperCase())}</div>
                                <div style="display: flex; flex-direction: column;">
                                    <span style="font-weight: 600; font-size: 1.1rem;">${escapeHTML(user.Nome)}</span>
                                    <span style="font-size: 0.85rem; color: var(--text-secondary);">RACF: <strong>${user.RACF || "-"}</strong> &nbsp;|&nbsp; Funcional: <strong>${user.Funcional || "-"}</strong></span>
                                </div>
                            </div>
                            <div style="display:flex; gap:8px; align-items:center;">
                                <span class="ping-result ${(user.Status || 'ativo').toLowerCase() === 'ativo' ? 'online' : 'offline'}" style="margin:0; padding: 4px 12px; border-radius: 999px;">
                                    <span class="ping-dot ${(user.Status || 'ativo').toLowerCase() === 'ativo' ? 'dot-online' : 'dot-offline'}"></span>
                                    ${user.Status || 'Ativo'}
                                </span>
                                <button class="icon-btn" onclick="editUser(${user.ID})" title="Editar">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                                    </svg>
                                </button>
                                <button id="fav-btn-${user.ID}" class="icon-btn ${favs.includes(user.ID) ? 'active' : ''}" onclick="toggleFavorite(${user.ID})" title="Favoritar">
                                    ${favs.includes(user.ID) 
                                        ? '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>'
                                        : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>'}
                                </button>
                                <button class="pill-btn danger" onclick="clearLookupDetail()" title="Fechar">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <line x1="18" y1="6" x2="6" y2="18"></line>
                                        <line x1="6" y1="6" x2="18" y2="18"></line>
                                    </svg>
                                    Fechar
                                </button>
                            </div>
                        </div>
                        
                        <div style="padding-top: 16px;">
                            <div style="font-weight:600; font-size:0.8rem; letter-spacing: 0.5px; color:var(--text-secondary);">MÁQUINAS CADASTRADAS</div>
                            ${machinesHtml}
                        </div>
                    </div>
                `;
            }
        };

        renderDetail();
        
        if (user.maquinas && user.maquinas.length > 0) {
            user.maquinas.forEach((m, index) => {
                autoPingSpecific(user.ID, index, m.Hostname);
            });
        }
        
        // Atualiza a lista de recentes silenciosamente
        if (document.getElementById("view-dashboard").classList.contains("active")) {
            safeFetch("/usuarios").then(users => renderDashboardLists(users));
        }
        
    } catch (error) {
        console.error("Erro ao carregar lookup", error);
        if (detailDiv) {
            detailDiv.innerHTML = `<div class="apple-card" style="text-align: center; padding: 24px; margin-top: 16px; color: var(--color-danger);">Erro ao carregar colaborador.</div>`;
        }
    }
}

function clearLookupDetail() {
    const doClear = () => {
        currentLookupUserId = null;
        currentLookupUserName = null;
        const detailDiv = document.getElementById("lookup-detail");
        if (detailDiv) {
            detailDiv.style.animation = "fadeOut 0.2s ease-out forwards";
            setTimeout(() => {
                detailDiv.innerHTML = "";
                detailDiv.style.display = "none";
                detailDiv.style.animation = "";
            }, 200);
        }
        const input = document.getElementById('lookup-input');
        if (input) {
            input.value = "";
        }
    };
    
    doClear();
}

async function autoPingSpecific(userId, index, hostname) {
    const ipEl = document.getElementById(`live-ip-${userId}-${index}`);
    const statusEl = document.getElementById(`live-status-${userId}-${index}`);

    try {
        const data = await safeFetch(`/ping/${encodeURIComponent(hostname)}`, {
            signal: dashboardAbortController ? dashboardAbortController.signal : undefined
        });
        

        if (true) {
            if (ipEl) {
                ipEl.innerHTML = `${escapeHTML(data.ip)} <button type="button" class="btn-copy" onclick="copyToClipboard('${escapeHTML(data.ip)}')" title="Copiar IP"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg></button>`;
            }
            if (statusEl) {
                statusEl.innerHTML = data.online
                    ? '<span class="ping-dot dot-online"></span> <span style="color:var(--color-success)">Online</span>'
                    : '<span class="ping-dot dot-offline"></span> <span style="color:var(--color-danger)">Offline</span>';
            }
        } else {
            if (ipEl) ipEl.textContent = "Não resolvido";
            if (statusEl) statusEl.innerHTML = '<span class="ping-dot dot-offline"></span> <span style="color:var(--color-danger)">Não acessível</span>';
        }
    } catch {
        if (ipEl) ipEl.textContent = "Erro";
        if (statusEl) statusEl.innerHTML = '<span style="color:var(--color-danger)">Erro na conexão</span>';
    }
}

// ─── AÇÕES REMOTAS (DESLIGAR / REINICIAR ESPECÍFICOS) ───────────
function getSpecificActionTarget(hostname, liveIpElementId, registeredIp) {
    const liveIpEl = document.getElementById(liveIpElementId);
    if (liveIpEl) {
        const match = liveIpEl.innerText.match(/(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/);
        if (match && match[1]) {
            return match[1];
        }
    }
    
    if (registeredIp && registeredIp !== "—" && registeredIp !== "") {
        return registeredIp;
    }
    
    if (hostname) {
        return hostname;
    }
    
    return null;
}

function copyModalCommand() {
    const cmdInput = document.getElementById("cmd-to-copy");
    if (cmdInput) {
        navigator.clipboard.writeText(cmdInput.value).then(() => {
            showToast("Comando copiado com sucesso!", "success");
        }).catch(err => {
            showToast("Erro ao copiar comando: " + err, "error");
        });
    }
}

function confirmShutdownSpecific(hostname, liveIpElementId, registeredIp, displayName) {
    const target = getSpecificActionTarget(hostname, liveIpElementId, registeredIp);
    if (!target) {
        showToast("Nenhum IP ou Hostname disponível para esta máquina.", "error");
        return;
    }
    
    const cmd = `shutdown /s /f /t 0 /m \\\\${target}`;
    const messageHtml = `
        <p style="margin-bottom: 12px;">Escolha como deseja <strong>desligar</strong> a máquina de <strong>${escapeHTML(displayName)}</strong> (${target}):</p>
        
        <div style="background: var(--bg-surface-hover); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 16px; margin-bottom: 16px;">
            <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 12px;">1. Executar via Jump Server (Configurado nas configurações)</p>
            <button type="button" class="apple-btn-primary" style="width: 100%; background: var(--color-danger); color: white;" onclick="executeJumpAction('shutdown', '${target}')">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:8px;"><path d="M18.36 6.64a9 9 0 1 1-12.73 0"></path><line x1="12" y1="2" x2="12" y2="12"></line></svg>
                Executar Automático (Jump Server)
            </button>
        </div>

        <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 8px;">2. Ou copie o comando para rodar manualmente:</p>
        <div style="position:relative;">
            <input type="text" id="cmd-to-copy" value="${cmd}" readonly 
                style="width:100%; padding:12px 40px 12px 12px; font-family: Consolas, monospace; font-size:0.85rem; border:1px solid var(--border-subtle); border-radius:var(--radius-sm); background:var(--bg-surface-hover); color:var(--text-primary); outline:none;">
            <button type="button" class="btn-copy" onclick="copyModalCommand()" title="Copiar Comando" style="position:absolute; right:12px; top:50%; transform:translateY(-50%); margin:0; padding:4px; display:inline-flex; align-items:center; justify-content:center; background:transparent; border:none; cursor:pointer;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
            </button>
        </div>
    `;
    
    openConfirmModal(
        "Desligar Máquina",
        messageHtml,
        "Fechar",
        "primary",
        () => {}
    );
}

function confirmRestartSpecific(hostname, liveIpElementId, registeredIp, displayName) {
    const target = getSpecificActionTarget(hostname, liveIpElementId, registeredIp);
    if (!target) {
        showToast("Nenhum IP ou Hostname disponível para esta máquina.", "error");
        return;
    }
    
    const cmd = `shutdown /r /f /t 0 /m \\\\${target}`;
    const messageHtml = `
        <p style="margin-bottom: 12px;">Escolha como deseja <strong>reiniciar</strong> a máquina de <strong>${escapeHTML(displayName)}</strong> (${target}):</p>
        
        <div style="background: var(--bg-surface-hover); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 16px; margin-bottom: 16px;">
            <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 12px;">1. Executar via Jump Server (Configurado nas configurações)</p>
            <button type="button" class="apple-btn-primary" style="width: 100%;" onclick="executeJumpAction('restart', '${target}')">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:8px;"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"></path></svg>
                Executar Automático (Jump Server)
            </button>
        </div>

        <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 8px;">2. Ou copie o comando para rodar manualmente:</p>
        <div style="position:relative;">
            <input type="text" id="cmd-to-copy" value="${cmd}" readonly 
                style="width:100%; padding:12px 40px 12px 12px; font-family: Consolas, monospace; font-size:0.85rem; border:1px solid var(--border-subtle); border-radius:var(--radius-sm); background:var(--bg-surface-hover); color:var(--text-primary); outline:none;">
            <button type="button" class="btn-copy" onclick="copyModalCommand()" title="Copiar Comando" style="position:absolute; right:12px; top:50%; transform:translateY(-50%); margin:0; padding:4px; display:inline-flex; align-items:center; justify-content:center; background:transparent; border:none; cursor:pointer;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
            </button>
        </div>
    `;
    
    openConfirmModal(
        "Reiniciar Máquina",
        messageHtml,
        "Fechar",
        "primary",
        () => {}
    );
}

// ─── CONFIGURAÇÕES DO JUMP SERVER ──────────────────────────────
function openJumpConfigModal() {
    loadJumpConfig();
    document.getElementById("jump-config-overlay").classList.add("active");
}

function closeJumpConfigModal() {
    document.getElementById("jump-config-overlay").classList.remove("active");
}

function saveJumpConfig() {
    const config = {
        rdpPath: document.getElementById("jump-rdp-path").value.trim(),
        ip: document.getElementById("jump-ip").value.trim(),
        user: document.getElementById("jump-user").value.trim(),
        cmdShutdown: document.getElementById("jump-cmd-shutdown").value.trim() || "C:\\Scripts\\desligar.bat",
        cmdRestart: document.getElementById("jump-cmd-restart").value.trim() || "C:\\Scripts\\reiniciar.bat"
    };
    const pass = document.getElementById("jump-pass").value.trim();
    if (pass) {
        sessionStorage.setItem("autoPing_jumpPass", pass);
    }
    
    if (!config.rdpPath && !config.ip) {
        showToast("Preencha o caminho do .rdp ou o IP do Jump Server para salvar.", "error");
        return;
    }
    
    localStorage.setItem("autoPing_jumpConfig", JSON.stringify(config));
    showToast("Configurações do Jump Server salvas!", "success");
    closeJumpConfigModal();
}

function loadJumpConfig() {
    const saved = localStorage.getItem("autoPing_jumpConfig");
    if (saved) {
        const config = JSON.parse(saved);
        document.getElementById("jump-rdp-path").value = config.rdpPath || "";
        document.getElementById("jump-ip").value = config.ip || "";
        document.getElementById("jump-user").value = config.user || "";
        document.getElementById("jump-pass").value = sessionStorage.getItem("autoPing_jumpPass") || "";
        document.getElementById("jump-cmd-shutdown").value = config.cmdShutdown || "";
        document.getElementById("jump-cmd-restart").value = config.cmdRestart || "";
    }
}

function downloadCustomRdp(targetIp) {
    const saved = localStorage.getItem("autoPing_jumpConfig");
    let baseRdp = "";
    if (saved) {
        const config = JSON.parse(saved);
        if (config.rdpPath) {
            baseRdp = encodeURIComponent(config.rdpPath);
        }
    }
    
    let url = `/api/download-rdp/${targetIp}`;
    if (baseRdp) {
        url += `?base_rdp=${baseRdp}`;
    }
    window.location.href = url;
}

async function executeJumpAction(action, targetIp) {
    const saved = localStorage.getItem("autoPing_jumpConfig");
    if (!saved) {
        closeModal();
        showToast("Configure seu Jump Server primeiro!", "error");
        openJumpConfigModal();
        return;
    }
    
    const config = JSON.parse(saved);
    const command = action === 'shutdown' ? config.cmdShutdown : config.cmdRestart;
    const fullCmdToCopy = `${command} ${targetIp}`;
    
    // Copiar para a área de transferência do usuário como medida de segurança!
    try {
        await navigator.clipboard.writeText(fullCmdToCopy);
    } catch(err) {
        console.warn("Não foi possível copiar para o clipboard automaticamente", err);
    }

    showToast("Comando copiado! Cole no CMD do Jump Server...", "success");
    closeModal();
    
    try {
        const payload = {
            rdp_path: config.rdpPath,
            jump_ip: config.ip,
            jump_user: config.user,
            jump_pass: sessionStorage.getItem("autoPing_jumpPass") || "",
            command: command,
            target_ip: targetIp
        };
        
        const data = await safeFetch("/api/jump-action", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        console.log(data?.mensagem);
    } catch (error) {
        showToast("Falha ao comunicar com o backend.", "error");
    }
}

// ─── INICIALIZAÇÃO ─────────────────────────────────────────────
initTheme();
loadDashboard();

// Preencher a data do Hero Banner
const dateOptions = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
const todayDate = new Date().toLocaleDateString('pt-BR', dateOptions);
const heroDateEl = document.getElementById("hero-date");
if (heroDateEl) heroDateEl.textContent = todayDate.charAt(0).toUpperCase() + todayDate.slice(1);

const hour = new Date().getHours();
let greeting = "Boa noite";
if (hour >= 5 && hour < 12) greeting = "Bom dia";
else if (hour >= 12 && hour < 18) greeting = "Boa tarde";

const heroGreetingEl = document.getElementById("hero-greeting");
if (heroGreetingEl) heroGreetingEl.textContent = `${greeting}, Admin`;


// Inicializa o contêiner de máquinas com uma vazia por padrão
const mContainer = document.getElementById("machines-container");
if (mContainer && mContainer.children.length === 0) {
    addMachineField();
}

// --- CRDITOS --------------------------------------------------
function openCreditsModal() {
    document.getElementById("credits-overlay").classList.add("active");
}
function closeCreditsModal() {
    document.getElementById("credits-overlay").classList.remove("active");
}
