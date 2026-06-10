import os
import logging

logger = logging.getLogger(__name__)
import subprocess
import re
import sqlite3
from flask import Flask, request, jsonify, send_from_directory, make_response
from contextlib import closing
from datetime import datetime

app = Flask(__name__, static_folder="static")

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
    try:
        import tempfile
        import time
        import threading
        data = request.json
        rdp_path = data.get('rdp_path')
        jump_ip = data.get('jump_ip')
        jump_user = data.get('jump_user')
        jump_pass = data.get('jump_pass')
        command = data.get('command')
        target_ip = data.get('target_ip')

        if not command or not target_ip:
            return jsonify({"erro": "Comando ou IP alvo ausente."}), 400
        if not rdp_path and not jump_ip:
            return jsonify({"erro": "Forneça o caminho do .rdp ou o IP do Jump Server."}), 400

        if jump_ip and not re.match(r'^[a-zA-Z0-9\-\.]+$', jump_ip):
            return jsonify({"erro": "IP do Jump Server inválido."}), 400
        if jump_user and not re.match(r'^[a-zA-Z0-9_\.\-\@]+$', jump_user):
            return jsonify({"erro": "Usuário do Jump Server inválido."}), 400
        if target_ip and not re.match(r'^[a-zA-Z0-9\-\.]+$', target_ip):
            return jsonify({"erro": "IP alvo inválido."}), 400

        if rdp_path:
            if not os.path.exists(rdp_path) or not rdp_path.endswith('.rdp'):
                return jsonify({"erro": "Arquivo RDP inválido ou inexistente."}), 400

        temp_dir = tempfile.gettempdir()
        safe_target = re.sub(r'[^a-zA-Z0-9]', '_', target_ip)
        temp_rdp = os.path.join(temp_dir, f"autoping_jump_{safe_target}_{int(time.time())}.rdp")

        rdp_content = []
        if rdp_path and os.path.exists(rdp_path):
            try:
                with open(rdp_path, 'r', encoding='utf-8') as f:
                    rdp_content = f.readlines()
            except UnicodeDecodeError:
                with open(rdp_path, 'r', encoding='utf-16') as f:
                    rdp_content = f.readlines()
            rdp_content = [line for line in rdp_content if not line.lower().startswith('alternate shell:')]
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

        rdp_content.append('alternate shell:s:cmd.exe\n')

        with open(temp_rdp, 'w', encoding='utf-16') as f:
            f.writelines(rdp_content)

        target = None
        if jump_ip and jump_user and jump_pass:
            import win32cred
            target = f"TERMSRV/{jump_ip}"
            cred = {
                'TargetName': target, 'UserName': jump_user,
                'CredentialBlob': jump_pass,
                'Type': win32cred.CRED_TYPE_DOMAIN_PASSWORD, 'Persist': win32cred.CRED_PERSIST_SESSION
            }
            win32cred.CredWrite(cred, 0)

        DETACHED_PROCESS = 0x00000008
        subprocess.Popen(["mstsc.exe", temp_rdp], creationflags=DETACHED_PROCESS)

        def cleanup_thread():
            try:
                time.sleep(3)
                if target:
                    import win32cred
                    try: win32cred.CredDelete(target, win32cred.CRED_TYPE_DOMAIN_PASSWORD, 0)
                    except Exception: pass
            finally:
                for _ in range(5):
                    time.sleep(2)
                    try:
                        if os.path.exists(temp_rdp):
                            os.remove(temp_rdp)
                            break
                    except Exception:
                        pass

        threading.Thread(target=cleanup_thread, daemon=True).start()

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
    try:
        import tempfile
        import time
        import threading
        data = request.json
        rdp_path = data.get('rdp_path')
        jump_ip = data.get('jump_ip')
        jump_user = data.get('jump_user')
        jump_pass = data.get('jump_pass')
        command = data.get('command')
        target_ip = data.get('target_ip')

        if not command or not target_ip:
            return jsonify({"erro": "Comando ou IP alvo ausente."}), 400
        if not rdp_path and not jump_ip:
            return jsonify({"erro": "Forneça o caminho do .rdp ou o IP do Jump Server."}), 400

        if jump_ip and not re.match(r'^[a-zA-Z0-9\-\.]+$', jump_ip):
            return jsonify({"erro": "IP do Jump Server inválido."}), 400
        if jump_user and not re.match(r'^[a-zA-Z0-9_\.\-\@]+$', jump_user):
            return jsonify({"erro": "Usuário do Jump Server inválido."}), 400
        if target_ip and not re.match(r'^[a-zA-Z0-9\-\.]+$', target_ip):
            return jsonify({"erro": "IP alvo inválido."}), 400

        if rdp_path:
            if not os.path.exists(rdp_path) or not rdp_path.endswith('.rdp'):
                return jsonify({"erro": "Arquivo RDP inválido ou inexistente."}), 400

        temp_dir = tempfile.gettempdir()
        safe_target = re.sub(r'[^a-zA-Z0-9]', '_', target_ip)
        temp_rdp = os.path.join(temp_dir, f"autoping_jump_{safe_target}_{int(time.time())}.rdp")

        rdp_content = []
        if rdp_path and os.path.exists(rdp_path):
            try:
                with open(rdp_path, 'r', encoding='utf-8') as f:
                    rdp_content = f.readlines()
            except UnicodeDecodeError:
                with open(rdp_path, 'r', encoding='utf-16') as f:
                    rdp_content = f.readlines()
            rdp_content = [line for line in rdp_content if not line.lower().startswith('alternate shell:')]
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

        rdp_content.append('alternate shell:s:cmd.exe\n')

        with open(temp_rdp, 'w', encoding='utf-16') as f:
            f.writelines(rdp_content)

        target = None
        if jump_ip and jump_user and jump_pass:
            import win32cred
            target = f"TERMSRV/{jump_ip}"
            cred = {
                'TargetName': target, 'UserName': jump_user,
                'CredentialBlob': jump_pass,
                'Type': win32cred.CRED_TYPE_DOMAIN_PASSWORD, 'Persist': win32cred.CRED_PERSIST_SESSION
            }
            win32cred.CredWrite(cred, 0)

        DETACHED_PROCESS = 0x00000008
        subprocess.Popen(["mstsc.exe", temp_rdp], creationflags=DETACHED_PROCESS)

        def cleanup_thread():
            try:
                time.sleep(3)
                if target:
                    import win32cred
                    try: win32cred.CredDelete(target, win32cred.CRED_TYPE_DOMAIN_PASSWORD, 0)
                    except Exception: pass
            finally:
                for _ in range(5):
                    time.sleep(2)
                    try:
                        if os.path.exists(temp_rdp):
                            os.remove(temp_rdp)
                            break
                    except Exception:
                        pass

        threading.Thread(target=cleanup_thread, daemon=True).start()

        return jsonify({"mensagem": "Iniciando Área de Trabalho Remota e Injetando Credenciais!"}), 200
    except Exception as e:
        logger.exception("Erro interno:")
        return jsonify({"erro": "Erro interno do servidor."}), 500

