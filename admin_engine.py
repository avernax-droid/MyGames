# ==============================================================================
# PROJETO: MyGames - Backoffice
# MÓDULO: admin_engine.py
# DATA DE CRIAÇÃO: 30/05/2026
# TÍTULO: Motor de Regras e Integração de Banco de Dados
# FUNÇÃO: Motor de persistência e regras de negócio do painel administrativo.
# Centraliza a execução de queries SQL complexas e o isolamento da camada de dados.
#
# HISTÓRICO DE ALTERAÇÕES:
# - 30/05/2026: Criação do motor de dados com as funções de busca de protocolo.
# - 01/06/2026: Adição das funções de CRUD para a gestão do Catálogo Mestre.
# - 01/06/2026: Correção das funções de persistência para a tabela regioes_atendimento.
# - 04/06/2026: Atualização no CRUD do catálogo para suportar gravação da coluna foto_oficial_url.
# - 04/06/2026: Adição da função buscar_produtos_por_nome para alimentar o auto-completar inteligente.
# - 10/06/2026: Atualização da função obter_cabecalho_protocolo com LEFT JOIN de status.
# - 10/06/2026: Criação das funções buscar_status_ativos e atualizar_status_protocolo 
#               para suportar o novo workflow (Esteira) de Gestão de Protocolos.
# - 10/06/2026: Adição de obter_resumo_esteira e obter_protocolos_por_status para painel de gavetas.
# - 10/06/2026: Inclusão do campo valor_total_pix na query de obter_cabecalho_protocolo.
# - 11/06/2026: Correção em obter_itens_protocolo (LEFT JOIN e Alias de colunas) para interface Cockpit.
# - 11/06/2026: Atualização em atualizar_status_protocolo para suportar persistência do valor_avaliado.
# - 11/06/2026: Inclusão do campo valor_avaliado na query de obter_cabecalho_protocolo.
# - 11/06/2026: Correção em obter_protocolos_por_status (LEFT JOIN clientes_usuarios) para evitar sumiço de dados.
# - 11/06/2026: Adição de obter_todos_protocolos_listagem para integrar com template de listagem.
# - 12/06/2026: Implementação de filtro em obter_todos_protocolos_listagem para ocultar protocolos encerrados (ID 9).
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

# [Funções de Protocolo e Esteira de Status]
def obter_cabecalho_protocolo(protocolo_id):
    db = conectar_bd()
    if not db: return None
    try:
        cursor = db.cursor(dictionary=True)
        query = """
            SELECT p.id, p.numero_protocolo, p.status, p.status_id, p.laudo_tecnico, p.valor_total_pix, p.valor_avaliado,
                   c.nome_completo as cliente_nome, c.whatsapp as cliente_whatsapp, c.chave_pix,
                   s.nome_exibicao as status_nome, s.cor_badge, s.slug_tecnico
            FROM protocolos_recompra p 
            JOIN clientes_usuarios c ON p.cliente_id = c.id 
            LEFT JOIN status_protocolos s ON p.status_id = s.id
            WHERE p.id = %s
        """
        cursor.execute(query, (protocolo_id,))
        resultado = cursor.fetchone()
        return resultado
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

def obter_todos_protocolos_listagem():
    db = conectar_bd()
    if not db: return []
    try:
        cursor = db.cursor(dictionary=True)
        query = """
            SELECT p.id, p.numero_protocolo, p.valor_total_pix, p.data_criacao,
                   c.nome_completo as cliente_nome, 
                   c.whatsapp as cliente_telefone,
                   s.nome_exibicao as status_nome, 
                   s.cor_badge
            FROM protocolos_recompra p 
            LEFT JOIN clientes_usuarios c ON p.cliente_id = c.id 
            LEFT JOIN status_protocolos s ON p.status_id = s.id
            WHERE p.status_id IS NULL OR p.status_id <> 9
            ORDER BY p.data_criacao DESC
        """
        cursor.execute(query)
        return cursor.fetchall()
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

def obter_itens_protocolo(protocolo_id):
    db = conectar_bd()
    if not db: return []
    try:
        cursor = db.cursor(dictionary=True)
        query = """
            SELECT 
                i.id, 
                i.quantidade, 
                i.fotos_json, 
                i.valor_pix_unitario, 
                i.comentarios AS descricao_estado, 
                cm.nome_produto,
                CASE cm.categoria_id
                    WHEN 1 THEN 'Consoles'
                    WHEN 2 THEN 'Controles'
                    WHEN 3 THEN 'Jogos Físicos'
                    WHEN 4 THEN 'Acessórios'
                    ELSE 'Produto'
                END AS categoria
            FROM itens_periciados i 
            LEFT JOIN catalogo_mestre cm ON i.produto_id = cm.id 
            WHERE i.protocolo_id = %s
        """
        cursor.execute(query, (protocolo_id,))
        itens = cursor.fetchall()
        return itens
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

