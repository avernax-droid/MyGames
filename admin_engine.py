# ==============================================================================
# PROJETO: MyGames - Backoffice
# MÓDULO: admin_engine.py
# DATA DE CRIAÇÃO: 30/05/2026
# FUNÇÃO: Motor de persistência e regras de negócio do painel administrativo.
# Centraliza a execução de queries SQL complexas e o isolamento da camada de dados.
#
# HISTÓRICO DE ALTERAÇÕES:
# - 30/05/2026: Criação do motor de dados com as funções de busca de protocolo.
# - 30/05/2026: Correção de JOINs para alinhar com a estrutura normalizada do banco.
# ==============================================================================

import mysql.connector
import os
import json
from dotenv import load_dotenv

load_dotenv()

def conectar_bd():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        database=os.getenv("DB_NAME")
    )

def obter_cabecalho_protocolo(protocolo_id):
    db = conectar_bd()
    cursor = db.cursor(dictionary=True)
    
    # Busca dados unindo cliente e protocolo [cite: 57, 108]
    query = """
        SELECT p.id, p.numero_protocolo, p.status, 
               c.nome_completo as cliente_nome, c.whatsapp as cliente_whatsapp, c.chave_pix
        FROM protocolos_recompra p
        JOIN clientes_usuarios c ON p.cliente_id = c.id
        WHERE p.id = %s
    """
    cursor.execute(query, (protocolo_id,))
    resultado = cursor.fetchone()
    
    cursor.close()
    db.close()
    return resultado

def obter_itens_protocolo(protocolo_id):
    db = conectar_bd()
    cursor = db.cursor(dictionary=True)
    
    # JOIN para buscar o NOME DO PRODUTO no catalogo_mestre [cite: 45, 90]
    query = """
        SELECT i.id, i.quantidade, i.fotos_json, i.valor_pix_unitario, i.comentarios,
               cm.nome_produto
        FROM itens_periciados i
        JOIN catalogo_mestre cm ON i.produto_id = cm.id
        WHERE i.protocolo_id = %s
    """
    cursor.execute(query, (protocolo_id,))
    itens = cursor.fetchall()
    
    # Processa o JSON das fotos para cada item
    for item in itens:
        item['fotos_lista'] = json.loads(item['fotos_json']) if item['fotos_json'] else []
        
    cursor.close()
    db.close()
    return itens