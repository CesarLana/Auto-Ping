#!/bin/bash
echo "=============================================="
echo "Iniciando o sistema de Gestao de Colaboradores..."
echo "=============================================="
echo ""

# Abre o navegador padrão no endereço do sistema (macOS usa 'open', Linux usa 'xdg-open')
if [[ "$OSTYPE" == "darwin"* ]]; then
  open http://localhost:5000
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
  xdg-open http://localhost:5000
fi

# Inicia o servidor Python
python app.py
