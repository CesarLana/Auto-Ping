import os
import subprocess
import re
import shutil
from flask import Flask, request, jsonify, send_from_directory
import pandas as pd

app = Flask(__name__, static_folder="static")

EXCEL_FILE = "usuarios.xlsx"
COLUMNS = ["ID", "RACF", "Funcional", "Nome", "Email", "Serial", "Hostname", "IP", "Status"]


# Cria o arquivo de banco de dados (Excel) com as colunas caso não exista
def init_excel():
    if not os.path.exists(EXCEL_FILE):
        df = pd.DataFrame(columns=COLUMNS)
        df.to_excel(EXCEL_FILE, index=False)


# Backup automático do banco de dados Excel antes de escritas
def backup_excel():
    if os.path.exists(EXCEL_FILE):
        backup_file = EXCEL_FILE + ".bak"
        try:
            shutil.copy2(EXCEL_FILE, backup_file)
        except Exception as e:
            print(f"Erro ao criar backup do Excel: {e}")


# Lê o arquivo Excel, normaliza e retorna os dados em formato DataFrame limpo
def read_excel():
    if not os.path.exists(EXCEL_FILE):
        init_excel()
    try:
        df = pd.read_excel(EXCEL_FILE)
    except Exception:
        df = pd.DataFrame(columns=COLUMNS)
        
    # Garante que todas as colunas existem na leitura para evitar erros
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""
            
    # Normaliza IDs
    df["ID"] = pd.to_numeric(df["ID"], errors="coerce").fillna(0).astype(int)
    
    # Normaliza colunas de texto para evitar "nan" e formatações de float indesejadas (ex: 123.0 -> "123")
    text_cols = ["RACF", "Funcional", "Nome", "Email", "Serial", "Hostname", "IP", "Status"]
    for col in text_cols:
        df[col] = df[col].apply(
            lambda x: str(int(x)) if isinstance(x, float) and x.is_integer() else (str(x) if pd.notna(x) else "")
        )
        df[col] = df[col].str.strip()
        
    # Higienizações específicas de case-insensitive
    df["RACF"] = df["RACF"].str.upper()
    df["Email"] = df["Email"].str.lower()
    df["Hostname"] = df["Hostname"].str.upper()
    
    # Status padrão
    df["Status"] = df["Status"].apply(lambda x: x if x in ["Ativo", "Inativo"] else "Ativo")
    
    return df


# Salva o DataFrame atualizado de volta no arquivo Excel (com backup preventivo)
def save_excel(df):
    backup_excel()
    df.to_excel(EXCEL_FILE, index=False)


# Gera um novo ID único (Auto Incremento) pegando o maior ID atual + 1
def next_id():
    df = read_excel()
    if df.empty:
        return 1
    return int(df["ID"].max()) + 1


# ─── Rotas de Página ─────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ─── API REST ─────────────────────────────────────────────────────

@app.route("/cadastrar", methods=["POST"])
def cadastrar():
    # Rota que recebe os dados do frontend em formato JSON
    dados = request.get_json()

    # Validação de campos obrigatórios
    for campo in ["RACF", "Funcional", "Nome", "Email", "Hostname"]:
        if not str(dados.get(campo, "")).strip():
            return jsonify({"erro": f"O campo '{campo}' é obrigatório."}), 400

    racf_req = str(dados["RACF"]).strip().upper()
    func_req = str(dados["Funcional"]).strip()
    email_req = str(dados["Email"]).strip().lower()
    hostname_req = str(dados["Hostname"]).strip().upper()

    # Validação do RACF: máximo de 7 caracteres
    if len(racf_req) > 7:
        return jsonify({"erro": "O campo RACF deve ter no máximo 7 caracteres."}), 400

    # Validação do Funcional: apenas números, máximo de 9 dígitos
    if not re.match(r'^\d{1,9}$', func_req):
        return jsonify({"erro": "O campo Funcional deve conter apenas números (máx. 9 dígitos)."}), 400

    df = read_excel()

    # Verificação de duplicatas (usando dados já normalizados)
    if not df.empty:
        if racf_req in df["RACF"].values:
            return jsonify({"erro": "Já existe um usuário cadastrado com este RACF."}), 409
        if func_req in df["Funcional"].values:
            return jsonify({"erro": "Já existe um usuário cadastrado com esta Funcional."}), 409
        if email_req and email_req in df["Email"].values:
            return jsonify({"erro": "Já existe um usuário cadastrado com este E-mail."}), 409
        if hostname_req in df["Hostname"].values:
            return jsonify({"erro": "Já existe um usuário cadastrado com este Hostname."}), 409

    novo = {
        "ID": next_id(),
        "RACF": racf_req,
        "Funcional": func_req,
        "Nome": dados["Nome"].strip(),
        "Email": dados["Email"].strip(),
        "Serial": str(dados.get("Serial", "")).strip(),
        "Hostname": dados["Hostname"].strip(),
        "IP": str(dados.get("IP", "")).strip(),
        "Status": dados.get("Status", "Ativo"),
    }

    # Adiciona o novo registro na tabela e salva no Excel
    df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
    save_excel(df)

    return jsonify({"mensagem": "Usuário cadastrado com sucesso!", "usuario": novo}), 201


