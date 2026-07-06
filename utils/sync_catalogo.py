# ==============================================================================
# PROJETO: MyGames - Backoffice
# MÓDULO: sync_catalogo.py (Pasta: utils)
# DATA DE CRIAÇÃO: 27/06/2026
# TÍTULO: ETL de Sincronização de Catálogo (Supabase -> MySQL) - OTIMIZADO
# FUNÇÃO: Processo batch (lote) autônomo para sincronização de catálogo.
#
# HISTÓRICO DE ALTERAÇÕES:
# - 27/06/2026: Criação do script de sincronização ETL.
# - 03/07/2026: Correção na função classificar_categoria invertendo os IDs 
#               de Jogos (para 4) e Acessórios (para 3) para alinhar com o banco local.
# - 06/07/2026: Inclusão do campo 'plataforma' no bloco ON DUPLICATE KEY UPDATE
#               para garantir a atualização da marca/console na base local.
# ==============================================================================

import os
import requests
import logging
import mysql.connector
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()

# Configuração de log
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [SYNC CATÁLOGO] %(levelname)s - %(message)s'
)

def conectar_bd():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        database=os.getenv("DB_NAME")
    )

def classificar_categoria(nome_produto):
    nome_lower = nome_produto.lower()
    if 'jogo' in nome_lower or 'jogos' in nome_lower:
        return 4  # CORRIGIDO: Agora retorna 4 para Jogos
    elif 'controle' in nome_lower or 'navigator' in nome_lower or 'move' in nome_lower:
        return 2
    elif any(acessorio in nome_lower for acessorio in ['camera', 'kinect', 'volante', 'vr', 'câmbio', 'óculos', 'portal']):
        return 3  # CORRIGIDO: Agora retorna 3 para Acessórios
    else:
        return 1

def extrair_dados_supabase():
    """
    Busca os dados do Supabase utilizando as credenciais do .env.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    modo_simulado = os.getenv("SYNC_MODO_SIMULADO", "1") == "1"

    if modo_simulado:
        logging.info("MODO SIMULADO ATIVO: Usando conjunto de dados de teste.")
        return [
            {"id": "02eb07a6-8631-4673-82d8-46cdcd2c40b3", "marca": "Sony", "categoria": "PlayStation 4", "nome": "Jogos Top", "valor_compra": "20.00", "valor_troca": "20.00", "valor_venda": "0.00", "ativo": False},
            {"id": "05363631-6568-434e-badd-b735d3bc1139", "marca": "Sony", "categoria": "PlayStation 5", "nome": "Camera PlayStation 5", "valor_compra": "150.00", "valor_troca": "170.00", "valor_venda": "299.00", "ativo": True}
        ]
        
    try:
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        resposta = requests.get(f"{url}/rest/v1/produtos?select=*", headers=headers, timeout=30)
        
        if resposta.status_code == 200:
            logging.info("Dados extraídos do Supabase com sucesso.")
            return resposta.json()
        else:
            logging.error(f"Erro na API do Supabase: HTTP {resposta.status_code} - {resposta.text}")
            return []
            
    except Exception as e:
        logging.error(f"Erro de conexão com o Supabase: {e}")
        return []

def sincronizar_catalogo():
    logging.info("Iniciando rotina de sincronização de catálogo (ETL)...")
    
    produtos_externos = extrair_dados_supabase()
    if not produtos_externos:
        logging.warning("Nenhum produto recuperado. Abortando sincronização.")
        return

    db = conectar_bd()
    try:
        cursor = db.cursor()
        
        # 1. Preparar os dados para o executemany (Lista de Tuplas)
        dados_lote = []
        skus_processados = []

        for prod in produtos_externos:
            sku_interno = prod.get('id')
            if not sku_interno: continue
                
            skus_processados.append(sku_interno)
            nome_prod = prod.get('nome', 'Produto Desconhecido')
            cat_id = classificar_categoria(nome_prod)
            ativo = 1 if prod.get('ativo') else 0
            
            v_venda = Decimal(str(prod.get('valor_venda', '0.00')))
            v_pix = Decimal(str(prod.get('valor_compra', '0.00')))
            v_cred = Decimal(str(prod.get('valor_troca', '0.00')))
            plataforma = prod.get('marca', 'Outros')

            # Tupla alinhada com a query (INSERTS)
            dados_lote.append((
                nome_prod, cat_id, plataforma, v_venda, v_pix, v_cred, ativo, sku_interno
            ))

        # 2. Executar UPSERT em lote
        # IMPORTANTE: A coluna sku_interno DEVE ter uma restrição UNIQUE no MySQL para o UPSERT funcionar.
        query_upsert = """
            INSERT INTO catalogo_mestre 
                (nome_produto, categoria_id, plataforma, valor_venda_ref, valor_pix_base, valor_cred_base, ativo, sku_interno) 
            VALUES 
                (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                nome_produto = VALUES(nome_produto),
                categoria_id = VALUES(categoria_id),
                plataforma = VALUES(plataforma),
                valor_venda_ref = VALUES(valor_venda_ref),
                valor_pix_base = VALUES(valor_pix_base),
                valor_cred_base = VALUES(valor_cred_base),
                ativo = VALUES(ativo)
        """
        
        logging.info(f"Enviando {len(dados_lote)} registros para UPSERT no banco...")
        cursor.executemany(query_upsert, dados_lote)

        # 3. Desativar SKUs que não vieram no payload (Soft Delete em chunks)
        if skus_processados:
             logging.info("Processando soft delete de itens ausentes no payload...")
             chunk_size = 1000
             for i in range(0, len(skus_processados), chunk_size):
                 chunk = skus_processados[i:i + chunk_size]
                 format_strings = ','.join(['%s'] * len(chunk))
                 query_desativacao = f"""
                     UPDATE catalogo_mestre 
                     SET ativo = 0 
                     WHERE sku_interno IS NOT NULL 
                     AND sku_interno NOT IN ({format_strings})
                 """
                 cursor.execute(query_desativacao, tuple(chunk))

        db.commit()
        logging.info("Sincronização concluída com sucesso!")

    except mysql.connector.Error as err:
        db.rollback()
        logging.error(f"Erro no banco de dados: {err}")
    except Exception as e:
        db.rollback()
        logging.error(f"Erro inesperado durante a persistência: {e}")
    finally:
        if db.is_connected():
            cursor.close()
            db.close()

if __name__ == "__main__":
    sincronizar_catalogo()