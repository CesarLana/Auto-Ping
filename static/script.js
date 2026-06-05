// ─── ESTADO ────────────────────────────────────────────────────
let deleteTargetId = null;

// ─── NAVEGAÇÃO ─────────────────────────────────────────────────
document.querySelectorAll(".nav-item").forEach((item) => {
    item.addEventListener("click", (e) => {
        e.preventDefault();
        const view = item.dataset.view;
        switchView(view);
    });
});

function switchView(viewName) {
    document.querySelectorAll(".nav-item").forEach((n) => n.classList.remove("active"));
    document.querySelector(`.nav-item[data-view="${viewName}"]`).classList.add("active");

    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    document.getElementById(`view-${viewName}`).classList.add("active");

    const titles = { dashboard: "Dashboard", cadastrar: "Cadastrar", listar: "Usuários" };
    const breadcrumbs = {
        dashboard: "Início / Dashboard",
        cadastrar: "Início / Cadastrar",
        listar: "Início / Usuários",
    };
    document.getElementById("page-title").textContent = titles[viewName];
    document.querySelector(".header-breadcrumb").textContent = breadcrumbs[viewName];

    if (viewName === "dashboard") loadDashboard();
    if (viewName === "listar") loadUsers();
}

// ─── TOAST ─────────────────────────────────────────────────────
function showToast(message, type = "success") {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.className = `toast ${type} show`;
    setTimeout(() => toast.classList.remove("show"), 3500);
}

// ─── TEMA (DARK MODE) ───────────────────────────────────────────
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute("data-theme");
    const newTheme = currentTheme === "dark" ? "light" : "dark";
    
    document.documentElement.setAttribute("data-theme", newTheme);
    localStorage.setItem("autoPing_theme", newTheme);
    
    const label = document.getElementById("theme-label");
    if (label) label.textContent = newTheme === "dark" ? "Modo Claro" : "Modo Escuro";
}