@app.route("/usuarios", methods=["GET"])
def listar():
    # Retorna a lista completa de usuários ou filtra caso haja uma pesquisa (busca)
    df = read_excel()
    busca = request.args.get("busca", "").strip().lower()

    if busca and not df.empty:
        # Filtra linhas onde qualquer valor de coluna contenha o texto da busca
        mask = df.apply(
            lambda row: row.astype(str).str.lower().str.contains(busca).any(), axis=1
        )
        df = df[mask]

    return jsonify(df.to_dict(orient="records"))


@app.route("/usuarios/<int:user_id>", methods=["GET"])
def buscar(user_id):
    # Retorna os detalhes de um único usuário pelo ID
    df = read_excel()
    usuario = df[df["ID"] == user_id]

    if usuario.empty:
        return jsonify({"erro": "Usuário não encontrado."}), 404

    return jsonify(usuario.iloc[0].to_dict())


@app.route("/usuarios/<int:user_id>", methods=["PUT"])
def editar(user_id):
    dados = request.get_json()
    df = read_excel()

    idx = df.index[df["ID"] == user_id]
    if idx.empty:
        return jsonify({"erro": "Usuário não encontrado."}), 404

    # Validação de campos obrigatórios na edição
    for campo in ["RACF", "Funcional", "Nome", "Email", "Hostname"]:
        if campo in dados and not str(dados[campo]).strip():
            return jsonify({"erro": f"O campo '{campo}' é obrigatório."}), 400

    racf_req = str(dados.get("RACF", "")).strip().upper() if "RACF" in dados else ""
    func_req = str(dados.get("Funcional", "")).strip() if "Funcional" in dados else ""
    email_req = str(dados.get("Email", "")).strip().lower() if "Email" in dados else ""
    hostname_req = str(dados.get("Hostname", "")).strip().upper() if "Hostname" in dados else ""

    # Validação do RACF: máximo de 7 caracteres
    if racf_req and len(racf_req) > 7:
        return jsonify({"erro": "O campo RACF deve ter no máximo 7 caracteres."}), 400

    # Validação do Funcional: apenas números, máximo de 9 dígitos
    if func_req and not re.match(r'^\d{1,9}$', func_req):
        return jsonify({"erro": "O campo Funcional deve conter apenas números (máx. 9 dígitos)."}), 400

    # Exclui o registro atual da verificação de duplicatas
    outros_df = df[df["ID"] != user_id]

    # Verificação de duplicatas (usando dados já normalizados), excluindo o próprio registro
    if not outros_df.empty:
        if racf_req and racf_req in outros_df["RACF"].values:
            return jsonify({"erro": "Já existe outro usuário cadastrado com este RACF."}), 409
        if func_req and func_req in outros_df["Funcional"].values:
            return jsonify({"erro": "Já existe outro usuário cadastrado com esta Funcional."}), 409
        if email_req and email_req in outros_df["Email"].values:
            return jsonify({"erro": "Já existe outro usuário cadastrado com este E-mail."}), 409
        if hostname_req and hostname_req in outros_df["Hostname"].values:
            return jsonify({"erro": "Já existe outro usuário cadastrado com este Hostname."}), 409

    # Atualiza apenas os campos enviados
    i = idx[0]
    for campo in ["RACF", "Funcional", "Nome", "Email", "Serial", "Hostname", "IP", "Status"]:
        if campo in dados:
            valor = str(dados[campo]).strip()
            if campo == "RACF" and valor:
                valor = valor.upper()
            df.at[i, campo] = valor

    save_excel(df)
    return jsonify({"mensagem": "Usuário atualizado com sucesso!", "usuario": df.loc[i].to_dict()})


@app.route("/usuarios/<int:user_id>", methods=["DELETE"])
def excluir(user_id):
    # Remove a linha cujo ID bate com o enviado
    df = read_excel()

    if user_id not in df["ID"].values:
        return jsonify({"erro": "Usuário não encontrado."}), 404

    df = df[df["ID"] != user_id]
    save_excel(df)

    return jsonify({"mensagem": "Usuário excluído com sucesso!"})


# ─── UTILITÁRIO: PING ────────────────────────────────────────────

@app.route("/ping/<hostname>", methods=["GET"])
def ping_host(hostname):
    # Proteção de segurança: apenas letras, números, hífens, pontos e underscores
    if not re.match(r'^[a-zA-Z0-9\-\._]+$', hostname):
        return jsonify({"erro": "Hostname inválido."}), 400

    try:
        # Dispara comando no Windows:
        # ping -4 (apenas IPv4) -n 1 (1 pacote) -w 3000 (espera até 3s)
        result = subprocess.run(
            ["ping", "-4", "-n", "1", "-w", "3000", hostname],
            capture_output=True,
            text=True,
            timeout=10,
        )

        output = result.stdout

        # Tenta capturar primeiro o IP do destinatário contido entre colchetes (ex: "Disparando BRA-PC [10.0.0.5]...")
        # para evitar pegar o IP do gateway/roteador em caso de erro "Host de destino inacessível"
        ip = None
        first_line_match = re.search(r'\[(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\]', output)
        if first_line_match:
            ip = first_line_match.group(1)
        else:
            # Fallback para qualquer IP presente na saída do comando
            match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', output)
            if match:
                ip = match.group(1)

        if ip:
            # Verifica se o host respondeu de fato analisando a presença de "ttl=" no texto e o returncode
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
