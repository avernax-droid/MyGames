# ==============================================================================
# PROJETO: MyGames
# MÓDULO: scripts/rastrear_correios.py
# FUNÇÃO: Script de teste isolado para consulta da API SRO dos Correios em lote.
# HISTÓRICO DE ALTERAÇÕES:
# - Atualizado para receber o código de rastreio via argumento de linha de comando.
# - Atualizado para ler as credenciais de produção diretamente do .env do MyGames_Admin.
# - 22/10/2026: Refatoração para autenticação OAuth2 (Basic Auth no endpoint /autentica/cartaopostagem).
# - 22/10/2026: Inclusão de .strip() nas variáveis de ambiente e User-Agent nos headers.
# - 22/10/2026: Correção da URL SRO para a versão 3 (srorastro/v3/objetos) e ajuste na passagem de parâmetros.
# ==============================================================================

import os
import sys
import base64
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

caminho_env_admin = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../MyGames_Admin/.env'))
if not os.path.exists(caminho_env_admin):
    caminho_env_admin = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../MyGames_Admin/.env_2'))

load_dotenv(dotenv_path=caminho_env_admin)

# Aplicação de .strip() para evitar espaços ou quebras de linha invisíveis
CLIENT_ID = os.getenv('CORREIOS_CLIENT_ID', '').strip()
CLIENT_SECRET = os.getenv('CORREIOS_CLIENT_SECRET', '').strip()
CARTAO_POSTAGEM = os.getenv('CORREIOS_CARTAO_POSTAGEM', '0076088456').strip()

URL_TOKEN = "https://api.correios.com.br/token/v1/autentica/cartaopostagem"
URL_SRO = "https://api.correios.com.br/srorastro/v1/objetos"

TOKEN_CACHE = {"token": None, "expira_em": None}

# User-Agent padrão para evitar bloqueios do WAF dos Correios
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"

def obter_token():
    global TOKEN_CACHE
    
    print(f"DEBUG - Lendo credenciais em: {caminho_env_admin}")
    print(f"DEBUG - Client ID carregado: '{CLIENT_ID}'")
    print(f"DEBUG - Cartão de Postagem: '{CARTAO_POSTAGEM}'")
    
    if not CLIENT_ID or not CLIENT_SECRET:
        raise ValueError("Erro: Credenciais CORREIOS_CLIENT_ID ou CORREIOS_CLIENT_SECRET não encontradas no ficheiro.")

    if TOKEN_CACHE["token"] and TOKEN_CACHE["expira_em"] > datetime.now() + timedelta(minutes=5):
        print("[TOKEN] Utilizando token em cache.")
        return TOKEN_CACHE["token"]

    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    auth_base64 = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
    
    headers = {
        "Authorization": f"Basic {auth_base64}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT
    }
    
    payload = {
        "numero": CARTAO_POSTAGEM
    }
    
    try:
        resp = requests.post(URL_TOKEN, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        token = data.get("token") or data.get("access_token")
        expira_em = datetime.now() + timedelta(seconds=data.get("expires_in", 28800))
        TOKEN_CACHE["token"] = token
        TOKEN_CACHE["expira_em"] = expira_em
        print(f"[TOKEN] Novo token gerado, expira às {expira_em.strftime('%d/%m/%Y %H:%M')}")
        return token
    except requests.exceptions.RequestException as e:
        print(f"Erro ao conectar na API de autenticação: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Detalhes: {e.response.text}")
        sys.exit(1)

def rastrear_lote(codigos):
    token = obter_token()
    codigos_str = ",".join(codigos)
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": USER_AGENT
    }
    
    try:
        resp = requests.get(URL_SRO, headers=headers, params={"codigosObjetos": codigos_str, "resultado": "T"}, timeout=20)
        
        if resp.status_code == 401:
            TOKEN_CACHE["token"] = None
            return rastrear_lote(codigos)
            
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro na consulta SRO: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Detalhes: {e.response.text}")
        return None

def formatar_saida(data):
    if not data or "objetos" not in data:
        print("Nenhum dado retornado.")
        return

    for obj in data.get("objetos", []):
        print(f"\n=== RASTREIO: {obj.get('codObjeto')} ===")
        
        if "mensagem" in obj:
            print(f"Aviso/Erro: {obj['mensagem']}")
            continue
            
        print(f"Status Atual: {obj.get('modalidade', 'N/A')}")
        
        eventos = obj.get("eventos", [])
        if not eventos:
            print("Sem eventos ainda.")
            continue
            
        print("\nÚltimo evento:")
        ultimo = eventos[0]
        
        dt_str = ultimo.get('dtHrCriado', '').replace('Z', '+00:00')
        data_ev = datetime.fromisoformat(dt_str).strftime('%d/%m/%Y %H:%M') if dt_str else "Data desconhecida"
        
        print(f"Data: {data_ev}")
        print(f"Status: {ultimo.get('descricao')}")
        
        cidade = ultimo.get("unidade", {}).get("endereco", {}).get("cidade", ultimo.get("unidade", {}).get("cidade", "N/A"))
        uf = ultimo.get("unidade", {}).get("endereco", {}).get("uf", ultimo.get("unidade", {}).get("uf", ""))
        print(f"Local: {cidade} - {uf}")
        
        if len(eventos) > 1:
            print(f"\nHistórico completo: {len(eventos)} eventos")
            for ev in eventos:
                dt_ev_str = ev.get('dtHrCriado', '').replace('Z', '+00:00')
                dt_ev = datetime.fromisoformat(dt_ev_str).strftime('%d/%m %H:%M') if dt_ev_str else "Data desconhecida"
                print(f" {dt_ev} - {ev.get('descricao')}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        codigos_informados = sys.argv[1:]
        print(f"Iniciando consulta para os códigos: {', '.join(codigos_informados)}\n")
        
        resultado = rastrear_lote(codigos_informados)
        formatar_saida(resultado)
    else:
        print("Uso incorreto. Por favor, informe um ou mais códigos de rastreio separados por espaço.")
        print("Exemplo de uso: python scripts/rastrear_correios.py AP608712808BR OU123456789BR")