function initTheme() {
    const savedTheme = localStorage.getItem("autoPing_theme");
    if (savedTheme === "dark") {
        document.documentElement.setAttribute("data-theme", "dark");
        const label = document.getElementById("theme-label");
        if (label) label.textContent = "Modo Claro";
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
    return JSON.parse(localStorage.getItem('autoPing_favorites')) || [];
}

function getRecents() {
    return JSON.parse(localStorage.getItem('autoPing_recents')) || [];
}

function toggleFavorite(userId) {
    let favs = getFavorites();
    if (favs.includes(userId)) {
        favs = favs.filter(id => id !== userId);
        showToast("Removido dos favoritos", "success");
    } else {
        favs.push(userId);
        showToast("Adicionado aos favoritos", "success");
    }
    localStorage.setItem('autoPing_favorites', JSON.stringify(favs));
    
    // Atualiza a interface se estiver na tela de dashboard
    if (document.getElementById("view-dashboard").classList.contains("active")) {
        loadDashboard();
        
        // Atualiza a estrela no lookup se estiver visível
        const btn = document.getElementById(`fav-btn-${userId}`);
        if (btn) {
            btn.classList.toggle("active");
            btn.innerHTML = favs.includes(userId) 
                ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>'
                : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>';
        }
    }
}

function addRecent(userId) {
    let recents = getRecents();
    recents = recents.filter(id => id !== userId); // remove se já existir
    recents.unshift(userId); // adiciona no topo
    if (recents.length > 5) recents.pop(); // mantém apenas os 5 últimos
    localStorage.setItem('autoPing_recents', JSON.stringify(recents));
}

// ─── MODAL ─────────────────────────────────────────────────────
let modalCallback = null;

function openConfirmModal(title, message, confirmText, confirmClass, callback) {
    document.getElementById("modal-title").textContent = title;
    document.getElementById("modal-message").textContent = message;
    
    const confirmBtn = document.getElementById("btn-confirm-action");
    confirmBtn.textContent = confirmText;
    confirmBtn.className = `btn ${confirmClass}`;
    
    modalCallback = callback;
    document.getElementById("modal-overlay").classList.add("show");
}

function closeModal() {
    document.getElementById("modal-overlay").classList.remove("show");
    modalCallback = null;
}

// Mantém openModal por compatibilidade com a tabela de usuários
function openModal(userId) {
    openConfirmModal(
        "Confirmar Exclusão",
        "Tem certeza que deseja excluir este registro? Esta ação não poderá ser desfeita.",
        "Excluir",
        "btn-danger",
        async () => {
            try {
                const res = await fetch(`/usuarios/${userId}`, { method: "DELETE" });
                const data = await res.json();
                if (res.ok) {
                    showToast(data.mensagem, "success");
                    loadUsers();
                    loadDashboard();
                } else {
                    showToast(data.erro, "error");
                }
            } catch {
                showToast("Erro de conexão com o servidor.", "error");
            }
        }
    );
}

document.getElementById("btn-confirm-action").addEventListener("click", () => {
    if (modalCallback) {
        modalCallback();
    }
    closeModal();
});

// ─── PING ──────────────────────────────────────────────────────
document.getElementById("btn-ping").addEventListener("click", async () => {
    const hostname = document.getElementById("hostname").value.trim();
    if (!hostname) {
        showToast("Preencha o hostname antes de pingar.", "error");
        return;
    }

    const btn = document.getElementById("btn-ping");
    const pingResult = document.getElementById("ping-result");

    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span> Pingando...`;
    pingResult.style.display = "none";

    try {
        const res = await fetch(`/ping/${encodeURIComponent(hostname)}`);
        const data = await res.json();

        if (res.ok) {
            document.getElementById("ip").value = data.ip;
            pingResult.style.display = "flex";
            pingResult.className = `ping-result ${data.online ? "online" : "offline"}`;
            pingResult.innerHTML = `
                <span class="ping-dot ${data.online ? "dot-online" : "dot-offline"}"></span>
                <span><strong>${hostname}</strong> — IP: <strong>${data.ip}</strong> <button type="button" class="btn-copy" onclick="copyToClipboard('${data.ip}')" title="Copiar IP" style="margin-top:-2px;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg></button> — ${data.online ? "Máquina Online" : "Máquina Offline"}</span>
            `;
            showToast(`IP resolvido: ${data.ip}`, "success");
        } else {
            pingResult.style.display = "flex";
            pingResult.className = "ping-result offline";
            pingResult.innerHTML = `
                <span class="ping-dot dot-offline"></span>
                <span>${data.erro}</span>
            `;
            showToast(data.erro, "error");
        }
    } catch {
        showToast("Erro ao tentar pingar a máquina.", "error");
    }

    btn.disabled = false;
    btn.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
        </svg>
        Ping`;
});

// ─── DASHBOARD ─────────────────────────────────────────────────
async function loadDashboard() {
    try {
        const res = await fetch("/usuarios");
        const users = await res.json();
        const total = users.length;
        const maquinas = users.filter((u) => u.Hostname && u.Hostname !== "").length;

        const statTotal = document.getElementById("stat-total");
        const statMaquinas = document.getElementById("stat-maquinas");

        if (statTotal) statTotal.textContent = total;
        if (statMaquinas) statMaquinas.textContent = maquinas;

        renderDashboardLists(users);

        const dbTbody = document.getElementById("dashboard-table-body");
        if (dbTbody) {
            const lastUsers = users.slice().reverse().slice(0, 5);
            if (lastUsers.length === 0) {
                dbTbody.innerHTML = '<tr><td colspan="6" class="empty-state">Nenhum registro encontrado.</td></tr>';
            } else {
                dbTbody.innerHTML = lastUsers.map((u) => `
                    <tr>
                        <td><span class="mono">${u.RACF || "—"}</span></td>
                        <td><span class="mono">${u.Funcional || "—"}</span></td>
                        <td>${u.Nome || "—"}</td>
                        <td><span class="mono">${u.Hostname || "—"}</span></td>
                        <td><span class="mono">${u.IP || "—"}</span></td>
                        <td><span class="badge badge-${(u.Status || "ativo").toLowerCase()}"><span class="badge-dot"></span>${u.Status || "Ativo"}</span></td>
                    </tr>
                `).join("");
            }
        }
    } catch (error) {
        console.error("Erro ao carregar dashboard", error);
    }
}

function renderDashboardLists(allUsers) {
    const favIds = getFavorites();
    const recentIds = getRecents();

    const favList = document.getElementById("favorites-list");
    const recList = document.getElementById("recents-list");

    const renderMiniCard = (u) => `
        <div class="mini-card" onclick="selectUserForLookup(${u.ID}, '${u.RACF || u.Nome}')">
            <div class="mini-card-info">
                <span class="mini-card-name">${u.Nome}</span>
                <span class="mini-card-meta">RACF: ${u.RACF || "-"} | Host: ${u.Hostname || "-"}</span>
            </div>
            <button class="btn-favorite ${favIds.includes(u.ID) ? 'active' : ''}" onclick="event.stopPropagation(); toggleFavorite(${u.ID})" title="Favoritar">
                ${favIds.includes(u.ID) 
                    ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>'
                    : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>'}
            </button>
        </div>
    `;

    const favUsers = favIds.map(id => allUsers.find(u => u.ID === id)).filter(Boolean);
    const recUsers = recentIds.map(id => allUsers.find(u => u.ID === id)).filter(Boolean);

    favList.innerHTML = favUsers.length > 0 ? favUsers.map(renderMiniCard).join("") : '<div style="color:var(--text-muted); font-size: 0.85rem; padding: 8px;">Nenhum favorito salvo.</div>';
    recList.innerHTML = recUsers.length > 0 ? recUsers.map(renderMiniCard).join("") : '<div style="color:var(--text-muted); font-size: 0.85rem; padding: 8px;">Nenhuma busca recente.</div>';
}

// ─── PAGINAÇÃO ────────────────────────────────────────────────
const USERS_PER_PAGE = 15;
let currentPage = 1;
let allUsersCache = [];

function renderPagination(totalUsers) {
    const totalPages = Math.ceil(totalUsers / USERS_PER_PAGE);
    const container = document.getElementById("pagination-controls");
    if (!container) return;

    if (totalPages <= 1) {
        container.innerHTML = "";
        return;
    }

    let html = '<div class="pagination">';

    // Botão Anterior
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
        // Sempre mostra a primeira página
        html += `<button class="btn-page ${1 === currentPage ? 'active' : ''}" onclick="goToPage(1)">1</button>`;
        
        // Determina o intervalo de páginas do meio
        let start = Math.max(2, currentPage - 1);
        let end = Math.min(totalPages - 1, currentPage + 1);
        
        if (currentPage <= 3) {
            end = 4;
        } else if (currentPage >= totalPages - 2) {
            start = totalPages - 3;
        }
        
        // Mostra reticências antes se necessário
        if (start > 2) {
            html += '<span class="page-dots">...</span>';
        }
        
        // Mostra as páginas do meio
        for (let i = start; i <= end; i++) {
            html += `<button class="btn-page ${i === currentPage ? 'active' : ''}" onclick="goToPage(${i})">${i}</button>`;
        }
        
        // Mostra reticências depois se necessário
        if (end < totalPages - 1) {
            html += '<span class="page-dots">...</span>';
        }
        
        // Sempre mostra a última página
        html += `<button class="btn-page ${totalPages === currentPage ? 'active' : ''}" onclick="goToPage(${totalPages})">${totalPages}</button>`;
    }

    // Botão Próximo
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

    const tbody = document.getElementById("users-table-body");
    tbody.innerHTML = pageUsers.map((u) => `
        <tr>
            <td><span class="mono">${u.RACF || "—"}</span></td>
            <td><span class="mono">${u.Funcional || "—"}</span></td>
            <td>${u.Nome || "—"}</td>
            <td><span class="mono">${u.Serial || "—"}</span></td>
            <td><span class="mono">${u.Hostname || "—"}</span></td>
            <td><span class="mono">${u.IP || "—"}</span></td>
            <td><span class="badge badge-${(u.Status || "ativo").toLowerCase()}"><span class="badge-dot"></span>${u.Status || "Ativo"}</span></td>
            <td>
                <div class="action-buttons">
                    <button class="btn-icon" title="Editar" onclick="editUser(${u.ID})">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                    </button>
                    <button class="btn-icon delete" title="Excluir" onclick="openModal(${u.ID})">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="3 6 5 6 21 6"/>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                        </svg>
                    </button>
                </div>
            </td>
        </tr>
    `).join("");

    renderPagination(allUsersCache.length);
}