@app.route('/api/open-rdp', methods=['POST'])
def open_rdp():
    import tempfile
    import time
    data = request.json
    ip = data.get('ip')
    base_rdp = data.get('base_rdp')

    if not ip or not re.match(r'^[a-zA-Z0-9\-\.]+$', ip):
        return jsonify({"erro": "IP ou Hostname inválido."}), 400

    rdp_content_lines = []
    if base_rdp and os.path.exists(base_rdp) and base_rdp.endswith('.rdp'):
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
    temp_rdp = os.path.join(temp_dir, f"autoping_direct_{safe_target}_{int(time.time())}.rdp")

    with open(temp_rdp, 'w', encoding='utf-16') as f:
        f.writelines(rdp_content_lines)

    DETACHED_PROCESS = 0x00000008
    subprocess.Popen(["mstsc.exe", temp_rdp], creationflags=DETACHED_PROCESS)

    def cleanup_thread():
        time.sleep(5)
        for _ in range(5):
            time.sleep(2)
            try:
                if os.path.exists(temp_rdp):
                    os.remove(temp_rdp)
                    break
            except Exception:
                pass

    threading.Thread(target=cleanup_thread, daemon=True).start()

    return jsonify({"mensagem": "Conexão de Área de Trabalho Remota iniciada com sucesso!"}), 200

@app.route('/api/download-rdp/<ip>')
def download_rdp(ip):
    if not re.match(r'^[a-zA-Z0-9\-\.]+$', ip):
        return "IP ou Hostname inválido", 400
    
    base_rdp = request.args.get('base_rdp', '')
    rdp_content_lines = []
    
    if base_rdp and os.path.exists(base_rdp) and base_rdp.endswith('.rdp'):
        try:
            with open(base_rdp, 'r', encoding='utf-8') as f:
                rdp_content_lines = f.readlines()
        except UnicodeDecodeError:
            with open(base_rdp, 'r', encoding='utf-16') as f:
                rdp_content_lines = f.readlines()
                
        # Remover IP/Host antigo do arquivo base
        rdp_content_lines = [line for line in rdp_content_lines if not line.lower().startswith('full address:s:')]
    
    # Injetar o novo IP
    rdp_content_lines.append(f"full address:s:{ip}\n")
    
    # Garantir prompt de credenciais se não existir
    if not any(line.lower().startswith('prompt for credentials:') for line in rdp_content_lines):
        rdp_content_lines.append("prompt for credentials:i:1\n")
        
    rdp_content = "".join(rdp_content_lines)
    
    response = make_response(rdp_content)
    response.headers["Content-Disposition"] = f"attachment; filename=Acesso_{ip}.rdp"
    response.headers["Content-type"] = "application/x-rdp"
    return response

if __name__ == '__main__':
    init_db()
    migrate_excel_to_sqlite()
    app.run(debug=False, port=5000, threaded=True, host="0.0.0.0")
