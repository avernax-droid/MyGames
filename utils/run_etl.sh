#!/bin/bash

# 1. Descobre onde o script está (pasta utils/)
DIR_SCRIPT=$(cd "$(dirname "$0")" && pwd)

# 2. Volta duas pastas para trás para achar a raiz (MyGames_Homo/)
DIR_RAIZ=$(cd "$DIR_SCRIPT/../../" && pwd)

# 3. Carrega as variáveis do arquivo .env da pasta raiz
set -a
source "$DIR_RAIZ/.env"
set +a

# 4. Vai para a raiz e executa o Docker
cd "$DIR_RAIZ" && docker compose run --rm "$SYNC_CONTAINER" > "$DIR_RAIZ/sync_catalogo.log" 2>&1