// ─── LISTAR USUÁRIOS ───────────────────────────────────────────
async function loadUsers(query = "") {
    try {
        const url = query ? `/usuarios?busca=${encodeURIComponent(query)}` : "/usuarios";
        const res = await fetch(url);
        const users = await res.json();

        allUsersCache = users;
        currentPage = 1;

        const tbody = document.getElementById("users-table-body");
        if (users.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="empty-state">Nenhum usuário encontrado.</td></tr>';
            const pag = document.getElementById("pagination-controls");
            if (pag) pag.innerHTML = "";
            return;
        }

        renderUsersPage();
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
    const payload = {
        RACF: document.getElementById("racf").value.trim(),
        Funcional: document.getElementById("funcional").value.trim(),
        Nome: document.getElementById("nome").value.trim(),
        Email: document.getElementById("email").value.trim(),
        Serial: document.getElementById("serial").value.trim(),
        Hostname: document.getElementById("hostname").value.trim(),
        IP: document.getElementById("ip").value.trim(),
        Status: document.getElementById("status").value,
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
            showToast(data.mensagem, "success");
            document.getElementById("user-form").reset();
            document.getElementById("ping-result").style.display = "none";
            cancelEdit();
        } else {
            showToast(data.erro, "error");
        }
    } catch {
        showToast("Erro de conexão com o servidor.", "error");
    }
});

