import os
import logging
import uuid
import tempfile
import threading
import atexit
import time

logger = logging.getLogger(__name__)
import subprocess
import re
import sqlite3
from flask import Flask, request, jsonify, send_from_directory, make_response
from contextlib import closing
from datetime import datetime

app = Flask(__name__, static_folder="static")

# Diretório de modelos RDP seguro (Whitelist)
TEMPLATE_DIR = os.path.abspath(r"C:\Users\Desktop\Documents\antigravity\Auto ping\rdp_templates")

# Registro global de arquivos temporários RDP para limpeza em caso de reinicialização do Flask
active_temp_files = set()

def register_temp_file(filepath):
    active_temp_files.add(filepath)

def unregister_temp_file(filepath):
    active_temp_files.discard(filepath)

@atexit.register
def cleanup_leftover_files():
    for filepath in list(active_temp_files):
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass

def get_safe_template_path(path_input):
    if not path_input:
        return None
    # Restringir o caminho ao diretório whitelist para evitar path traversal
    filename = os.path.basename(path_input)
    resolved = os.path.abspath(os.path.join(TEMPLATE_DIR, filename))
    if resolved.startswith(TEMPLATE_DIR) and resolved.endswith('.rdp') and os.path.exists(resolved):
        return resolved
    return None

def encrypt_rdp_password(password):
    try:
        import win32crypt
        import binascii
        pw_bytes = (password + "\0").encode("utf-16-le")
        encrypted_bytes = win32crypt.CryptProtectData(pw_bytes, None, None, None, None, 0)
        return binascii.hexlify(encrypted_bytes).decode("utf-8")
    except Exception as e:
        logger.error(f"Erro ao criptografar senha com DPAPI: {e}")
        return None

def is_windows():
    return os.name == 'nt'

@app.after_request
def add_header(response):
    if request.path.startswith('/static/'):
        response.cache_control.max_age = 86400
        response.cache_control.public = True
    return response

DB_FILE = "usuarios.db"
EXCEL_FILE = "usuarios.xlsx"

