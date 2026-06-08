import os
import subprocess
import re
import shutil
from flask import Flask, request, jsonify, send_from_directory
import pandas as pd

app = Flask(__name__, static_folder="static")

EXCEL_FILE = "usuarios.xlsx"
COLUMNS_USERS = ["ID", "RACF", "Funcional", "Nome", "Email", "Status"]
COLUMNS_MACHINES = ["ID", "Usuario_ID", "Tipo", "Hostname", "IP", "Serial"]


# Cria o arquivo de banco de dados (Excel) com as colunas caso não exista
def init_excel():
    if not os.path.exists(EXCEL_FILE):
        with pd.ExcelWriter(EXCEL_FILE) as writer:
            pd.DataFrame(columns=COLUMNS_USERS).to_excel(writer, sheet_name="Colaboradores", index=False)
            pd.DataFrame(columns=COLUMNS_MACHINES).to_excel(writer, sheet_name="Maquinas", index=False)


# Backup automático do banco de dados Excel antes de escritas
def backup_excel():
    if os.path.exists(EXCEL_FILE):
        backup_file = EXCEL_FILE + ".bak"
        try:
            shutil.copy2(EXCEL_FILE, backup_file)
        except Exception as e:
            print(f"Erro ao criar backup do Excel: {e}")


# Lê as duas abas do Excel, normaliza e retorna os dados em formato DataFrame limpo
def read_excel():
    if not os.path.exists(EXCEL_FILE):
        init_excel()
    try:
        xls = pd.ExcelFile(EXCEL_FILE)
    except Exception:
        init_excel()
        xls = pd.ExcelFile(EXCEL_FILE)

    # Migração automática de dados caso detecte planilha do formato antigo (aba única)
    if "Colaboradores" not in xls.sheet_names:
        backup_excel()
        try:
            df_old = pd.read_excel(EXCEL_FILE)
            for col in ["ID", "RACF", "Funcional", "Nome", "Email", "Serial", "Hostname", "IP", "Status"]:
                if col not in df_old.columns:
                    df_old[col] = ""
            
            df_users = df_old[["ID", "RACF", "Funcional", "Nome", "Email", "Status"]].copy()
            
            machines_list = []
            machine_id = 1
            for _, row in df_old.iterrows():
                h_name = str(row.get("Hostname", "")).strip()
                if h_name and h_name.lower() not in ["nan", ""]:
                    tipo = "Notebook"
                    h_lower = h_name.lower()
                    if "desk" in h_lower:
                        tipo = "Desktop"
                    elif "mini" in h_lower:
                        tipo = "Minidesk"
                        
                    machines_list.append({
                        "ID": machine_id,
                        "Usuario_ID": row["ID"],
                        "Tipo": tipo,
                        "Hostname": h_name,
                        "IP": str(row.get("IP", "")).strip(),
                        "Serial": str(row.get("Serial", "")).strip()
                    })
                    machine_id += 1
                    
            df_machines = pd.DataFrame(machines_list, columns=COLUMNS_MACHINES)
            
            with pd.ExcelWriter(EXCEL_FILE) as writer:
                df_users.to_excel(writer, sheet_name="Colaboradores", index=False)
                df_machines.to_excel(writer, sheet_name="Maquinas", index=False)
                
            xls = pd.ExcelFile(EXCEL_FILE)
        except Exception as e:
            print(f"Erro ao migrar a planilha antiga: {e}")
            df_users = pd.DataFrame(columns=COLUMNS_USERS)
            df_machines = pd.DataFrame(columns=COLUMNS_MACHINES)
            return df_users, df_machines

    df_users = pd.read_excel(xls, sheet_name="Colaboradores")
    df_machines = pd.read_excel(xls, sheet_name="Maquinas")

    # Normalização dos Colaboradores
    for col in COLUMNS_USERS:
        if col not in df_users.columns:
            df_users[col] = ""
    df_users["ID"] = pd.to_numeric(df_users["ID"], errors="coerce").fillna(0).astype(int)
    for col in ["RACF", "Funcional", "Nome", "Email", "Status"]:
        df_users[col] = df_users[col].apply(
            lambda x: str(int(x)) if isinstance(x, float) and x.is_integer() else (str(x) if pd.notna(x) else "")
        ).str.strip()
    df_users["RACF"] = df_users["RACF"].str.upper()
    df_users["Email"] = df_users["Email"].str.lower()
    df_users["Status"] = df_users["Status"].apply(lambda x: x if x in ["Ativo", "Inativo"] else "Ativo")

    # Normalização das Máquinas
    for col in COLUMNS_MACHINES:
        if col not in df_machines.columns:
            df_machines[col] = ""
    df_machines["ID"] = pd.to_numeric(df_machines["ID"], errors="coerce").fillna(0).astype(int)
    df_machines["Usuario_ID"] = pd.to_numeric(df_machines["Usuario_ID"], errors="coerce").fillna(0).astype(int)
    for col in ["Tipo", "Hostname", "IP", "Serial"]:
        df_machines[col] = df_machines[col].apply(
            lambda x: str(int(x)) if isinstance(x, float) and x.is_integer() else (str(x) if pd.notna(x) else "")
        ).str.strip()
    df_machines["Hostname"] = df_machines["Hostname"].str.upper()
    df_machines["Tipo"] = df_machines["Tipo"].apply(lambda x: x if x in ["Desktop", "Notebook", "Minidesk"] else "Notebook")

    return df_users, df_machines