async function editUser(userId) {
    try {
        const res = await fetch(`/usuarios/${userId}`);
        const user = await res.json();

        if (!res.ok) {
            showToast(user.erro, "error");
            return;
        }

        switchView("cadastrar");

        document.getElementById("edit-id").value = user.ID;
        document.getElementById("racf").value = user.RACF || "";
        document.getElementById("funcional").value = user.Funcional || "";
        document.getElementById("nome").value = user.Nome || "";
        document.getElementById("email").value = user.Email || "";
        document.getElementById("serial").value = user.Serial || "";
        document.getElementById("hostname").value = user.Hostname || "";
        document.getElementById("ip").value = user.IP || "";
        document.getElementById("status").value = user.Status || "Ativo";

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
    document.getElementById("ping-result").style.display = "none";
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
            // Restaura o estado original do dashboard
            const dashWidgets = document.getElementById("dash-widgets");
            if (dashWidgets) dashWidgets.style.display = "grid";
            document.getElementById("lookup-results").style.display = "none";
            document.getElementById("lookup-empty").style.display = "none";
        }
    }, 300);
});

// Fecha o dropdown se clicar fora dele ou do input
document.addEventListener("click", (e) => {
    const dropdown = document.getElementById("lookup-dropdown");
    const input = document.getElementById("lookup-input");
    if (dropdown && !dropdown.contains(e.target) && e.target !== input) {
        closeLookupDropdown();
    }
});

async function lookupUserSuggestions(query) {
    const dropdown = document.getElementById("lookup-dropdown");
    if (!dropdown) return;
    
    try {
        const res = await fetch(`/usuarios?busca=${encodeURIComponent(query)}`);
        const users = await res.json();
        
        if (users.length === 0) {
            dropdown.innerHTML = '<div style="padding: 12px 16px; color: var(--text-muted); font-size: 0.85rem; text-align: center;">Nenhum colaborador encontrado</div>';
            dropdown.style.display = "block";
            return;
        }
        
        dropdown.innerHTML = users.map((u) => `
            <div class="lookup-dropdown-item" onclick="selectUserForLookup(${u.ID}, '${u.RACF || u.Nome}'); closeLookupDropdown();">
                <span class="lookup-dropdown-name">${u.Nome}</span>
                <span class="lookup-dropdown-meta">RACF: ${u.RACF || "-"} | Host: ${u.Hostname || "-"}</span>
            </div>
        `).join("");
        dropdown.style.display = "block";
        
    } catch {
        dropdown.innerHTML = '<div style="padding: 12px 16px; color: var(--red); font-size: 0.85rem; text-align: center;">Erro ao carregar sugestões</div>';
        dropdown.style.display = "block";
    }
}

function closeLookupDropdown() {
    const dropdown = document.getElementById("lookup-dropdown");
    if (dropdown) {
        dropdown.style.display = "none";
    }
}

