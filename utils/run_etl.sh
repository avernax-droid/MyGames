#!/bin/bash

# 1. Descobre onde o script está (pasta utils/)
DIR_SCRIPT=$(cd "$(dirname "$0")" && pwd)

# 2. Volta uma pasta para trás para achar a raiz (mygames_site/)
DIR_RAIZ=$(cd "$DIR_SCRIPT/../" && pwd)

# 3. Define os caminhos exatos (Python do VENV, script e log)
PYTHON_EXEC="$DIR_RAIZ/venv/bin/python"
SCRIPT_PYTHON="$DIR_SCRIPT/sync_catalogo.py"
ARQUIVO_LOG="$DIR_RAIZ/sync_catalogo.log"

# 4. Registra a data da execução no log e roda o script via VENV
echo "===================================================" >> "$ARQUIVO_LOG"
echo "Iniciando ETL em: $(date)" >> "$ARQUIVO_LOG"
"$PYTHON_EXEC" "$SCRIPT_PYTHON" >> "$ARQUIVO_LOG" 2>&1
