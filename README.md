# Auto-Ping - Gestão de Colaboradores e Monitoramento

Uma ferramenta web leve e local construída para otimizar o dia a dia do Suporte de TI. Ela centraliza informações de usuários (RACF, Funcional, Hostname) e automatiza o processo de "Ping" de máquinas via CMD, entregando resultados e endereços IP instantaneamente na tela, sem a necessidade de alternar entre o ServiceNow, Intune e o Prompt de Comando.

## 🚀 Principais Funcionalidades

- **Ping em Tempo Real**: Digite o RACF ou nome do colaborador para pingar a máquina dele automaticamente em *background*.
- **Cópia de 1 Clique**: Um botão ao lado de cada IP resolvido para copiar rapidamente para a área de transferência (ideal para colar no Remote Desktop / Jump Server).
- **Lista de Favoritos**: Salve os colaboradores que você atende frequentemente com uma "estrela" para acesso e ping instantâneos no Dashboard.
- **Histórico Recente**: Suas últimas 5 pesquisas ficam salvas no Dashboard para retorno rápido.
- **Banco de Dados Local (Excel)**: Todos os registros ficam salvos em um arquivo local `usuarios.xlsx`, que é criado automaticamente na primeira execução. Não requer configuração de banco de dados SQL.
- **Prevenção de Duplicatas**: Validação automática para impedir a criação de usuários com RACF, Funcional ou E-mail repetidos.

## 📋 Pré-requisitos

Para rodar este projeto, você precisará ter o [Python](https://www.python.org/) instalado em sua máquina e as seguintes bibliotecas:

```bash
pip install flask pandas openpyxl
```

## 🛠️ Como Usar

### Opção 1: O Jeito Rápido (Recomendado)
Basta dar um duplo clique no arquivo **`iniciar.bat`**. 
Ele abrirá uma janela preta (o servidor) e em seguida abrirá automaticamente o seu navegador padrão na tela do sistema.

### Opção 2: Pelo Terminal
Abra o Prompt de Comando na pasta do projeto e digite:
```bash
python app.py
```
Em seguida, acesse no navegador: `http://localhost:5000`

## 📁 Estrutura de Arquivos

- `app.py` - Backend em Python/Flask que roda os pings e acessa a planilha.
- `iniciar.bat` - Atalho para inicialização rápida.
- `seed.py` - Script opcional para gerar uma base de dados falsa para testes.
- `static/`
  - `index.html` - Toda a interface do sistema.
  - `style.css` - Estilos visuais e Modo Escuro.
  - `script.js` - Lógica visual, requisições de Ping e LocalStorage de favoritos.
- `usuarios.xlsx` - Arquivo onde os dados de cadastro são guardados (gerado na execução).