async function selectUserForLookup(userId, userDisplayValue) {
    const input = document.getElementById('lookup-input');
    input.value = userDisplayValue;
    
    const dashWidgets = document.getElementById("dash-widgets");
    if (dashWidgets) dashWidgets.style.display = "none";
    
    const resultsDiv = document.getElementById("lookup-results");
    const emptyDiv = document.getElementById("lookup-empty");
    resultsDiv.style.display = "block";
    emptyDiv.style.display = "none";
    resultsDiv.innerHTML = `<div style="text-align: center; padding: 20px;"><span class="spinner"></span> Carregando colaborador...</div>`;
    
    try {
        const res = await fetch(`/usuarios/${userId}`);
        const user = await res.json();
        
        if (!res.ok) {
            resultsDiv.style.display = "none";
            emptyDiv.style.display = "block";
            emptyDiv.textContent = user.erro || "Colaborador não encontrado.";
            return;
        }
        
        addRecent(user.ID);
        
        const favs = getFavorites();
        resultsDiv.innerHTML = `
            <div class="lookup-card" id="lookup-card-${user.ID}">
                <div class="lookup-card-header">
                    <div class="lookup-card-title-row">
                        <div style="display:flex; align-items:center; gap:16px;">
                            <div class="lookup-avatar">${user.Nome.charAt(0).toUpperCase()}</div>
                            <div class="lookup-info">
                                <span class="lookup-name">${user.Nome}</span>
                                <span class="lookup-meta">RACF: <strong>${user.RACF || "-"}</strong> &nbsp;|&nbsp; Funcional: <strong>${user.Funcional || "-"}</strong></span>
                            </div>
                        </div>
                        <div style="display:flex; gap:8px; align-items:center;">
                            <button class="btn-icon" title="Editar Colaborador" onclick="editUser(${user.ID})" style="background:transparent; border-color:var(--border); width:32px; height:32px;">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                                </svg>
                            </button>
                            <button id="fav-btn-${user.ID}" class="btn-favorite ${favs.includes(user.ID) ? 'active' : ''}" onclick="toggleFavorite(${user.ID})" title="Favoritar">
                                ${favs.includes(user.ID) 
                                    ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>'
                                    : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>'}
                            </button>
                        </div>
                    </div>
                    <span class="badge badge-${(user.Status || 'ativo').toLowerCase()}"><span class="badge-dot"></span>${user.Status || 'Ativo'}</span>
                </div>
                <div class="lookup-card-body">
                    <div class="lookup-field">
                        <span class="lookup-label">Serial</span>
                        <span class="lookup-value mono">${user.Serial || '—'}</span>
                    </div>
                    <div class="lookup-field">
                        <span class="lookup-label">Hostname</span>
                        <span class="lookup-value mono">${user.Hostname || '—'}</span>
                    </div>
                    <div class="lookup-field">
                        <span class="lookup-label">IP Cadastrado</span>
                        <span class="lookup-value mono">${user.IP || '—'}</span>
                    </div>
                    <div class="lookup-field">
                        <span class="lookup-label">IP Atual</span>
                        <span class="lookup-value mono lookup-live-ip" id="live-ip-${user.ID}">
                            <span class="spinner"></span> Verificando...
                        </span>
                    </div>
                    <div class="lookup-field">
                        <span class="lookup-label">Status da Máquina</span>
                        <span class="lookup-value" id="live-status-${user.ID}">
                            <span class="spinner"></span> Verificando...
                        </span>
                    </div>
                </div>
                <div class="lookup-card-actions" style="padding: 16px 20px; border-top: 1px solid var(--border); display: flex; gap: 12px; background: rgba(255, 255, 255, 0.01);">
                    <button class="btn btn-danger" onclick="confirmShutdown(${user.ID}, '${user.Nome}')" style="padding: 8px 16px; font-size: 0.8rem;">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-top:-2px;">
                            <path d="M18.36 6.64a9 9 0 1 1-12.73 0"></path>
                            <line x1="12" y1="2" x2="12" y2="12"></line>
                        </svg>
                        Desligar Máquina
                    </button>
                    <button class="btn btn-secondary" onclick="confirmRestart(${user.ID}, '${user.Nome}')" style="padding: 8px 16px; font-size: 0.8rem; border-color: var(--warning); color: var(--warning); background: transparent;">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-top:-2px;">
                            <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"></path>
                        </svg>
                        Reiniciar Máquina
                    </button>
                </div>
            </div>
        `;
        
        if (user.Hostname && user.Hostname !== "") {
            autoPing(user.ID, user.Hostname);
        } else {
            const ipEl = document.getElementById(`live-ip-${user.ID}`);
            const statusEl = document.getElementById(`live-status-${user.ID}`);
            if (ipEl) ipEl.textContent = "Sem hostname";
            if (statusEl) statusEl.innerHTML = '<span style="color:var(--text-muted)">Sem hostname cadastrado</span>';
        }
        
        loadDashboard();
        
    } catch {
        resultsDiv.style.display = "none";
        emptyDiv.style.display = "block";
        emptyDiv.textContent = "Erro ao carregar colaborador.";
    }
}