def get_db():
    conn = sqlite3.connect(DB_FILE, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn

def init_db():
    with closing(get_db()) as conn:
        with conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS colaboradores (
                    ID INTEGER PRIMARY KEY AUTOINCREMENT,
                    RACF TEXT NOT NULL,
                    Funcional TEXT NOT NULL,
                    Nome TEXT NOT NULL,
                    Email TEXT,
                    Status TEXT DEFAULT 'Ativo'
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS maquinas (
                    ID INTEGER PRIMARY KEY AUTOINCREMENT,
                    Usuario_ID INTEGER NOT NULL,
                    Tipo TEXT DEFAULT 'Notebook',
                    Hostname TEXT NOT NULL,
                    IP TEXT,
                    Serial TEXT,
                    FOREIGN KEY(Usuario_ID) REFERENCES colaboradores(ID) ON DELETE CASCADE
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_colab_racf ON colaboradores(RACF)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_colab_func ON colaboradores(Funcional)')
            conn.execute("CREATE INDEX IF NOT EXISTS idx_colab_email ON colaboradores(Email) WHERE Email != ''")
            conn.execute('CREATE INDEX IF NOT EXISTS idx_maq_host ON maquinas(Hostname)')
            conn.execute("CREATE INDEX IF NOT EXISTS idx_maq_serial ON maquinas(Serial) WHERE Serial != ''")
            conn.execute('CREATE INDEX IF NOT EXISTS idx_maq_usu ON maquinas(Usuario_ID)')
            
            # Tabelas da integração do Intune
            conn.execute('''
                CREATE TABLE IF NOT EXISTS intune_cache (
                    ID INTEGER PRIMARY KEY AUTOINCREMENT,
                    Email TEXT NOT NULL,
                    Hostname TEXT NOT NULL,
                    Serial TEXT,
                    Modelo TEXT,
                    IP TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS configuracoes (
                    Chave TEXT PRIMARY KEY,
                    Valor TEXT
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_intune_email ON intune_cache(Email)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_intune_host ON intune_cache(Hostname)')

def migrate_excel_to_sqlite():
    try:
        import pandas as pd
    except ImportError:
        return
    if not os.path.exists(EXCEL_FILE):
        return

    try:
        xls = pd.ExcelFile(EXCEL_FILE)
    except Exception:
        return
        
    if "Colaboradores" not in xls.sheet_names or "Maquinas" not in xls.sheet_names:
        return

    df_users = pd.read_excel(xls, sheet_name="Colaboradores")
    df_machines = pd.read_excel(xls, sheet_name="Maquinas")

    with closing(get_db()) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM colaboradores")
        if cursor.fetchone()[0] > 0:
            return

        with conn:
            for _, row in df_users.iterrows():
                if pd.isna(row.get("Nome")): continue
                cursor.execute('''
                    INSERT OR IGNORE INTO colaboradores (ID, RACF, Funcional, Nome, Email, Status)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    int(row["ID"]) if pd.notna(row.get("ID")) else None,
                    str(int(row["RACF"])) if isinstance(row.get("RACF"), float) and row["RACF"].is_integer() else str(row.get("RACF", "")),
                    str(int(row["Funcional"])) if isinstance(row.get("Funcional"), float) and row["Funcional"].is_integer() else str(row.get("Funcional", "")),
                    str(row.get("Nome", "")),
                    str(row.get("Email", "")),
                    str(row.get("Status", "Ativo"))
                ))

            for _, row in df_machines.iterrows():
                if pd.isna(row.get("Hostname")): continue
                cursor.execute('''
                    INSERT OR IGNORE INTO maquinas (ID, Usuario_ID, Tipo, Hostname, IP, Serial)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    int(row["ID"]) if pd.notna(row.get("ID")) else None,
                    int(row["Usuario_ID"]) if pd.notna(row.get("Usuario_ID")) else 0,
                    str(row.get("Tipo", "Notebook")),
                    str(row.get("Hostname", "")),
                    str(row.get("IP", "")),
                    str(int(row["Serial"])) if isinstance(row.get("Serial"), float) and row["Serial"].is_integer() else str(row.get("Serial", ""))
                ))
            
    try:
        os.rename(EXCEL_FILE, EXCEL_FILE + ".migrated.bak")
    except Exception:
        pass


def is_valid_ip(ip_str):
    parts = ip_str.split('.')
    if len(parts) != 4:
        return False
    for p in parts:
        try:
            if not 0 <= int(p) <= 255:
                return False
        except ValueError:
            return False
    return True


@app.route("/")
def index():
    response = make_response(send_from_directory("static", "index.html"))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route("/test")
def test_route():
    return "OK"


@app.route("/cadastrar", methods=["POST"])
def cadastrar():
    try:
        dados = request.get_json()
        if not dados:
            return jsonify({"erro": "Requisição inválida. O corpo da mensagem deve ser um JSON."}), 400

        for campo in ["RACF", "Funcional", "Nome"]:
            if not str(dados.get(campo, "")).strip():
                return jsonify({"erro": f"O campo '{campo}' é obrigatório."}), 400

        racf_req = str(dados["RACF"]).strip().upper()
        func_req = str(dados["Funcional"]).strip()
        email_req = str(dados["Email"]).strip().lower()

        if len(racf_req) > 7:
            return jsonify({"erro": "O campo RACF deve ter no máximo 7 caracteres."}), 400

        if not re.match(r'^\d{1,9}$', func_req):
            return jsonify({"erro": "O campo Funcional deve conter apenas números (máx. 9 dígitos)."}), 400

        if email_req and not re.match(r'^[\w\.\-]+@[\w\.\-]+\.[a-zA-Z]{2,6}$', email_req):
            return jsonify({"erro": "E-mail inválido."}), 400

        with closing(get_db()) as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT ID FROM colaboradores WHERE RACF=?", (racf_req,))
            if cursor.fetchone(): return jsonify({"erro": "Já existe um usuário cadastrado com este RACF."}), 409
            cursor.execute("SELECT ID FROM colaboradores WHERE Funcional=?", (func_req,))
            if cursor.fetchone(): return jsonify({"erro": "Já existe um usuário cadastrado com esta Funcional."}), 409
            if email_req:
                cursor.execute("SELECT ID FROM colaboradores WHERE Email=?", (email_req,))
                if cursor.fetchone(): return jsonify({"erro": "Já existe um usuário cadastrado com este E-mail."}), 409

            maquinas_req = dados.get("maquinas", [])
            novas_maquinas = []
            hostnames_lote = set()
            seriais_lote = set()

            for idx, maq in enumerate(maquinas_req):
                if not isinstance(maq, dict): continue
                h_name = str(maq.get("Hostname", "")).strip().upper()
                serial = str(maq.get("Serial", "")).strip()
                tipo = str(maq.get("Tipo", "Notebook")).strip()
                ip = str(maq.get("IP", "")).strip()

                if not h_name:
                    return jsonify({"erro": f"O campo Hostname da máquina #{idx + 1} é obrigatório."}), 400
                if not re.match(r'^[a-zA-Z0-9\-\._]+$', h_name):
                    return jsonify({"erro": f"Hostname '{h_name}' inválido."}), 400
                if ip and not is_valid_ip(ip):
                    return jsonify({"erro": f"O IP '{ip}' da máquina #{idx + 1} é inválido."}), 400

                if h_name in hostnames_lote: return jsonify({"erro": f"O hostname '{h_name}' foi informado mais de uma vez."}), 400
                hostnames_lote.add(h_name)

                if serial:
                    if serial in seriais_lote: return jsonify({"erro": f"O número de serial '{serial}' foi informado mais de uma vez."}), 400
                    seriais_lote.add(serial)

                cursor.execute("SELECT ID FROM maquinas WHERE Hostname=?", (h_name,))
                if cursor.fetchone(): return jsonify({"erro": f"O hostname '{h_name}' já está cadastrado para outro colaborador."}), 409
                if serial:
                    cursor.execute("SELECT ID FROM maquinas WHERE Serial=?", (serial,))
                    if cursor.fetchone(): return jsonify({"erro": f"O número de serial '{serial}' já está cadastrado para outro colaborador."}), 409

                novas_maquinas.append((tipo, h_name, ip, serial))

            with conn:
                cursor.execute('''
                    INSERT INTO colaboradores (RACF, Funcional, Nome, Email, Status)
                    VALUES (?, ?, ?, ?, ?)
                ''', (racf_req, func_req, dados["Nome"].strip(), email_req, dados.get("Status", "Ativo")))
                user_id = cursor.lastrowid

                for maq in novas_maquinas:
                    cursor.execute('''
                        INSERT INTO maquinas (Usuario_ID, Tipo, Hostname, IP, Serial)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (user_id, maq[0], maq[1], maq[2], maq[3]))

            # Format return payload
            novo_usuario = {
                "ID": user_id, "RACF": racf_req, "Funcional": func_req, 
                "Nome": dados["Nome"].strip(), "Email": email_req, "Status": dados.get("Status", "Ativo")
            }
            maqs = conn.execute("SELECT * FROM maquinas WHERE Usuario_ID=?", (user_id,)).fetchall()
            novo_usuario["maquinas"] = [dict(m) for m in maqs]

        return jsonify({"mensagem": "Usuário cadastrado com sucesso!", "usuario": novo_usuario}), 201

    except Exception as e:
        logger.exception("Erro interno:")
        return jsonify({"erro": "Erro interno do servidor."}), 500


@app.route("/usuarios", methods=["GET"])
def listar():
    busca = request.args.get("busca", "").strip().lower()
    with closing(get_db()) as conn:
        rows = conn.execute('''
            SELECT c.*, 
                   m.ID as m_ID, m.Tipo, m.Hostname, m.IP, m.Serial 
            FROM colaboradores c
            LEFT JOIN maquinas m ON c.ID = m.Usuario_ID
            ORDER BY c.ID
        ''').fetchall()

        usuarios_map = {}
        for row in rows:
            uid = row["ID"]
            if uid not in usuarios_map:
                usuarios_map[uid] = {
                    "ID": uid, "RACF": row["RACF"], "Funcional": row["Funcional"],
                    "Nome": row["Nome"], "Email": row["Email"], "Status": row["Status"],
                    "maquinas": []
                }
            if row["m_ID"]:
                usuarios_map[uid]["maquinas"].append({
                    "ID": row["m_ID"], "Tipo": row["Tipo"],
                    "Hostname": row["Hostname"], "IP": row["IP"], "Serial": row["Serial"]
                })
        usuarios_list = list(usuarios_map.values())

    if busca:
        filtrados = []
        for u in usuarios_list:
            match_colab = any(busca in str(u.get(k, "")).lower() for k in ["RACF", "Funcional", "Nome", "Email", "Status"])
            match_maq = any(busca in str(m.get(k, "")).lower() for m in u["maquinas"] for k in ["Hostname", "IP", "Serial", "Tipo"])
            if match_colab or match_maq:
                filtrados.append(u)
        usuarios_list = filtrados

    return jsonify(usuarios_list)


@app.route("/usuarios/<int:user_id>", methods=["GET"])
def buscar(user_id):
    with closing(get_db()) as conn:
        u = conn.execute("SELECT * FROM colaboradores WHERE ID=?", (user_id,)).fetchone()
        if not u:
            return jsonify({"erro": "Usuário não encontrado."}), 404
        user_dict = dict(u)
        maquinas = conn.execute("SELECT * FROM maquinas WHERE Usuario_ID=?", (user_id,)).fetchall()
        user_dict["maquinas"] = [dict(m) for m in maquinas]
    return jsonify(user_dict)


@app.route("/usuarios/<int:user_id>", methods=["PUT"])
def editar(user_id):
    try:
        dados = request.get_json()
        if not dados: return jsonify({"erro": "Requisição inválida. O corpo da mensagem deve ser um JSON."}), 400

        with closing(get_db()) as conn:
            cursor = conn.cursor()
            u = cursor.execute("SELECT ID FROM colaboradores WHERE ID=?", (user_id,)).fetchone()
            if not u: return jsonify({"erro": "Usuário não encontrado."}), 404

            for campo in ["RACF", "Funcional", "Nome"]:
                if campo in dados and not str(dados[campo]).strip():
                    return jsonify({"erro": f"O campo '{campo}' é obrigatório."}), 400

            racf_req = str(dados.get("RACF", "")).strip().upper() if "RACF" in dados else ""
            func_req = str(dados.get("Funcional", "")).strip() if "Funcional" in dados else ""
            email_req = str(dados.get("Email", "")).strip().lower() if "Email" in dados else ""

            if racf_req and len(racf_req) > 7: return jsonify({"erro": "O campo RACF deve ter no máximo 7 caracteres."}), 400
            if func_req and not re.match(r'^\d{1,9}$', func_req): return jsonify({"erro": "O campo Funcional deve conter apenas números (máx. 9 dígitos)."}), 400
            if email_req and not re.match(r'^[\w\.\-]+@[\w\.\-]+\.[a-zA-Z]{2,6}$', email_req): return jsonify({"erro": "E-mail inválido."}), 400

            if racf_req:
                if cursor.execute("SELECT ID FROM colaboradores WHERE RACF=? AND ID!=?", (racf_req, user_id)).fetchone(): return jsonify({"erro": "Já existe outro usuário cadastrado com este RACF."}), 409
            if func_req:
                if cursor.execute("SELECT ID FROM colaboradores WHERE Funcional=? AND ID!=?", (func_req, user_id)).fetchone(): return jsonify({"erro": "Já existe outro usuário cadastrado com esta Funcional."}), 409
            if email_req:
                if cursor.execute("SELECT ID FROM colaboradores WHERE Email=? AND ID!=?", (email_req, user_id)).fetchone(): return jsonify({"erro": "Já existe outro usuário cadastrado com este E-mail."}), 409

            if "maquinas" in dados:
                maquinas_req = dados["maquinas"]
                novas_maquinas = []
                hostnames_lote = set()
                seriais_lote = set()

                for idx_m, maq in enumerate(maquinas_req):
                    if not isinstance(maq, dict): continue
                    h_name = str(maq.get("Hostname", "")).strip().upper()
                    serial = str(maq.get("Serial", "")).strip()
                    tipo = str(maq.get("Tipo", "Notebook")).strip()
                    ip = str(maq.get("IP", "")).strip()

                    if not h_name: return jsonify({"erro": f"O campo Hostname da máquina #{idx_m + 1} é obrigatório."}), 400
                    if not re.match(r'^[a-zA-Z0-9\-\._]+$', h_name): return jsonify({"erro": f"Hostname '{h_name}' inválido."}), 400
                    if ip and not is_valid_ip(ip): return jsonify({"erro": f"O IP '{ip}' da máquina #{idx_m + 1} é inválido."}), 400

                    if h_name in hostnames_lote: return jsonify({"erro": f"O hostname '{h_name}' foi informado mais de uma vez."}), 400
                    hostnames_lote.add(h_name)

                    if serial:
                        if serial in seriais_lote: return jsonify({"erro": f"O número de serial '{serial}' foi informado mais de uma vez."}), 400
                        seriais_lote.add(serial)

                    if cursor.execute("SELECT ID FROM maquinas WHERE Hostname=? AND Usuario_ID!=?", (h_name, user_id)).fetchone():
                        return jsonify({"erro": f"O hostname '{h_name}' já está cadastrado para outro colaborador."}), 409
                    if serial:
                        if cursor.execute("SELECT ID FROM maquinas WHERE Serial=? AND Usuario_ID!=?", (serial, user_id)).fetchone():
                            return jsonify({"erro": f"O número de serial '{serial}' já está cadastrado para outro colaborador."}), 409

                    novas_maquinas.append((tipo, h_name, ip, serial))

            with conn:
                if "maquinas" in dados:
                    cursor.execute("DELETE FROM maquinas WHERE Usuario_ID=?", (user_id,))
                    for maq in novas_maquinas:
                        cursor.execute('''
                            INSERT INTO maquinas (Usuario_ID, Tipo, Hostname, IP, Serial)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (user_id, maq[0], maq[1], maq[2], maq[3]))

                campos_update = []
                vals_update = []
                for campo in ["RACF", "Funcional", "Nome", "Email", "Status"]:
                    if campo in dados:
                        valor = str(dados[campo]).strip()
                        if campo == "RACF" and valor: valor = valor.upper()
                        campos_update.append(f"{campo}=?")
                        vals_update.append(valor)
                
                if campos_update:
                    vals_update.append(user_id)
                    query = f"UPDATE colaboradores SET {', '.join(campos_update)} WHERE ID=?"
                    cursor.execute(query, tuple(vals_update))

            u = conn.execute("SELECT * FROM colaboradores WHERE ID=?", (user_id,)).fetchone()
            usuario_atualizado = dict(u)
            maquinas = conn.execute("SELECT * FROM maquinas WHERE Usuario_ID=?", (user_id,)).fetchall()
            usuario_atualizado["maquinas"] = [dict(m) for m in maquinas]

        return jsonify({"mensagem": "Usuário atualizado com sucesso!", "usuario": usuario_atualizado})
    except Exception as e:
        logger.exception("Erro interno:")
        return jsonify({"erro": "Erro interno do servidor."}), 500


@app.route("/usuarios/<int:user_id>", methods=["DELETE"])
def excluir(user_id):
    with closing(get_db()) as conn:
        cursor = conn.cursor()
        u = cursor.execute("SELECT ID FROM colaboradores WHERE ID=?", (user_id,)).fetchone()
        if not u: return jsonify({"erro": "Usuário não encontrado."}), 404
        with conn:
            cursor.execute("DELETE FROM colaboradores WHERE ID=?", (user_id,))
    return jsonify({"mensagem": "Usuário excluído com sucesso!"})


@app.route("/ping/<hostname>", methods=["GET"])
def ping_host(hostname):
    if not re.match(r'^[a-zA-Z0-9\-\._]+$', hostname):
        return jsonify({"erro": "Hostname inválido."}), 400

    try:
        result = subprocess.run(
            ["ping", "-4", "-n", "1", "-w", "3000", hostname],
            capture_output=True,
            text=True,
            timeout=10,
        )

        output = result.stdout
        ip = None
        bracket_match = re.search(r'\[(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\]', output)
        if bracket_match: ip = bracket_match.group(1)
        elif re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', hostname): ip = hostname
        else:
            for line in output.splitlines():
                line_lower = line.lower()
                if ("disparando" in line_lower or "pinging" in line_lower or "ping" in line_lower) and not ("resposta" in line_lower or "reply" in line_lower):
                    ipv4_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', line)
                    if ipv4_match:
                        ip = ipv4_match.group(1)
                        break
        if not ip:
            for line in output.splitlines():
                line_lower = line.lower()
                if "estatí" in line_lower or "estatisticas" in line_lower or "statistics" in line_lower or "estatist" in line_lower:
                    ipv4_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', line)
                    if ipv4_match:
                        ip = ipv4_match.group(1)
                        break
        if not ip:
            for line in output.splitlines():
                line_lower = line.lower()
                if any(x in line_lower for x in ["inacess", "unreach", "resposta de", "reply from", "perda", "lost"]): continue
                ipv4_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', line)
                if ipv4_match:
                    ip = ipv4_match.group(1)
                    break

        if ip:
            online = result.returncode == 0 and "ttl=" in output.lower()
            return jsonify({
                "hostname": hostname,
                "ip": ip,
                "online": online,
                "mensagem": f"{'Online' if online else 'Offline'} — IP: {ip}"
            })
        else:
            return jsonify({"erro": f"Não foi possível resolver o hostname '{hostname}'."}), 404

    except subprocess.TimeoutExpired:
        return jsonify({"erro": "Timeout ao tentar pingar a máquina."}), 408
    except Exception as e:
        logger.exception("Erro interno:")
        return jsonify({"erro": "Erro interno do servidor."}), 500


@app.route('/api/jump-action', methods=['POST'])
def jump_action():
    if not is_windows():
        return jsonify({"erro": "Esta ação é suportada apenas em servidores Windows."}), 400

    try:
        data = request.json
        rdp_path = get_safe_template_path(data.get('rdp_path'))
        jump_ip = data.get('jump_ip')
        jump_user = data.get('jump_user')
        jump_pass = data.get('jump_pass')
        command = data.get('command')
        target_ip = data.get('target_ip')

        if not target_ip:
            return jsonify({"erro": "IP alvo ausente."}), 400
        if not rdp_path and not jump_ip:
            return jsonify({"erro": "Forneça um modelo RDP válido ou o IP do Jump Server."}), 400

        # Input validation
        if jump_ip and not re.match(r'^[a-zA-Z0-9\-\.]+$', jump_ip):
            return jsonify({"erro": "IP do Jump Server inválido."}), 400
        if jump_user and not re.match(r'^[a-zA-Z0-9_\.\-\@]+$', jump_user):
            return jsonify({"erro": "Usuário do Jump Server inválido."}), 400
        if target_ip and not re.match(r'^[a-zA-Z0-9\-\.]+$', target_ip):
            return jsonify({"erro": "IP alvo inválido."}), 400

        temp_dir = tempfile.gettempdir()
        safe_target = re.sub(r'[^a-zA-Z0-9]', '_', target_ip)
        temp_rdp = os.path.join(temp_dir, f"autoping_jump_{safe_target}_{uuid.uuid4().hex}.rdp")

        rdp_content = []
        if rdp_path:
            try:
                with open(rdp_path, 'r', encoding='utf-8') as f:
                    rdp_content = f.readlines()
            except UnicodeDecodeError:
                with open(rdp_path, 'r', encoding='utf-16') as f:
                    rdp_content = f.readlines()
            # Clean overrides
            rdp_content = [line for line in rdp_content if not line.lower().startswith(('alternate shell:', 'password 51:'))]
            if not jump_ip:
                for line in rdp_content:
                    if line.lower().startswith('full address:s:'):
                        jump_ip = line.split(':s:')[1].strip()
        else:
            rdp_content = [
                f"full address:s:{jump_ip}\n",
                f"username:s:{jump_user}\n",
                "prompt for credentials:i:0\n"
            ]


        # Inject DPAPI encrypted password (no CredWrite required!)
        if jump_pass:
            hex_pw = encrypt_rdp_password(jump_pass)
            if hex_pw:
                rdp_content.append(f"password 51:b:{hex_pw}\n")
            else:
                return jsonify({"erro": "Falha ao criptografar senha do RDP."}), 500

        # Save secure temp file
        with open(temp_rdp, 'w', encoding='utf-16') as f:
            f.writelines(rdp_content)

        register_temp_file(temp_rdp)

        # Launch mstsc.exe
        DETACHED_PROCESS = 0x00000008
        subprocess.Popen(["mstsc.exe", temp_rdp], creationflags=DETACHED_PROCESS)

        # Async clean up
        def cleanup_thread():
            try:
                time.sleep(8)  # Allow mstsc plenty of time to read
            finally:
                for _ in range(5):
                    try:
                        if os.path.exists(temp_rdp):
                            os.remove(temp_rdp)
                            unregister_temp_file(temp_rdp)
                            break
                    except Exception as e:
                        logger.warning(f"Retrying temp file deletion: {e}")
                        time.sleep(2)

        threading.Thread(target=cleanup_thread, daemon=False).start() # Daemon=False to prevent killing on shutdown

        return jsonify({"mensagem": "Iniciando Área de Trabalho Remota com DPAPI seguro!"}), 200
    except Exception as e:
        logger.exception("Erro interno no jump-action:")
        return jsonify({"erro": "Erro interno do servidor."}), 500


@app.route('/api/open-rdp', methods=['POST'])
def open_rdp():
    if not is_windows():
        return jsonify({"erro": "Esta ação é suportada apenas em servidores Windows."}), 400

    data = request.json
    ip = data.get('ip')
    base_rdp = get_safe_template_path(data.get('base_rdp'))

    if not ip or not re.match(r'^[a-zA-Z0-9\-\.]+$', ip):
        return jsonify({"erro": "IP ou Hostname inválido."}), 400

    rdp_content_lines = []
    if base_rdp:
        try:
            with open(base_rdp, 'r', encoding='utf-8') as f:
                rdp_content_lines = f.readlines()
        except UnicodeDecodeError:
            with open(base_rdp, 'r', encoding='utf-16') as f:
                rdp_content_lines = f.readlines()

        rdp_content_lines = [line for line in rdp_content_lines if not line.lower().startswith('full address:s:')]

    rdp_content_lines.append(f"full address:s:{ip}\n")
    if not any(line.lower().startswith('prompt for credentials:') for line in rdp_content_lines):
        rdp_content_lines.append("prompt for credentials:i:1\n")

    temp_dir = tempfile.gettempdir()
    safe_target = re.sub(r'[^a-zA-Z0-9]', '_', ip)
    temp_rdp = os.path.join(temp_dir, f"autoping_direct_{safe_target}_{uuid.uuid4().hex}.rdp")

    with open(temp_rdp, 'w', encoding='utf-16') as f:
        f.writelines(rdp_content_lines)

    register_temp_file(temp_rdp)

    DETACHED_PROCESS = 0x00000008
    subprocess.Popen(["mstsc.exe", temp_rdp], creationflags=DETACHED_PROCESS)

    def cleanup_thread():
        try:
            time.sleep(8)
        finally:
            for _ in range(5):
                try:
                    if os.path.exists(temp_rdp):
                        os.remove(temp_rdp)
                        unregister_temp_file(temp_rdp)
                        break
                except Exception:
                    time.sleep(2)

    threading.Thread(target=cleanup_thread, daemon=False).start()

    return jsonify({"mensagem": "Conexão de Área de Trabalho Remota iniciada com sucesso!"}), 200


@app.route('/api/download-rdp/<ip>')
def download_rdp(ip):
    if not re.match(r'^[a-zA-Z0-9\-\.]+$', ip):
        return "IP ou Hostname inválido", 400
    
    base_rdp = get_safe_template_path(request.args.get('base_rdp', ''))
    rdp_content_lines = []
    
    if base_rdp:
        try:
            with open(base_rdp, 'r', encoding='utf-8') as f:
                rdp_content_lines = f.readlines()
        except UnicodeDecodeError:
            with open(base_rdp, 'r', encoding='utf-16') as f:
                rdp_content_lines = f.readlines()
                
        rdp_content_lines = [line for line in rdp_content_lines if not line.lower().startswith('full address:s:')]
    
    rdp_content_lines.append(f"full address:s:{ip}\n")
    
    if not any(line.lower().startswith('prompt for credentials:') for line in rdp_content_lines):
        rdp_content_lines.append("prompt for credentials:i:1\n")
        
    rdp_content = "".join(rdp_content_lines)
    
    response = make_response(rdp_content)
    response.headers["Content-Disposition"] = f"attachment; filename=Acesso_{ip}.rdp"
    response.headers["Content-type"] = "application/x-rdp"
    return response

@app.route("/api/intune/import", methods=["POST"])
def import_intune():
    try:
        import csv
        import io
        
        if 'file' not in request.files:
            return jsonify({"erro": "Nenhum arquivo enviado."}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({"erro": "Nome de arquivo inválido."}), 400
            
        limpar_base = request.form.get("limpar_base", "false").lower() == "true"
        
        # Read file contents
        content = file.stream.read()
        
        # Try to detect encoding
        decoded_content = None
        for encoding in ['utf-8-sig', 'utf-8', 'utf-16', 'latin-1']:
            try:
                decoded_content = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
                
        if decoded_content is None:
            return jsonify({"erro": "Não foi possível detectar a codificação do arquivo. Certifique-se de que é um CSV válido."}), 400
            
        # Determine delimiter (';' or ',')
        first_line = decoded_content.splitlines()[0] if decoded_content.splitlines() else ""
        delimiter = ';' if ';' in first_line else ','
        
        stream = io.StringIO(decoded_content)
        reader = csv.DictReader(stream, delimiter=delimiter)
        
        if not reader.fieldnames:
            return jsonify({"erro": "Arquivo CSV vazio ou sem cabeçalhos."}), 400
            
        # Normalize headers and map them
        headers = reader.fieldnames
        col_map = {}
        for h in headers:
            h_norm = h.strip().lower()
            if h_norm in ["device name", "nome do dispositivo", "hostname", "devicename"]:
                col_map["hostname"] = h
            elif h_norm in ["primary user upn", "user principal name", "upn do usuário primário", "upn", "email", "e-mail", "userprincipalname"]:
                col_map["email"] = h
            elif h_norm in ["primary user display name", "nome de exibição do usuário primário", "nome", "displayname", "user display name", "userdisplayname"]:
                col_map["nome"] = h
            elif h_norm in ["serial number", "número de série", "serial", "serialnumber"]:
                col_map["serial"] = h
            elif h_norm in ["device model", "modelo do dispositivo", "model", "devicemodel"]:
                col_map["model"] = h
            elif h_norm in ["manufacturer", "fabricante"]:
                col_map["manufacturer"] = h
            elif h_norm in ["ip address", "endereço ip", "ip", "ipv4 address", "ipaddress"]:
                col_map["ip"] = h

        if "hostname" not in col_map:
            return jsonify({"erro": "Coluna de Hostname/Nome do dispositivo não encontrada no CSV. As colunas reconhecidas são: 'Device name', 'Nome do dispositivo', 'Hostname' ou 'DeviceName'."}), 400

        colaboradores_importados = 0
        maquinas_importadas = 0
        erros_avisos = []
        
        with closing(get_db()) as conn:
            cursor = conn.cursor()
            
            with conn:
                if limpar_base:
                    cursor.execute("DELETE FROM colaboradores")
                    cursor.execute("DELETE FROM intune_cache")
                
                # Fetch existing collaborators and machines to map/update
                cursor.execute("SELECT ID, RACF, Funcional, Nome, Email FROM colaboradores")
                colab_cache = {row["RACF"]: dict(row) for row in cursor.fetchall()}
                
                cursor.execute("SELECT ID, Hostname FROM maquinas")
                maq_cache = {row["Hostname"]: row["ID"] for row in cursor.fetchall()}
                
                # Counter for generating dummy Functional IDs if needed
                cursor.execute("SELECT MAX(CAST(Funcional AS INTEGER)) FROM colaboradores WHERE Funcional LIKE '9%'")
                max_func = cursor.fetchone()[0]
                next_func = int(max_func) + 1 if max_func else 900000000
                
                for row_idx, row in enumerate(reader):
                    hostname = row.get(col_map["hostname"], "").strip().upper()
                    if not hostname:
                        continue
                    
                    # Validate hostname format
                    if not re.match(r'^[a-zA-Z0-9\-\._]+$', hostname):
                        erros_avisos.append(f"Linha {row_idx+2}: Hostname '{hostname}' contém caracteres inválidos e foi pulado.")
                        continue
                    
                    # Extract user UPN/Email
                    upn = ""
                    if "email" in col_map:
                        upn = row.get(col_map["email"], "").strip().lower()
                    
                    # Get or create collaborator
                    user_id = None
                    if not upn:
                        # Associa a um usuário genérico "Sem Usuário"
                        racf = "SEMUSER"
                        nome = "Sem Usuário"
                        email = ""
                    else:
                        # Extract RACF from UPN prefix
                        username = upn.split('@')[0]
                        # Normalize username: keep only alphanumeric characters, max 7 length
                        username_clean = re.sub(r'[^a-zA-Z0-9]', '', username)
                        racf = username_clean[:7].upper()
                        if not racf:
                            racf = "SEMUSER"
                            nome = "Sem Usuário"
                            email = ""
                        else:
                            nome = row.get(col_map.get("nome"), "").strip() if "nome" in col_map else ""
                            if not nome:
                                # Fallback: format name from username
                                nome = username.replace('.', ' ').title()
                            email = upn
                    
                    # Check if collaborator exists
                    if racf in colab_cache:
                        user_id = colab_cache[racf]["ID"]
                    else:
                        # Try to get functional number
                        # Extract digits from RACF if possible
                        digits = "".join([c for c in racf if c.isdigit()])
                        if digits and 1 <= len(digits) <= 9:
                            funcional = digits
                        else:
                            funcional = str(next_func)
                            next_func += 1
                            
                        # Double check if this functional is already used
                        cursor.execute("SELECT ID FROM colaboradores WHERE Funcional=?", (funcional,))
                        if cursor.fetchone():
                            # Generate unique
                            funcional = str(next_func)
                            next_func += 1
                            
                        cursor.execute('''
                            INSERT INTO colaboradores (RACF, Funcional, Nome, Email, Status)
                            VALUES (?, ?, ?, ?, 'Ativo')
                        ''', (racf, funcional, nome, email))
                        user_id = cursor.lastrowid
                        
                        # Cache it
                        colab_cache[racf] = {"ID": user_id, "RACF": racf, "Funcional": funcional, "Nome": nome, "Email": email}
                        colaboradores_importados += 1
                        
                    # Determine machine properties
                    serial = ""
                    if "serial" in col_map:
                        serial = row.get(col_map["serial"], "").strip()
                        
                    ip = ""
                    if "ip" in col_map:
                        ip_val = row.get(col_map["ip"], "").strip()
                        if is_valid_ip(ip_val):
                            ip = ip_val
                            
                    # Determine type
                    tipo = "Notebook"
                    model_val = ""
                    if "model" in col_map:
                        model_val += " " + row.get(col_map["model"], "").lower()
                    if "manufacturer" in col_map:
                        model_val += " " + row.get(col_map["manufacturer"], "").lower()
                        
                    if any(x in model_val for x in ["desktop", "tower", "prodesk", "pc", "workstation"]):
                        tipo = "Desktop"
                    elif any(x in model_val for x in ["mini", "micro", "nuc"]):
                        tipo = "Minidesk"
                        
                    # Insert into intune_cache for future lookup by email
                    cursor.execute('''
                        INSERT INTO intune_cache (Email, Hostname, Serial, Modelo, IP)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (upn, hostname, serial, model_val, ip))
                    
                    # Insert or update machine in primary tables
                    if hostname in maq_cache:
                        # Update machine
                        cursor.execute('''
                            UPDATE maquinas 
                            SET Usuario_ID=?, Tipo=?, IP=?, Serial=?
                            WHERE Hostname=?
                        ''', (user_id, tipo, ip, serial, hostname))
                    else:
                        # Insert machine
                        cursor.execute('''
                            INSERT INTO maquinas (Usuario_ID, Tipo, Hostname, IP, Serial)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (user_id, tipo, hostname, ip, serial))
                        maq_cache[hostname] = cursor.lastrowid
                        maquinas_importadas += 1
                        
        return jsonify({
            "mensagem": "Sincronização do Intune realizada com sucesso!",
            "colaboradores_importados": colaboradores_importados,
            "maquinas_importadas": maquinas_importadas,
            "erros": erros_avisos[:10]  # Return max 10 warnings
        }), 200
        
    except Exception as e:
        logger.exception("Erro na importação do Intune:")
        return jsonify({"erro": f"Erro interno: {str(e)}"}), 500

def get_valid_access_token():
    import urllib.request
    import urllib.parse
    import json
    with closing(get_db()) as conn:
        row_access = conn.execute("SELECT Valor FROM configuracoes WHERE Chave='intune_access_token'").fetchone()
        row_refresh = conn.execute("SELECT Valor FROM configuracoes WHERE Chave='intune_refresh_token'").fetchone()
        row_expires = conn.execute("SELECT Valor FROM configuracoes WHERE Chave='intune_token_expires'").fetchone()
        
        if not row_access or not row_refresh:
            return None
            
        access_token = row_access["Valor"]
        refresh_token = row_refresh["Valor"]
        expires_at = int(row_expires["Valor"]) if row_expires else 0
        
        if expires_at > int(datetime.now().timestamp()) + 300:
            return access_token
            
        try:
            url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
            client_id = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
            post_data = urllib.parse.urlencode({
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "scope": "offline_access User.Read DeviceManagementManagedDevices.Read.All"
            }).encode("utf-8")
            
            req = urllib.request.Request(url, data=post_data, method="POST")
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                
            new_access = res_data.get("access_token")
            new_refresh = res_data.get("refresh_token", refresh_token)
            expires_in = res_data.get("expires_in")
            
            with conn:
                conn.execute("INSERT OR REPLACE INTO configuracoes (Chave, Valor) VALUES ('intune_access_token', ?)", (new_access,))
                conn.execute("INSERT OR REPLACE INTO configuracoes (Chave, Valor) VALUES ('intune_refresh_token', ?)", (new_refresh,))
                conn.execute("INSERT OR REPLACE INTO configuracoes (Chave, Valor) VALUES ('intune_token_expires', ?)", (str(int(datetime.now().timestamp()) + expires_in),))
                
            return new_access
        except Exception as e:
            logger.error(f"Erro ao renovar token do Intune: {str(e)}")
            return None

@app.route("/api/intune/devicecode", methods=["POST"])
def get_devicecode():
    import urllib.request
    import urllib.parse
    import json

    url = "https://login.microsoftonline.com/common/oauth2/v2.0/devicecode"
    client_id = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"

    # Lista de escopos para tentar — do mais completo ao mínimo
    scope_sets = [
        "offline_access User.Read DeviceManagementManagedDevices.Read.All",
        "offline_access User.Read DeviceManagementManagedDevices.Read",
        "offline_access User.Read",
    ]

    last_error = None
    for scopes in scope_sets:
        try:
            post_data = urllib.parse.urlencode({
                "client_id": client_id,
                "scope": scopes
            }).encode("utf-8")

            req = urllib.request.Request(url, data=post_data, method="POST")
            req.add_header("Content-Type", "application/x-www-form-urlencoded")

            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode("utf-8"))

            logger.info(f"Device code obtido com scopes: {scopes}")
            return jsonify(res_data), 200

        except urllib.error.HTTPError as he:
            err_body = ""
            try:
                err_body = he.read().decode("utf-8")
                err_json = json.loads(err_body)
                last_error = err_json.get("error_description", err_body)
            except Exception:
                last_error = err_body or str(he)
            logger.warning(f"Device code falhou com scopes [{scopes}]: {last_error}")
            continue
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Device code falhou com scopes [{scopes}]: {last_error}")
            continue

    logger.error(f"Device code falhou com todos os conjuntos de scopes. Último erro: {last_error}")
    return jsonify({"erro": f"Não foi possível obter código de autenticação. Verifique se o Device Code Flow está habilitado no seu tenant Azure AD. Detalhe: {last_error}"}), 500

@app.route("/api/intune/token-check", methods=["POST"])
def check_token():
    import urllib.request
    import urllib.parse
    import json
    try:
        data_req = request.get_json()
        device_code = data_req.get("device_code")
        if not device_code:
            return jsonify({"erro": "device_code ausente."}), 400
            
        url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        client_id = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
        post_data = urllib.parse.urlencode({
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_code,
            "client_id": client_id
        }).encode("utf-8")
        
        req = urllib.request.Request(url, data=post_data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                
            access_token = res_data.get("access_token")
            refresh_token = res_data.get("refresh_token")
            expires_in = res_data.get("expires_in")
            
            with closing(get_db()) as conn:
                with conn:
                    conn.execute("INSERT OR REPLACE INTO configuracoes (Chave, Valor) VALUES ('intune_access_token', ?)", (access_token,))
                    conn.execute("INSERT OR REPLACE INTO configuracoes (Chave, Valor) VALUES ('intune_refresh_token', ?)", (refresh_token,))
                    conn.execute("INSERT OR REPLACE INTO configuracoes (Chave, Valor) VALUES ('intune_token_expires', ?)", (str(int(datetime.now().timestamp()) + expires_in),))
                    
            return jsonify({"status": "completed", "mensagem": "Autenticado com sucesso!"}), 200
        except urllib.error.HTTPError as he:
            try:
                err_data = json.loads(he.read().decode("utf-8"))
                err_code = err_data.get("error")
                if err_code == "authorization_pending":
                    return jsonify({"status": "pending", "mensagem": "Aguardando autenticação..."}), 200
                elif err_code == "authorization_declined":
                    return jsonify({"status": "declined", "erro": "Autenticação recusada."}), 400
                elif err_code == "expired_token":
                    return jsonify({"status": "expired", "erro": "Código expirado."}), 400
                else:
                    return jsonify({"status": "error", "erro": err_data.get("error_description", "Erro ao autenticar")}), 400
            except Exception:
                return jsonify({"status": "error", "erro": "Erro na requisição com o Azure AD."}), 400
    except Exception as e:
        logger.exception("Erro ao checar token no Azure AD:")
        return jsonify({"erro": f"Erro interno: {str(e)}"}), 500

@app.route("/api/intune/lookup-devices", methods=["GET"])
def lookup_devices():
    import urllib.request
    import json
    
    email = request.args.get("email", "").strip().lower()
    if not email:
        return jsonify({"erro": "O parâmetro e-mail é obrigatório."}), 400
        
    try:
        devices = []
        source = "cache"
        
        # 1. Try Live Graph API first if connected
        token = get_valid_access_token()
        if token:
            try:
                import urllib.parse
                safe_email = urllib.parse.quote(email)
                url = f"https://graph.microsoft.com/v1.0/deviceManagement/managedDevices?$filter=userPrincipalName%20eq%20'{safe_email}'"
                
                req = urllib.request.Request(url)
                req.add_header("Authorization", f"Bearer {token}")
                
                with urllib.request.urlopen(req) as response:
                    res_data = json.loads(response.read().decode("utf-8"))
                    
                graph_devices = res_data.get("value", [])
                for d in graph_devices:
                    hostname = d.get("deviceName", "").upper()
                    if hostname:
                        model = d.get("model", "")
                        manufacturer = d.get("manufacturer", "")
                        model_norm = (model + " " + manufacturer).lower()
                        
                        tipo = "Notebook"
                        if any(x in model_norm for x in ["desktop", "tower", "prodesk", "pc", "workstation"]):
                            tipo = "Desktop"
                        elif any(x in model_norm for x in ["mini", "micro", "nuc"]):
                            tipo = "Minidesk"
                            
                        devices.append({
                            "Hostname": hostname,
                            "Serial": d.get("serialNumber", "") or "",
                            "Tipo": tipo,
                            "IP": d.get("ipAddress", "") or ""
                        })
                source = "api"
            except Exception as graph_err:
                logger.error(f"Erro ao buscar dispositivos no Graph API: {str(graph_err)}")
                
        # 2. Fallback to local intune_cache
        if not devices:
            with closing(get_db()) as conn:
                rows = conn.execute(
                    "SELECT Hostname, Serial, Modelo, IP FROM intune_cache WHERE Email=?",
                    (email,)
                ).fetchall()
                
                for r in rows:
                    model_norm = str(r["Modelo"]).lower()
                    tipo = "Notebook"
                    if any(x in model_norm for x in ["desktop", "tower", "prodesk", "pc", "workstation"]):
                        tipo = "Desktop"
                    elif any(x in model_norm for x in ["mini", "micro", "nuc"]):
                        tipo = "Minidesk"
                        
                    devices.append({
                        "Hostname": r["Hostname"],
                        "Serial": r["Serial"] or "",
                        "Tipo": tipo,
                        "IP": r["IP"] or ""
                    })
                    
        return jsonify({
            "email": email,
            "source": source,
            "devices": devices
        }), 200
    except Exception as e:
        logger.exception("Erro no lookup de dispositivos do Intune:")
        return jsonify({"erro": f"Erro interno: {str(e)}"}), 500
@app.route("/api/intune/status", methods=["GET"])
def intune_status():
    token = get_valid_access_token()
    return jsonify({"connected": token is not None}), 200

@app.route("/api/intune/disconnect", methods=["POST"])
def intune_disconnect():
    with closing(get_db()) as conn:
        with conn:
            conn.execute("DELETE FROM configuracoes WHERE Chave IN ('intune_access_token', 'intune_refresh_token', 'intune_token_expires')")
    return jsonify({"mensagem": "Conta desconectada com sucesso!"}), 200

if __name__ == '__main__':
    init_db()
    migrate_excel_to_sqlite()
    app.run(debug=False, port=5000, threaded=True, host="0.0.0.0")
