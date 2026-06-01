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
# - 01/06/2026: Inclusão de tratamento de erro para JSON de fotos e validação 
#               de existência de arquivos físicos no servidor.
# - 01/06/2026: Correção da decodificação dupla do JSON para suportar conversão 
#               nativa do tipo JSON pelo mysql-connector.
# - 01/06/2026: Modificação do diretório base e da rota de URL para ler arquivos 
#               de uma pasta externa (volume compartilhado) configurada via .env.
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
    
    # Busca dados unindo cliente e protocolo
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
    
    # JOIN para buscar o NOME DO PRODUTO no catalogo_mestre
    query = """
        SELECT i.id, i.quantidade, i.fotos_json, i.valor_pix_unitario, i.comentarios,
               cm.nome_produto
        FROM itens_periciados i
        JOIN catalogo_mestre cm ON i.produto_id = cm.id
        WHERE i.protocolo_id = %s
    """
    cursor.execute(query, (protocolo_id,))
    itens = cursor.fetchall()
    
    # Lê a pasta compartilhada a partir do .env (onde o Site salva as fotos reais)
    PASTA_PERICIA = os.getenv("DIRETORIO_UPLOADS_PERICIA")
    
    # Processa o JSON das fotos para cada item e valida a presença física do arquivo
    for item in itens:
        fotos_validadas = []
        fotos_raw = item.get('fotos_json')
        nomes_fotos = []
        
        # Teste de JSON: Verifica se o campo não é nulo ou vazio
        if fotos_raw:
            # 1. Se o banco já converteu para Lista Python automaticamente (tipo JSON nativo)
            if isinstance(fotos_raw, list):
                nomes_fotos = fotos_raw
            
            # 2. Se o banco enviou como Texto/String, tentamos decodificar
            elif isinstance(fotos_raw, str):
                try:
                    nomes_fotos = json.loads(fotos_raw)
                except json.JSONDecodeError:
                    nomes_fotos = []

        # Garante que temos uma lista válida para iterar e montar os caminhos
        if isinstance(nomes_fotos, list):
            for nome_foto in nomes_fotos:
                
                # Previne erro caso a variável do .env não tenha sido configurada
                if PASTA_PERICIA:
                    # Caminho das imagens: Monta o caminho do arquivo no sistema
                    caminho_fisico = os.path.join(PASTA_PERICIA, nome_foto)
                    # Valida se o nome do banco bate com o arquivo físico na pasta
                    arquivo_existe = os.path.exists(caminho_fisico)
                else:
                    arquivo_existe = False
                
                fotos_validadas.append({
                    'nome': nome_foto,
                    'existe_no_disco': arquivo_existe,
                    # Agora aponta para a rota do Flask que lê a pasta externa
                    'url_estatica': f'/media/pericia/{nome_foto}' if arquivo_existe else None
                })

        # Mantém compatibilidade com a chave antiga (apenas lista de strings)
        item['fotos_lista'] = [f['nome'] for f in fotos_validadas]
        
        # Nova chave estruturada com os metadados de validação física para o template/server
        item['fotos_validadas'] = fotos_validadas
        
    cursor.close()
    db.close()
    return itens