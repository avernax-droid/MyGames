# ==============================================================================
# PROJETO: MyGames - Backoffice
# MÓDULO: admin_engine.py
# DATA DE CRIAÇÃO: 30/05/2026
# FUNÇÃO: Motor de persistência e regras de negócio do painel administrativo.
# Centraliza a execução de queries SQL complexas e o isolamento da camada de dados.
#
# HISTÓRICO DE ALTERAÇÕES:
# - 30/05/2026: Criação do motor de dados com as funções de busca de protocolo.
# - 01/06/2026: Adição das funções de CRUD para a gestão do Catálogo Mestre.
# - 01/06/2026: Correção das funções de persistência para a tabela regioes_atendimento.
# - 04/06/2026: Atualização no CRUD do catálogo para suportar gravação da coluna foto_oficial_url.
# - 04/06/2026: Adição da função buscar_produtos_por_nome para alimentar o auto-completar inteligente.
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

# [Funções de Protocolo]
def obter_cabecalho_protocolo(protocolo_id):
    db = conectar_bd()
    cursor = db.cursor(dictionary=True)
    query = "SELECT p.id, p.numero_protocolo, p.status, c.nome_completo as cliente_nome, c.whatsapp as cliente_whatsapp, c.chave_pix FROM protocolos_recompra p JOIN clientes_usuarios c ON p.cliente_id = c.id WHERE p.id = %s"
    cursor.execute(query, (protocolo_id,))
    resultado = cursor.fetchone()
    cursor.close()
    db.close()
    return resultado

def obter_itens_protocolo(protocolo_id):
    db = conectar_bd()
    cursor = db.cursor(dictionary=True)
    query = "SELECT i.id, i.quantidade, i.fotos_json, i.valor_pix_unitario, i.comentarios, cm.nome_produto FROM itens_periciados i JOIN catalogo_mestre cm ON i.produto_id = cm.id WHERE i.protocolo_id = %s"
    cursor.execute(query, (protocolo_id,))
    itens = cursor.fetchall()
    cursor.close()
    db.close()
    return itens

# [Funções do Catálogo Mestre]
def obter_catalogo_completo():
    db = conectar_bd()
    cursor = db.cursor(dictionary=True)
    query = "SELECT id, nome_produto, categoria_id, plataforma, valor_venda_ref, valor_pix_base, valor_cred_base, ativo, foto_oficial_url FROM catalogo_mestre ORDER BY nome_produto ASC"
    cursor.execute(query)
    resultados = cursor.fetchall()
    cursor.close()
    db.close()
    return resultados

def buscar_produtos_por_nome(termo):
    db = conectar_bd()
    cursor = db.cursor(dictionary=True)
    query = """
        SELECT id, nome_produto, categoria_id, plataforma, 
               valor_venda_ref, valor_pix_base, valor_cred_base, 
               ativo, foto_oficial_url 
        FROM catalogo_mestre 
        WHERE nome_produto LIKE %s 
        ORDER BY nome_produto ASC LIMIT 10
    """
    cursor.execute(query, (f"%{termo}%",))
    resultados = cursor.fetchall()
    cursor.close()
    db.close()
    return resultados

def obter_categorias():
    return [{'id': 1, 'nome_categoria': 'Consoles'}, {'id': 2, 'nome_categoria': 'Controles'}, {'id': 3, 'nome_categoria': 'Jogos Físicos'}, {'id': 4, 'nome_categoria': 'Acessórios'}]

def salvar_produto_catalogo(produto_id, nome, categoria, plataforma, valor_venda, valor_pix, valor_cred, ativo, foto_url=None):
    db = conectar_bd()
    cursor = db.cursor()
    try:
        if produto_id:
            if foto_url:
                query = "UPDATE catalogo_mestre SET nome_produto = %s, categoria_id = %s, plataforma = %s, valor_venda_ref = %s, valor_pix_base = %s, valor_cred_base = %s, ativo = %s, foto_oficial_url = %s WHERE id = %s"
                cursor.execute(query, (nome, categoria, plataforma, valor_venda, valor_pix, valor_cred, ativo, foto_url, produto_id))
            else:
                query = "UPDATE catalogo_mestre SET nome_produto = %s, categoria_id = %s, plataforma = %s, valor_venda_ref = %s, valor_pix_base = %s, valor_cred_base = %s, ativo = %s WHERE id = %s"
                cursor.execute(query, (nome, categoria, plataforma, valor_venda, valor_pix, valor_cred, ativo, produto_id))
        else:
            query = "INSERT INTO catalogo_mestre (nome_produto, categoria_id, plataforma, valor_venda_ref, valor_pix_base, valor_cred_base, ativo, foto_oficial_url) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
            cursor.execute(query, (nome, categoria, plataforma, valor_venda, valor_pix, valor_cred, ativo, foto_url))
            
        db.commit()
        sucesso = True
    except mysql.connector.Error as err:
        print(f"Erro ao salvar produto: {err}")
        db.rollback()
        sucesso = False
    finally:
        cursor.close()
        db.close()
    return sucesso

# [Funções de Gestão de Regiões]
def obter_todas_regioes():
    db = conectar_bd()
    cursor = db.cursor(dictionary=True)
    query = "SELECT id, cidade, estado_uf, multiplicador_preco, ativo FROM regioes_atendimento ORDER BY cidade ASC"
    cursor.execute(query)
    resultados = cursor.fetchall()
    cursor.close()
    db.close()
    return resultados

def salvar_regiao(regiao_id, cidade, estado_uf, multiplicador_preco, ativo):
    db = conectar_bd()
    cursor = db.cursor()
    try:
        if regiao_id:
            query = """
                UPDATE regioes_atendimento 
                SET cidade = %s, estado_uf = %s, multiplicador_preco = %s, ativo = %s
                WHERE id = %s
            """
            cursor.execute(query, (cidade, estado_uf, multiplicador_preco, ativo, regiao_id))
        else:
            query = """
                INSERT INTO regioes_atendimento (cidade, estado_uf, multiplicador_preco, ativo)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(query, (cidade, estado_uf, multiplicador_preco, ativo))
            
        db.commit()
        sucesso = True
    except mysql.connector.Error as err:
        print(f"Erro ao salvar região: {err}")
        db.rollback()
        sucesso = False
    finally:
        cursor.close()
        db.close()
    return sucesso