async function autoPing(userId, hostname) {
    const ipEl = document.getElementById(`live-ip-${userId}`);
    const statusEl = document.getElementById(`live-status-${userId}`);

    try {
        const res = await fetch(`/ping/${encodeURIComponent(hostname)}`);
        const data = await res.json();

        if (res.ok) {
            if (ipEl) {
                ipEl.innerHTML = `${data.ip} <button type="button" class="btn-copy" onclick="copyToClipboard('${data.ip}')" title="Copiar IP"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg></button>`;
            }
            if (statusEl) {
                statusEl.innerHTML = data.online
                    ? '<span class="ping-dot dot-online"></span> <span style="color:var(--green)">Online</span>'
                    : '<span class="ping-dot dot-offline"></span> <span style="color:var(--red)">Offline</span>';
            }
        } else {
            if (ipEl) ipEl.textContent = "Não resolvido";
            if (statusEl) statusEl.innerHTML = '<span class="ping-dot dot-offline"></span> <span style="color:var(--red)">Não acessível</span>';
        }
    } catch {
        if (ipEl) ipEl.textContent = "Erro";
        if (statusEl) statusEl.innerHTML = '<span style="color:var(--red)">Erro na conexão</span>';
    }
}

// ─── AÇÕES REMOTAS (DESLIGAR / REINICIAR) ──────────────────────
function getActionTarget(userId) {
    const card = document.getElementById(`lookup-card-${userId}`);
    if (!card) return null;
    
    const fields = card.querySelectorAll('.lookup-field');
    
    // 1. Prioridade máxima: Hostname (necessário para Kerberos / Active Directory no comando shutdown)
    for (let field of fields) {
        const label = field.querySelector('.lookup-label');
        const value = field.querySelector('.lookup-value');
        if (label && value) {
            const labelText = label.textContent.toLowerCase();
            if (labelText.includes("hostname")) {
                const valText = value.textContent.trim();
                if (valText && valText !== "—" && valText !== "") {
                    return valText;
                }
            }
        }
    }
    
    // 2. Fallback 1: IP Atual resolvido ao vivo
    const liveIpEl = document.getElementById(`live-ip-${userId}`);
    if (liveIpEl) {
        const match = liveIpEl.innerText.match(/(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/);
        if (match && match[1]) {
            return match[1];
        }
    }
    
    // 3. Fallback 2: IP Cadastrado
    for (let field of fields) {
        const label = field.querySelector('.lookup-label');
        const value = field.querySelector('.lookup-value');
        if (label && value) {
            const labelText = label.textContent.toLowerCase();
            if (labelText.includes("ip cadastrado") || labelText.includes("ip")) {
                const valText = value.textContent.replace(/[^0-9\.]/g, '').trim();
                if (valText && valText !== "—" && valText !== "") {
                    return valText;
                }
            }
        }
    }
    
    return null;
}

function confirmShutdown(userId, name) {
    const target = getActionTarget(userId);
    if (!target) {
        showToast("Nenhum IP ou Hostname disponível para enviar o comando.", "error");
        return;
    }
    openConfirmModal(
        "Confirmar Desligamento",
        `Tem certeza que deseja DESLIGAR a máquina de ${name}? (Alvo: ${target})`,
        "Desligar Máquina",
        "btn-danger",
        async () => {
            showToast("Enviando comando de desligamento...", "success");
            try {
                const res = await fetch(`/usuarios/desligar/${encodeURIComponent(target)}`, { method: "POST" });
                const data = await res.json();
                if (res.ok) {
                    showToast(data.mensagem, "success");
                } else {
                    showToast(data.erro || "Erro ao desligar a máquina.", "error");
                }
            } catch {
                showToast("Erro de conexão com o servidor.", "error");
            }
        }
    );
}

function confirmRestart(userId, name) {
    const target = getActionTarget(userId);
    if (!target) {
        showToast("Nenhum IP ou Hostname disponível para enviar o comando.", "error");
        return;
    }
    openConfirmModal(
        "Confirmar Reinicialização",
        `Tem certeza que deseja REINICIAR a máquina de ${name}? (Alvo: ${target})`,
        "Reiniciar Máquina",
        "btn-primary",
        async () => {
            showToast("Enviando comando de reinicialização...", "success");
            try {
                const res = await fetch(`/usuarios/reiniciar/${encodeURIComponent(target)}`, { method: "POST" });
                const data = await res.json();
                if (res.ok) {
                    showToast(data.mensagem, "success");
                } else {
                    showToast(data.erro || "Erro ao reiniciar a máquina.", "error");
                }
            } catch {
                showToast("Erro de conexão com o servidor.", "error");
            }
        }
    );
}

// ─── INICIALIZAÇÃO ─────────────────────────────────────────────
initTheme();
loadDashboard();
