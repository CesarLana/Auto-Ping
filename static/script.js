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
    localStorage.setItem("magicalBorg_theme", newTheme);
    
    const label = document.getElementById("theme-label");
    if (label) label.textContent = newTheme === "dark" ? "Modo Claro" : "Modo Escuro";
}

function initTheme() {
    const savedTheme = localStorage.getItem("magicalBorg_theme");
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
    return JSON.parse(localStorage.getItem('magicalBorg_favorites')) || [];
}

function getRecents() {
    return JSON.parse(localStorage.getItem('magicalBorg_recents')) || [];
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
    localStorage.setItem('magicalBorg_favorites', JSON.stringify(favs));
    
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
    localStorage.setItem('magicalBorg_recents', JSON.stringify(recents));
}

// ─── MODAL ─────────────────────────────────────────────────────
function openModal(userId) {
    deleteTargetId = userId;
    document.getElementById("modal-overlay").classList.add("show");
}

function closeModal() {
    deleteTargetId = null;
    document.getElementById("modal-overlay").classList.remove("show");
}

document.getElementById("btn-confirm-delete").addEventListener("click", async () => {
    if (deleteTargetId === null) return;
    try {
        const res = await fetch(`/usuarios/${deleteTargetId}`, { method: "DELETE" });
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
        <div class="mini-card" onclick="document.getElementById('lookup-input').value = '${u.RACF || u.Nome}'; document.getElementById('lookup-input').dispatchEvent(new Event('input'));">
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

// ─── LISTAR USUÁRIOS ───────────────────────────────────────────
async function loadUsers(query = "") {
    try {
        const url = query ? `/usuarios?busca=${encodeURIComponent(query)}` : "/usuarios";
        const res = await fetch(url);
        const users = await res.json();

        const tbody = document.getElementById("users-table-body");
        if (users.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="empty-state">Nenhum usuário encontrado.</td></tr>';
            return;
        }

        tbody.innerHTML = users.map((u) => `
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
        const dashWidgets = document.getElementById("dash-widgets");
        if (query.length > 0) {
            if (dashWidgets) dashWidgets.style.display = "none";
            lookupUser(query);
        } else {
            if (dashWidgets) dashWidgets.style.display = "grid";
            document.getElementById("lookup-results").style.display = "none";
            document.getElementById("lookup-empty").style.display = "none";
        }
    }, 400);
});

async function lookupUser(query) {
    const resultsDiv = document.getElementById("lookup-results");
    const emptyDiv = document.getElementById("lookup-empty");

    if (!query) {
        resultsDiv.style.display = "none";
        emptyDiv.style.display = "flex";
        return;
    }

    try {
        const res = await fetch(`/usuarios?busca=${encodeURIComponent(query)}`);
        const users = await res.json();

        if (users.length === 0) {
            resultsDiv.style.display = "none";
            emptyDiv.style.display = "block";
            emptyDiv.textContent = `Nenhum colaborador encontrado para "${query}".`;
            return;
        }

        emptyDiv.style.display = "none";
        resultsDiv.style.display = "block";

        // Se a busca for exata ou tiver resultado, salva nos recentes (apenas o primeiro da lista)
        if (users.length > 0) {
            addRecent(users[0].ID);
            loadDashboard(); // atualiza a lista de recentes
        }

        const favs = getFavorites();

        resultsDiv.innerHTML = users.map((u) => `
            <div class="lookup-card" id="lookup-card-${u.ID}">
                <div class="lookup-card-header">
                    <div class="lookup-card-title-row">
                        <div style="display:flex; align-items:center; gap:16px;">
                            <div class="lookup-avatar">${u.Nome.charAt(0).toUpperCase()}</div>
                            <div class="lookup-info">
                                <span class="lookup-name">${u.Nome}</span>
                                <span class="lookup-meta">RACF: <strong>${u.RACF || "-"}</strong> &nbsp;|&nbsp; Funcional: <strong>${u.Funcional || "-"}</strong></span>
                            </div>
                        </div>
                        <button id="fav-btn-${u.ID}" class="btn-favorite ${favs.includes(u.ID) ? 'active' : ''}" onclick="toggleFavorite(${u.ID})" title="Favoritar">
                            ${favs.includes(u.ID) 
                                ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>'
                                : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>'}
                        </button>
                    </div>
                    <span class="badge badge-${(u.Status || 'ativo').toLowerCase()}"><span class="badge-dot"></span>${u.Status || 'Ativo'}</span>
                </div>
                <div class="lookup-card-body">
                    <div class="lookup-field">
                        <span class="lookup-label">Serial</span>
                        <span class="lookup-value mono">${u.Serial || '—'}</span>
                    </div>
                    <div class="lookup-field">
                        <span class="lookup-label">Hostname</span>
                        <span class="lookup-value mono">${u.Hostname || '—'}</span>
                    </div>
                    <div class="lookup-field">
                        <span class="lookup-label">IP Cadastrado</span>
                        <span class="lookup-value mono">${u.IP || '—'}</span>
                    </div>
                    <div class="lookup-field">
                        <span class="lookup-label">IP Atual</span>
                        <span class="lookup-value mono lookup-live-ip" id="live-ip-${u.ID}">
                            <span class="spinner"></span> Verificando...
                        </span>
                    </div>
                    <div class="lookup-field">
                        <span class="lookup-label">Status da Máquina</span>
                        <span class="lookup-value" id="live-status-${u.ID}">
                            <span class="spinner"></span> Verificando...
                        </span>
                    </div>
                </div>
            </div>
        `).join("");

        // Auto-ping cada resultado que tem hostname
        users.forEach((u) => {
            if (u.Hostname && u.Hostname !== "") {
                autoPing(u.ID, u.Hostname);
            } else {
                const ipEl = document.getElementById(`live-ip-${u.ID}`);
                const statusEl = document.getElementById(`live-status-${u.ID}`);
                if (ipEl) ipEl.textContent = "Sem hostname";
                if (statusEl) statusEl.innerHTML = '<span style="color:var(--text-muted)">Sem hostname cadastrado</span>';
            }
        });

    } catch {
        showToast("Erro ao buscar colaborador.", "error");
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

// ─── INICIALIZAÇÃO ─────────────────────────────────────────────
initTheme();
loadDashboard();
