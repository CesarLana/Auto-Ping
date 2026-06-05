import pandas as pd
import random

users = [
    {"ID": 1, "RACF": "BRJOAOS", "Funcional": "100101", "Nome": "João Silva", "Email": "joao.silva@empresa.com", "Serial": "S-73829", "Hostname": "localhost", "IP": "127.0.0.1", "Status": "Ativo"},
    {"ID": 2, "RACF": "BRMARIA", "Funcional": "100102", "Nome": "Maria Oliveira", "Email": "maria.oliveira@empresa.com", "Serial": "S-12345", "Hostname": "BRSAONB94831", "IP": "10.0.0.15", "Status": "Ativo"},
    {"ID": 3, "RACF": "BRCARLO", "Funcional": "100103", "Nome": "Carlos Mendes", "Email": "carlos.mendes@empresa.com", "Serial": "S-99823", "Hostname": "127.0.0.1", "IP": "127.0.0.1", "Status": "Inativo"},
    {"ID": 4, "RACF": "BRANAC",  "Funcional": "100104", "Nome": "Ana Costa", "Email": "ana.costa@empresa.com", "Serial": "S-55442", "Hostname": "BRRJDT1234", "IP": "192.168.1.50", "Status": "Ativo"},
    {"ID": 5, "RACF": "BRLUCAS", "Funcional": "100105", "Nome": "Lucas Pereira", "Email": "lucas.pereira@empresa.com", "Serial": "S-11223", "Hostname": "localhost", "IP": "127.0.0.1", "Status": "Ativo"},
    {"ID": 6, "RACF": "BRJULIA", "Funcional": "100106", "Nome": "Júlia Ferreira", "Email": "julia.ferreira@empresa.com", "Serial": "S-44556", "Hostname": "BRSAONB8877", "IP": "10.1.2.33", "Status": "Ativo"},
    {"ID": 7, "RACF": "BRROBER", "Funcional": "100107", "Nome": "Roberto Almeida", "Email": "roberto.almeida@empresa.com", "Serial": "S-77889", "Hostname": "127.0.0.1", "IP": "127.0.0.1", "Status": "Ativo"},
    {"ID": 8, "RACF": "BRFERNA", "Funcional": "100108", "Nome": "Fernanda Lima", "Email": "fernanda.lima@empresa.com", "Serial": "S-33445", "Hostname": "BRBHDT9999", "IP": "192.168.0.100", "Status": "Inativo"},
    {"ID": 9, "RACF": "BRMICH",  "Funcional": "100109", "Nome": "Michael Scott", "Email": "michael.scott@empresa.com", "Serial": "S-99000", "Hostname": "localhost", "IP": "127.0.0.1", "Status": "Ativo"},
    {"ID": 10, "RACF": "BRDWIGH", "Funcional": "100110", "Nome": "Dwight Schrute", "Email": "dwight.schrute@empresa.com", "Serial": "S-66666", "Hostname": "BRSAONB1111", "IP": "10.0.5.55", "Status": "Ativo"}
]

df = pd.DataFrame(users)
df.to_excel('usuarios.xlsx', index=False)
print("Base de dados falsa gerada com sucesso!")