# Salva ambos os DataFrames de volta no arquivo Excel
def save_excel(df_users, df_machines):
    backup_excel()
    with pd.ExcelWriter(EXCEL_FILE) as writer:
        df_users.to_excel(writer, sheet_name="Colaboradores", index=False)
        df_machines.to_excel(writer, sheet_name="Maquinas", index=False)


# Gera um novo ID único para colaborador
def next_id():
    df_users, _ = read_excel()
    if df_users.empty:
        return 1
    return int(df_users["ID"].max()) + 1


# Gera um novo ID único para máquina
def next_machine_id():
    _, df_machines = read_excel()
    if df_machines.empty:
        return 1
    return int(df_machines["ID"].max()) + 1


# ─── Rotas de Página ─────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ─── API REST ─────────────────────────────────────────────────────

@app.route("/cadastrar", methods=["POST"])
def cadastrar():
    dados = request.get_json()

    # Validação de campos obrigatórios
    for campo in ["RACF", "Funcional", "Nome", "Email"]:
        if not str(dados.get(campo, "")).strip():
            return jsonify({"erro": f"O campo '{campo}' é obrigatório."}), 400

    racf_req = str(dados["RACF"]).strip().upper()
    func_req = str(dados["Funcional"]).strip()
    email_req = str(dados["Email"]).strip().lower()

    if len(racf_req) > 7:
        return jsonify({"erro": "O campo RACF deve ter no máximo 7 caracteres."}), 400

    if not re.match(r'^\d{1,9}$', func_req):
        return jsonify({"erro": "O campo Funcional deve conter apenas números (máx. 9 dígitos)."}), 400

    df_users, df_machines = read_excel()

    # Verificação de duplicatas do colaborador
    if not df_users.empty:
        if racf_req in df_users["RACF"].values:
            return jsonify({"erro": "Já existe um usuário cadastrado com este RACF."}), 409
        if func_req in df_users["Funcional"].values:
            return jsonify({"erro": "Já existe um usuário cadastrado com esta Funcional."}), 409
        if email_req and email_req in df_users["Email"].values:
            return jsonify({"erro": "Já existe um usuário cadastrado com este E-mail."}), 409

    # Validar a lista de máquinas recebidas
    maquinas_req = dados.get("maquinas", [])
    novas_maquinas = []
    
    hostnames_lote = set()
    seriais_lote = set()

    for idx, maq in enumerate(maquinas_req):
        h_name = str(maq.get("Hostname", "")).strip().upper()
        serial = str(maq.get("Serial", "")).strip()
        tipo = str(maq.get("Tipo", "Notebook")).strip()
        ip = str(maq.get("IP", "")).strip()

        if not h_name:
            return jsonify({"erro": f"O campo Hostname da máquina #{idx + 1} é obrigatório."}), 400
        
        if not re.match(r'^[a-zA-Z0-9\-\._]+$', h_name):
            return jsonify({"erro": f"Hostname '{h_name}' inválido."}), 400

        # Verifica duplicação interna no próprio payload enviado
        if h_name in hostnames_lote:
            return jsonify({"erro": f"O hostname '{h_name}' foi informado mais de uma vez."}), 400
        hostnames_lote.add(h_name)

        if serial:
            if serial in seriais_lote:
                return jsonify({"erro": f"O número de serial '{serial}' foi informado mais de uma vez."}), 400
            seriais_lote.add(serial)

        # Verifica duplicação no banco de dados Excel de máquinas
        if not df_machines.empty:
            if h_name in df_machines["Hostname"].values:
                return jsonify({"erro": f"O hostname '{h_name}' já está cadastrado para outro colaborador."}), 409
            if serial and serial in df_machines["Serial"].values:
                return jsonify({"erro": f"O número de serial '{serial}' já está cadastrado para outro colaborador."}), 409

        novas_maquinas.append({
            "Tipo": tipo,
            "Hostname": h_name,
            "IP": ip,
            "Serial": serial
        })

    user_id = next_id()
    novo_usuario = {
        "ID": user_id,
        "RACF": racf_req,
        "Funcional": func_req,
        "Nome": dados["Nome"].strip(),
        "Email": email_req,
        "Status": dados.get("Status", "Ativo"),
    }

    # Adiciona máquinas vinculadas
    machine_start_id = next_machine_id()
    maquinas_adicionadas = []
    for idx_m, maq in enumerate(novas_maquinas):
        maq["ID"] = machine_start_id + idx_m
        maq["Usuario_ID"] = user_id
        maquinas_adicionadas.append(maq)

    # Insere e salva
    df_users = pd.concat([df_users, pd.DataFrame([novo_usuario])], ignore_index=True)
    if maquinas_adicionadas:
        df_machines = pd.concat([df_machines, pd.DataFrame(maquinas_adicionadas)], ignore_index=True)
    
    save_excel(df_users, df_machines)

    novo_usuario["maquinas"] = maquinas_adicionadas
    return jsonify({"mensagem": "Usuário cadastrado com sucesso!", "usuario": novo_usuario}), 201


