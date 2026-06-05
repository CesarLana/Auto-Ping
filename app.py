import os
import subprocess
import re
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


# Lê o arquivo Excel e retorna os dados em formato DataFrame (Tabela do Pandas)
def read_excel():
    if not os.path.exists(EXCEL_FILE):
        init_excel()
    df = pd.read_excel(EXCEL_FILE)
    # Garante que todas as colunas existem na leitura para evitar erros
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df


# Salva o DataFrame atualizado de volta no arquivo Excel
def save_excel(df):
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
    for campo in ["RACF", "Funcional", "Nome"]:
        if not dados.get(campo):
            return jsonify({"erro": f"O campo '{campo}' é obrigatório."}), 400

    df = read_excel()

    racf_req = str(dados.get("RACF", "")).strip().upper()
    func_req = str(dados.get("Funcional", "")).strip()
    email_req = str(dados.get("Email", "")).strip().lower()

    if not df.empty:
        if racf_req and racf_req in df["RACF"].astype(str).str.strip().str.upper().values:
            return jsonify({"erro": "Já existe um usuário cadastrado com este RACF."}), 409
        if func_req and func_req in df["Funcional"].astype(str).str.strip().values:
            return jsonify({"erro": "Já existe um usuário cadastrado com esta Funcional."}), 409
        if email_req and email_req in df["Email"].astype(str).str.strip().str.lower().values:
            return jsonify({"erro": "Já existe um usuário cadastrado com este E-mail."}), 409

    novo = {
        "ID": next_id(),
        "RACF": dados["RACF"].upper(),
        "Funcional": dados["Funcional"],
        "Nome": dados.get("Nome", ""),
        "Email": dados.get("Email", ""),
        "Serial": dados.get("Serial", ""),
        "Hostname": dados.get("Hostname", ""),
        "IP": dados.get("IP", ""),
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

    df = df.fillna("")
    return jsonify(df.to_dict(orient="records"))


@app.route("/usuarios/<int:user_id>", methods=["GET"])
def buscar(user_id):
    # Retorna os detalhes de um único usuário pelo ID
    df = read_excel()
    usuario = df[df["ID"] == user_id]

    if usuario.empty:
        return jsonify({"erro": "Usuário não encontrado."}), 404

    return jsonify(usuario.iloc[0].fillna("").to_dict())


@app.route("/usuarios/<int:user_id>", methods=["PUT"])
def editar(user_id):
    dados = request.get_json()
    df = read_excel()

    idx = df.index[df["ID"] == user_id]
    if idx.empty:
        return jsonify({"erro": "Usuário não encontrado."}), 404

    outros_df = df[df["ID"] != user_id]

    racf_req = str(dados.get("RACF", "")).strip().upper() if "RACF" in dados else ""
    func_req = str(dados.get("Funcional", "")).strip() if "Funcional" in dados else ""
    email_req = str(dados.get("Email", "")).strip().lower() if "Email" in dados else ""

    if not outros_df.empty:
        if racf_req and racf_req in outros_df["RACF"].astype(str).str.strip().str.upper().values:
            return jsonify({"erro": "Já existe outro usuário cadastrado com este RACF."}), 409
        if func_req and func_req in outros_df["Funcional"].astype(str).str.strip().values:
            return jsonify({"erro": "Já existe outro usuário cadastrado com esta Funcional."}), 409
        if email_req and email_req in outros_df["Email"].astype(str).str.strip().str.lower().values:
            return jsonify({"erro": "Já existe outro usuário cadastrado com este E-mail."}), 409

    # Atualiza apenas os campos enviados
    i = idx[0]
    for campo in ["RACF", "Funcional", "Nome", "Email", "Serial", "Hostname", "IP", "Status"]:
        if campo in dados:
            valor = dados[campo]
            if campo == "RACF" and valor:
                valor = valor.upper()
            df.at[i, campo] = valor

    save_excel(df)
    return jsonify({"mensagem": "Usuário atualizado com sucesso!", "usuario": df.loc[i].fillna("").to_dict()})


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
    # Proteção de segurança: apenas letras, números, hífens e pontos
    if not re.match(r'^[a-zA-Z0-9\-\.]+$', hostname):
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

        # Usa Regex para capturar especificamente um padrão IPv4 (x.x.x.x) na resposta do ping
        match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', output)

        if match:
            ip = match.group(1)
            online = "Resposta de" in output or "Reply from" in output
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
