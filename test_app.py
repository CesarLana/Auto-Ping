import os
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

# Importa o app do projeto
from app import app, EXCEL_FILE
import app as main_app

TEST_EXCEL_FILE = "test_usuarios.xlsx"

@pytest.fixture
def client():
    # Configura a aplicação para modo de teste
    app.config["TESTING"] = True
    
    # Redireciona o arquivo Excel para um arquivo temporário de teste
    main_app.EXCEL_FILE = TEST_EXCEL_FILE
    
    # Garante que começa limpo
    if os.path.exists(TEST_EXCEL_FILE):
        os.remove(TEST_EXCEL_FILE)
        
    main_app.init_excel()

    with app.test_client() as client:
        yield client
        
    # Limpeza após os testes
    if os.path.exists(TEST_EXCEL_FILE):
        os.remove(TEST_EXCEL_FILE)


def test_cadastrar_usuario_sucesso(client):
    payload = {
        "RACF": "TEST01",
        "Funcional": "99901",
        "Nome": "Usuário Teste",
        "Email": "teste@empresa.com",
        "Serial": "SN-123",
        "Hostname": "PC-TESTE",
        "IP": "10.0.0.50",
        "Status": "Ativo"
    }
    response = client.post("/cadastrar", json=payload)
    assert response.status_code == 201
    dados = response.get_json()
    assert dados["mensagem"] == "Usuário cadastrado com sucesso!"
    assert dados["usuario"]["RACF"] == "TEST01"


def test_cadastrar_usuario_duplicado(client):
    payload = {
        "RACF": "TEST02",
        "Funcional": "99902",
        "Nome": "Duplicado"
    }
    client.post("/cadastrar", json=payload)
    
    # Tenta cadastrar novamente com o mesmo RACF
    response = client.post("/cadastrar", json=payload)
    assert response.status_code == 409
    assert "Já existe um usuário cadastrado com este RACF" in response.get_json()["erro"]


def test_listar_usuarios(client):
    client.post("/cadastrar", json={"RACF": "LST01", "Funcional": "88801", "Nome": "Listado 1"})
    client.post("/cadastrar", json={"RACF": "LST02", "Funcional": "88802", "Nome": "Listado 2"})
    
    response = client.get("/usuarios")
    assert response.status_code == 200
    dados = response.get_json()
    assert len(dados) == 2
    assert dados[0]["RACF"] == "LST01"


def test_buscar_usuario_por_id(client):
    res = client.post("/cadastrar", json={"RACF": "FND01", "Funcional": "77701", "Nome": "Encontrado"})
    user_id = res.get_json()["usuario"]["ID"]
    
    response = client.get(f"/usuarios/{user_id}")
    assert response.status_code == 200
    assert response.get_json()["RACF"] == "FND01"


def test_editar_usuario(client):
    res = client.post("/cadastrar", json={"RACF": "EDT01", "Funcional": "66601", "Nome": "Antes"})
    user_id = res.get_json()["usuario"]["ID"]
    
    response = client.put(f"/usuarios/{user_id}", json={"Nome": "Depois"})
    assert response.status_code == 200
    assert response.get_json()["usuario"]["Nome"] == "Depois"


def test_excluir_usuario(client):
    res = client.post("/cadastrar", json={"RACF": "DEL01", "Funcional": "55501", "Nome": "A ser deletado"})
    user_id = res.get_json()["usuario"]["ID"]
    
    response = client.delete(f"/usuarios/{user_id}")
    assert response.status_code == 200
    
    # Verifica se foi excluído
    response_get = client.get(f"/usuarios/{user_id}")
    assert response_get.status_code == 404


@patch("app.subprocess.run")
def test_ping_host_online(mock_run, client):
    # Simula o retorno de um ping bem-sucedido no Windows
    mock_result = MagicMock()
    mock_result.stdout = "Disparando contra localhost [127.0.0.1] com 32 bytes de dados:\nResposta de 127.0.0.1: bytes=32 tempo<1ms TTL=128"
    mock_run.return_value = mock_result
    
    response = client.get("/ping/localhost")
    assert response.status_code == 200
    dados = response.get_json()
    assert dados["online"] is True
    assert dados["ip"] == "127.0.0.1"


@patch("app.subprocess.run")
def test_ping_host_offline(mock_run, client):
    # Simula o retorno de um ping que falhou
    mock_result = MagicMock()
    mock_result.stdout = "A solicitação ping não pôde encontrar o host maquina-inexistente. Verifique o nome e tente novamente."
    mock_run.return_value = mock_result
    
    response = client.get("/ping/maquina-inexistente")
    assert response.status_code == 404
    assert "Não foi possível resolver o hostname" in response.get_json()["erro"]