@app.route("/usuarios", methods=["GET"])
def listar():
    df_users, df_machines = read_excel()
    busca = request.args.get("busca", "").strip().lower()

    usuarios_list = []
    for _, user_row in df_users.iterrows():
        user_dict = user_row.to_dict()
        user_id = user_dict["ID"]
        
        user_machines = []
        if not df_machines.empty:
            user_machines_df = df_machines[df_machines["Usuario_ID"] == user_id]
            user_machines = user_machines_df.to_dict(orient="records")
            
        user_dict["maquinas"] = user_machines
        usuarios_list.append(user_dict)

    # Busca global por colaborador ou suas máquinas
    if busca:
        filtrados = []
        for u in usuarios_list:
            match_colab = any(
                busca in str(u.get(k, "")).lower() 
                for k in ["RACF", "Funcional", "Nome", "Email", "Status"]
            )
            match_maq = any(
                busca in str(m.get(k, "")).lower() 
                for m in u["maquinas"] 
                for k in ["Hostname", "IP", "Serial", "Tipo"]
            )
            if match_colab or match_maq:
                filtrados.append(u)
        usuarios_list = filtrados

    return jsonify(usuarios_list)


@app.route("/usuarios/<int:user_id>", methods=["GET"])
def buscar(user_id):
    df_users, df_machines = read_excel()
    usuario_df = df_users[df_users["ID"] == user_id]

    if usuario_df.empty:
        return jsonify({"erro": "Usuário não encontrado."}), 404

    usuario = usuario_df.iloc[0].to_dict()
    user_machines = []
    if not df_machines.empty:
        user_machines_df = df_machines[df_machines["Usuario_ID"] == user_id]
        user_machines = user_machines_df.to_dict(orient="records")
        
    usuario["maquinas"] = user_machines
    return jsonify(usuario)