def buscar_status_ativos():
    db = conectar_bd()
    if not db: return []
    try:
        cursor = db.cursor(dictionary=True, buffered=True)
        cursor.execute("""
            SELECT id, slug_tecnico, nome_exibicao, cor_badge 
            FROM status_protocolos 
            WHERE ativo = 1 
            ORDER BY id
        """)
        return cursor.fetchall()
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

def atualizar_status_protocolo(protocolo_id, status_id, laudo_tecnico, valor_avaliado=None):
    db = conectar_bd()
    if not db: return False
    try:
        cursor = db.cursor()
        if valor_avaliado is not None:
            query = """
                UPDATE protocolos_recompra 
                SET status_id = %s, laudo_tecnico = %s, valor_avaliado = %s
                WHERE id = %s
            """
            cursor.execute(query, (status_id, laudo_tecnico, valor_avaliado, protocolo_id))
        else:
            query = """
                UPDATE protocolos_recompra 
                SET status_id = %s, laudo_tecnico = %s 
                WHERE id = %s
            """
            cursor.execute(query, (status_id, laudo_tecnico, protocolo_id))
            
        db.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Erro ao atualizar status do protocolo: {err}")
        db.rollback()
        return False
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

def obter_resumo_esteira():
    db = conectar_bd()
    if not db: return []
    try:
        cursor = db.cursor(dictionary=True)
        query = """
            SELECT s.id, s.nome_exibicao, s.cor_badge, COUNT(p.id) as total
            FROM status_protocolos s
            LEFT JOIN protocolos_recompra p ON s.id = p.status_id
            WHERE s.ativo = 1
            GROUP BY s.id, s.nome_exibicao, s.cor_badge
            ORDER BY s.id
        """
        cursor.execute(query)
        return cursor.fetchall()
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

def obter_protocolos_por_status(status_id):
    db = conectar_bd()
    if not db: return []
    try:
        cursor = db.cursor(dictionary=True)
        query = """
            SELECT p.id, p.numero_protocolo, p.valor_total_pix, p.data_criacao,
                   IFNULL(c.nome_completo, 'Cliente Não Vinculado') as cliente_nome,
                   s.nome_exibicao as status_nome
            FROM protocolos_recompra p 
            LEFT JOIN clientes_usuarios c ON p.cliente_id = c.id 
            LEFT JOIN status_protocolos s ON p.status_id = s.id
            WHERE p.status_id = %s
            ORDER BY p.data_criacao ASC
        """
        cursor.execute(query, (status_id,))
        return cursor.fetchall()
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

# [Funções do Catálogo Mestre]
def obter_catalogo_completo():
    db = conectar_bd()
    if not db: return []
    try:
        cursor = db.cursor(dictionary=True)
        query = "SELECT id, nome_produto, categoria_id, plataforma, valor_venda_ref, valor_pix_base, valor_cred_base, ativo, foto_oficial_url FROM catalogo_mestre ORDER BY nome_produto ASC"
        cursor.execute(query)
        resultados = cursor.fetchall()
        return resultados
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

def buscar_produtos_por_nome(termo):
    db = conectar_bd()
    if not db: return []
    try:
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
        return resultados
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

def obter_categorias():
    return [{'id': 1, 'nome_categoria': 'Consoles'}, {'id': 2, 'nome_categoria': 'Controles'}, {'id': 3, 'nome_categoria': 'Jogos Físicos'}, {'id': 4, 'nome_categoria': 'Acessórios'}]

def salvar_produto_catalogo(produto_id, nome, categoria, plataforma, valor_venda, valor_pix, valor_cred, ativo, foto_url=None):
    db = conectar_bd()
    if not db: return False
    try:
        cursor = db.cursor()
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
        return True
    except mysql.connector.Error as err:
        print(f"Erro ao salvar produto: {err}")
        db.rollback()
        return False
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

# [Funções de Gestão de Regiões]
def obter_todas_regioes():
    db = conectar_bd()
    if not db: return []
    try:
        cursor = db.cursor(dictionary=True)
        query = "SELECT id, city, estado_uf, multiplicador_preco, ativo FROM regioes_atendimento ORDER BY cidade ASC"
        cursor.execute(query)
        resultados = cursor.fetchall()
        return resultados
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

def salvar_regiao(regiao_id, cidade, estado_uf, multiplicador_preco, ativo):
    db = conectar_bd()
    if not db: return False
    try:
        cursor = db.cursor()
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
        return True
    except mysql.connector.Error as err:
        print(f"Erro ao salvar região: {err}")
        db.rollback()
        return False
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()