@app.route("/usuarios/<int:user_id>", methods=["PUT"])
def editar(user_id):
    dados = request.get_json()
    df_users, df_machines = read_excel()

    idx = df_users.index[df_users["ID"] == user_id]
    if idx.empty:
        return jsonify({"erro": "Usuário não encontrado."}), 404

    # Validação de campos obrigatórios
    for campo in ["RACF", "Funcional", "Nome", "Email"]:
        if campo in dados and not str(dados[campo]).strip():
            return jsonify({"erro": f"O campo '{campo}' é obrigatório."}), 400

    racf_req = str(dados.get("RACF", "")).strip().upper() if "RACF" in dados else ""
    func_req = str(dados.get("Funcional", "")).strip() if "Funcional" in dados else ""
    email_req = str(dados.get("Email", "")).strip().lower() if "Email" in dados else ""

    if racf_req and len(racf_req) > 7:
        return jsonify({"erro": "O campo RACF deve ter no máximo 7 caracteres."}), 400

    if func_req and not re.match(r'^\d{1,9}$', func_req):
        return jsonify({"erro": "O campo Funcional deve conter apenas números (máx. 9 dígitos)."}), 400

    # Verificação de duplicatas
    outros_users = df_users[df_users["ID"] != user_id]
    if not outros_users.empty:
        if racf_req and racf_req in outros_users["RACF"].values:
            return jsonify({"erro": "Já existe outro usuário cadastrado com este RACF."}), 409
        if func_req and func_req in outros_users["Funcional"].values:
            return jsonify({"erro": "Já existe outro usuário cadastrado com esta Funcional."}), 409
        if email_req and email_req in outros_users["Email"].values:
            return jsonify({"erro": "Já existe outro usuário cadastrado com este E-mail."}), 409

    # Validar e vincular novas máquinas (se fornecido na edição)
    if "maquinas" in dados:
        maquinas_req = dados["maquinas"]
        novas_maquinas = []
        
        hostnames_lote = set()
        seriais_lote = set()

        outras_maquinas = df_machines[df_machines["Usuario_ID"] != user_id] if not df_machines.empty else pd.DataFrame(columns=COLUMNS_MACHINES)

        for idx_m, maq in enumerate(maquinas_req):
            h_name = str(maq.get("Hostname", "")).strip().upper()
            serial = str(maq.get("Serial", "")).strip()
            tipo = str(maq.get("Tipo", "Notebook")).strip()
            ip = str(maq.get("IP", "")).strip()

            if not h_name:
                return jsonify({"erro": f"O campo Hostname da máquina #{idx_m + 1} é obrigatório."}), 400
            
            if not re.match(r'^[a-zA-Z0-9\-\._]+$', h_name):
                return jsonify({"erro": f"Hostname '{h_name}' inválido."}), 400

            if h_name in hostnames_lote:
                return jsonify({"erro": f"O hostname '{h_name}' foi informado mais de uma vez."}), 400
            hostnames_lote.add(h_name)

            if serial:
                if serial in seriais_lote:
                    return jsonify({"erro": f"O número de serial '{serial}' foi informado mais de uma vez."}), 400
                seriais_lote.add(serial)

            if not outras_maquinas.empty:
                if h_name in outras_maquinas["Hostname"].values:
                    return jsonify({"erro": f"O hostname '{h_name}' já está cadastrado para outro colaborador."}), 409
                if serial and serial in outras_maquinas["Serial"].values:
                    return jsonify({"erro": f"O número de serial '{serial}' já está cadastrado para outro colaborador."}), 409

            novas_maquinas.append({
                "Tipo": tipo,
                "Hostname": h_name,
                "IP": ip,
                "Serial": serial
            })

        # Remove todas as máquinas antigas vinculadas a este ID
        if not df_machines.empty:
            df_machines = df_machines[df_machines["Usuario_ID"] != user_id]

        # Insere a nova lista de máquinas
        machine_start_id = next_machine_id()
        maquinas_adicionadas = []
        for idx_m, maq in enumerate(novas_maquinas):
            maq["ID"] = machine_start_id + idx_m
            maq["Usuario_ID"] = user_id
            maquinas_adicionadas.append(maq)

        if maquinas_adicionadas:
            df_machines = pd.concat([df_machines, pd.DataFrame(maquinas_adicionadas)], ignore_index=True)

    # Atualiza o colaborador
    i = idx[0]
    for campo in ["RACF", "Funcional", "Nome", "Email", "Status"]:
        if campo in dados:
            valor = str(dados[campo]).strip()
            if campo == "RACF" and valor:
                valor = valor.upper()
            df_users.at[i, campo] = valor

    save_excel(df_users, df_machines)
    
    usuario_atualizado = df_users.loc[i].to_dict()
    user_machines = []
    if not df_machines.empty:
        user_machines = df_machines[df_machines["Usuario_ID"] == user_id].to_dict(orient="records")
    usuario_atualizado["maquinas"] = user_machines

    return jsonify({"mensagem": "Usuário atualizado com sucesso!", "usuario": usuario_atualizado})


@app.route("/usuarios/<int:user_id>", methods=["DELETE"])
def excluir(user_id):
    df_users, df_machines = read_excel()

    if user_id not in df_users["ID"].values:
        return jsonify({"erro": "Usuário não encontrado."}), 404

    df_users = df_users[df_users["ID"] != user_id]
    if not df_machines.empty:
        df_machines = df_machines[df_machines["Usuario_ID"] != user_id]

    save_excel(df_users, df_machines)
    return jsonify({"mensagem": "Usuário excluído com sucesso!"})


# ─── UTILITÁRIO: PING ────────────────────────────────────────────

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
        if bracket_match:
            ip = bracket_match.group(1)
        elif re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', hostname):
            ip = hostname
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
                if any(x in line_lower for x in ["inacess", "unreach", "resposta de", "reply from", "perda", "lost"]):
                    continue
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
        return jsonify({"erro": str(e)}), 500


if __name__ == "__main__":
    init_excel()
    app.run(debug=True, port=5000)
