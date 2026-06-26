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
# - 12/06/2026: Atualização em obter_cabecalho_protocolo para buscar data_status_atual da tabela de histórico.
# - 12/06/2026: Adição do parâmetro admin_id e injeção do INSERT na tabela historico_status_protocolo.
# - 15/06/2026: Adição das funções de persistência (get_categorias, upsert_categoria) para a tabela categorias.
# - 15/06/2026: Adição das funções de persistência (get_canais, upsert_canal) para a tabela canais_aquisicao.
# - 15/06/2026: Correção no schema de canais_aquisicao (nome_exibicao) e geração automática de slug_tecnico.
# - 15/06/2026: Adição das funções de persistência (obter_todos_status, upsert_status) para status_protocolos.
# - 15/06/2026: Adição das funções de persistência (obter_todas_perguntas, upsert_pergunta) para perguntas_conservacao.
# - 15/06/2026: Adição das funções 'obter_opcoes_estado' e 'upsert_opcao_estado'.
# - 15/06/2026: Correção na query SQL de 'upsert_opcao_estado' para utilizar a coluna 'descricao' em vez de 'nome_estado'.
# - 15/06/2026: Adição das funções obter_todos_usuarios, atualizar_permissoes_usuario e registrar_novo_usuario 
#               para suportar o fluxo de Auto-Cadastro e Aprovação de Usuários Admin.
# - 15/06/2026: Adição das funções obter_dados_empresa e salvar_dados_empresa para gerenciar os dados corporativos.
# - 20/06/2026: Implementação de sanitização de dados (remoção de máscaras) na função salvar_dados_empresa.
# - 25/06/2026: Adição da função enviar_email_recuperacao para suporte ao fluxo de recuperação de senha via SMTP.
# - 25/06/2026: Inclusão do cliente_email na query e nova função enviar_email_status_pericia para notificar o usuário final.
# - 25/06/2026: Adição de trava em enviar_email_status_pericia para forçar o valor = 0 caso o status seja Negado ou Recusado.
# - 25/06/2026: Inclusão da biblioteca werkzeug.security e das funções validar_senha_atual e atualizar_senha_usuario.
# - 26/06/2026: Dinamização do nome fantasia (via obter_dados_empresa) nos cabeçalhos e assinaturas de e-mail.
# - 26/06/2026: Conversão dos templates de e-mail de status (Aprovado, Parcial e Negado) para HTML rico com busca de itens do protocolo.
# ==============================================================================

import mysql.connector
import os
import json
import re
import unicodedata
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr 
from dotenv import load_dotenv
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

def conectar_bd():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        database=os.getenv("DB_NAME")
    )

# --- SERVIÇOS DE E-MAIL ---
def enviar_email_recuperacao(destinatario, nova_senha):
    """
    Envia a senha provisória via SMTP utilizando credenciais do .env.
    """
    try:
        # Busca o nome fantasia da empresa para injetar no e-mail
        dados_empresa = obter_dados_empresa()
        nome_empresa = dados_empresa['nome_fantasia'] if dados_empresa and 'nome_fantasia' in dados_empresa else "MyGames"

        sender_email = os.getenv("EMAIL_USER")
        sender_password = os.getenv("EMAIL_PASS")
        smtp_server = os.getenv("EMAIL_HOST")
        smtp_port = int(os.getenv("EMAIL_PORT", 587))

        msg = MIMEMultipart()
        msg['From'] = formataddr((nome_empresa, sender_email))
        msg['To'] = destinatario
        msg['Subject'] = f"{nome_empresa} - Recuperação de Senha Administrativa"

        corpo = f"""
        Olá,
        
        Recebemos uma solicitação de redefinição de senha para sua conta administrativa.
        
        Sua senha provisória é: {nova_senha}
        
        Por favor, acesse o painel e altere sua senha imediatamente após o primeiro login.
        
        Atenciosamente,
        Equipe {nome_empresa}
        """
        
        msg.attach(MIMEText(corpo, 'plain'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Erro ao enviar e-mail de recuperação: {e}")
        return False

def enviar_email_status_pericia(destinatario, nome_cliente, numero_protocolo, status_nome, laudo_tecnico, valor_avaliado):
    """
    Envia notificação em HTML ao usuário sobre a decisão da perícia técnica.
    Formata o e-mail dinamicamente para Aprovado, Reprovado ou Parcialmente Aprovado.
    """
    try:
        dados_empresa = obter_dados_empresa()
        nome_empresa = dados_empresa['nome_fantasia'] if dados_empresa and 'nome_fantasia' in dados_empresa else "MyGames"

        sender_email = os.getenv("EMAIL_USER")
        sender_password = os.getenv("EMAIL_PASS")
        smtp_server = os.getenv("EMAIL_HOST")
        smtp_port = int(os.getenv("EMAIL_PORT", 587))

        # Normaliza o status para realizar a regra de negócio com segurança
        slug_status = unicodedata.normalize('NFKD', status_nome).encode('ASCII', 'ignore').decode('utf-8').lower()

        # Tratamento seguro para quebra de linhas do HTML
        laudo_formatado = laudo_tecnico.replace('\n', '<br>') if laudo_tecnico else 'Não informado.'

        # REGRA DE NEGÓCIO: Se for negado/recusado, zera o valor exibido no e-mail
        if 'negado' in slug_status or 'recusado' in slug_status or 'reprovado' in slug_status:
            valor_avaliado = 0.0

        # BUSCA DOS ITENS DO PROTOCOLO PARA LISTAGEM NO E-MAIL
        itens_avaliados = []
        db = conectar_bd()
        if db:
            try:
                cursor = db.cursor(dictionary=True)
                cursor.execute("SELECT id FROM protocolos_recompra WHERE numero_protocolo = %s", (numero_protocolo,))
                prot = cursor.fetchone()
                if prot:
                    itens_avaliados = obter_itens_protocolo(prot['id'])
            finally:
                db.close()

        # MONTANDO A LISTA HTML DOS PRODUTOS
        html_itens = "<strong>ÍTENS INCLUÍDOS NA VENDA:</strong><br><br>"
        for item in itens_avaliados:
            nome_produto = item.get('nome_produto', 'Produto não identificado')
            valor_item = float(item.get('valor_pix_unitario', 0.0))
            
            status_item = ""
            if 'parcial' in slug_status:
                # Regra Futura: não define o status por linha no modelo parcial ainda
                status_item = ""
            elif 'negado' in slug_status or 'recusado' in slug_status or 'reprovado' in slug_status:
                status_item = " - REPROVADO"
            else:
                status_item = " - APROVADO"

            html_itens += f"<strong>Produto:</strong> {nome_produto}{status_item}<br>"
            html_itens += f"<strong>Valor:</strong> R$ {valor_item:.2f}<br><br>"


        # MONTANDO O CORPO DO E-MAIL BASEADO NO STATUS
        corpo_html = ""

        if 'parcial' in slug_status:
            corpo_html = f"""
            <div style="font-family: Arial, sans-serif; font-size: 14px; color: #333; line-height: 1.5;">
                <p>Olá {nome_cliente},</p>
                <p>Muito obrigado por realizar a venda de seu Game Usado para a <strong>{nome_empresa}</strong>!</p>
                <p>Segue seu LAUDO abaixo para finalização do seu processo de venda:</p>
                <p><strong>Protocolo:</strong> {numero_protocolo}</p>
                <p><strong>LAUDO DA PERÍCIA TÉCNICA</strong><br>{laudo_formatado}</p>
                <br>
                {html_itens}
                <p>Como pode notar no laudo, alguns de seus itens foram aprovados na perícia técnica e estão marcados como <strong>APROVADOS</strong> enquanto outros foram <strong>REPROVADOS</strong>.</p>
                <p>Nossa equipe entrará em contato com você para definirmos o que fazer com os ítens reprovados para que possamos seguir com o PAGAMENTO!</p>
                <p>Está sendo um grande prazer fazer negócio com você e tê-lo como nosso cliente.</p>
                <br>
                <p>Atenciosamente,<br>Equipe <strong>{nome_empresa}</strong></p>
            </div>
            """

        elif 'negado' in slug_status or 'recusado' in slug_status or 'reprovado' in slug_status:
            corpo_html = f"""
            <div style="font-family: Arial, sans-serif; font-size: 14px; color: #333; line-height: 1.5;">
                <p>Olá {nome_cliente},</p>
                <p>Muito obrigado por realizar a sua cotação de venda de seu Game Usado para a <strong>{nome_empresa}</strong>!</p>
                <p>Segue seu LAUDO abaixo para finalização do seu processo de venda:</p>
                <p><strong>Protocolo:</strong> {numero_protocolo}</p>
                <p><strong>LAUDO DA PERÍCIA TÉCNICA</strong><br>{laudo_formatado}</p>
                <br>
                {html_itens}
                <p>Infelizmente, <strong>TODOS</strong> os seus itens foram <strong>REPROVADOS</strong> na perícia técnica. O Laudo explica o que aconteceu.</p>
                <p>Nossa equipe entrará em contato com você para definirmos como podemos avançar com a nossa negociação ou para acertar detalhes da devolução dos produtos para você!</p>
                <br>
                <p>Atenciosamente,<br>Equipe <strong>{nome_empresa}</strong></p>
            </div>
            """

        else: # TOTALMENTE APROVADO
            corpo_html = f"""
            <div style="font-family: Arial, sans-serif; font-size: 14px; color: #333; line-height: 1.5;">
                <p>Olá {nome_cliente},</p>
                <p>Muito obrigado por realizar a venda de seu Game Usado para a <strong>{nome_empresa}</strong>!</p>
                <p>Segue seu LAUDO abaixo para finalização do seu processo de venda:</p>
                <p><strong>Protocolo:</strong> {numero_protocolo}</p>
                <p><strong>LAUDO DA PERÍCIA TÉCNICA</strong><br>{laudo_formatado}</p>
                <br>
                {html_itens}
                <p>Todos os seus itens aprovados na perícia técnica estão marcados como <strong>APROVADOS</strong> e vamos realizar o PAGAMENTO destes itens em até 48 horas úteis.</p>
                <p>Foi um grande prazer fazer negócio com você e tê-lo como nosso cliente.</p>
                <br>
                <p>Atenciosamente,<br>Equipe <strong>{nome_empresa}</strong></p>
            </div>
            """

        msg = MIMEMultipart('alternative')
        msg['From'] = formataddr((nome_empresa, sender_email))
        msg['To'] = destinatario
        msg['Subject'] = f"{nome_empresa} - Atualização do Protocolo #{numero_protocolo}"
        
        # Anexa o HTML na mensagem
        msg.attach(MIMEText(corpo_html, 'html', 'utf-8'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Erro ao enviar e-mail de status da perícia (HTML): {e}")
        return False

# [Funções de Protocolo e Esteira de Status]
def obter_cabecalho_protocolo(protocolo_id):
    db = conectar_bd()
    if not db: return None
    try:
        cursor = db.cursor(dictionary=True)
        query = """
            SELECT p.id, p.numero_protocolo, p.status, p.status_id, p.laudo_tecnico, p.valor_total_pix, p.valor_avaliado, p.data_criacao,
                   c.nome_completo as cliente_nome, c.email as cliente_email, c.whatsapp as cliente_whatsapp, c.chave_pix,
                   s.nome_exibicao as status_nome, s.cor_badge, s.slug_tecnico,
                   IFNULL(
                       (SELECT MAX(data_alteracao) FROM historico_status_protocolo WHERE protocolo_id = p.id),
                       p.data_criacao
                   ) AS data_status_atual
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

def atualizar_status_protocolo(protocolo_id, status_id, laudo_tecnico, valor_avaliado=None, admin_id=None):
    db = conectar_bd()
    if not db: return False
    try:
        cursor = db.cursor()
        
        # 1. Atualiza o status do protocolo principal
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
            
        # 2. Insere na tabela de histórico se houver admin_id e status_id preenchidos
        if admin_id and status_id:
            query_log = """
                INSERT INTO historico_status_protocolo (protocolo_id, status_id, usuario_admin_id)
                VALUES (%s, %s, %s)
            """
            cursor.execute(query_log, (protocolo_id, status_id, admin_id))
            
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
        query = "SELECT id, cidade, estado_uf, multiplicador_preco, ativo FROM regioes_atendimento ORDER BY cidade ASC"
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

# [Funções de Gestão de Categorias]
def get_categorias():
    db = conectar_bd()
    if not db: return []
    try:
        cursor = db.cursor(dictionary=True)
        query = "SELECT id, nome, ativo FROM categorias ORDER BY nome ASC"
        cursor.execute(query)
        return cursor.fetchall()
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

def upsert_categoria(cat_id, nome, ativo):
    db = conectar_bd()
    if not db: return False
    try:
        cursor = db.cursor()
        if cat_id:
            query = "UPDATE categorias SET nome = %s, ativo = %s WHERE id = %s"
            cursor.execute(query, (nome, ativo, cat_id))
        else:
            query = "INSERT INTO categorias (nome, ativo) VALUES (%s, %s)"
            cursor.execute(query, (nome, ativo))
            
        db.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Erro ao salvar categoria: {err}")
        db.rollback()
        return False
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

# [Funções de Gestão de Canais de Aquisição]
def get_canais():
    db = conectar_bd()
    if not db: return []
    try:
        cursor = db.cursor(dictionary=True)
        query = "SELECT id, nome_exibicao as nome, ativo FROM canais_aquisicao ORDER BY nome_exibicao ASC"
        cursor.execute(query)
        return cursor.fetchall()
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

def upsert_canal(canal_id, nome, ativo):
    db = conectar_bd()
    if not db: return False
    try:
        cursor = db.cursor()
        
        # Gerando o slug_tecnico dinamicamente (removendo acentos e espaços)
        slug = unicodedata.normalize('NFKD', nome).encode('ASCII', 'ignore').decode('utf-8')
        slug = re.sub(r'[^a-zA-Z0-9]+', '_', slug).strip('_').lower()
        
        if canal_id:
            query = "UPDATE canais_aquisicao SET nome_exibicao = %s, ativo = %s, slug_tecnico = %s WHERE id = %s"
            cursor.execute(query, (nome, ativo, slug, canal_id))
        else:
            query = "INSERT INTO canais_aquisicao (nome_exibicao, slug_tecnico, ativo) VALUES (%s, %s, %s)"
            cursor.execute(query, (nome, slug, ativo))
            
        db.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Erro ao salvar canal de aquisição: {err}")
        db.rollback()
        return False
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

# [Funções de Gestão de Status de Protocolos]
def obter_todos_status():
    db = conectar_bd()
    if not db: return []
    try:
        cursor = db.cursor(dictionary=True)
        query = "SELECT id, slug_tecnico, nome_exibicao, cor_badge, ativo FROM status_protocolos ORDER BY id ASC"
        cursor.execute(query)
        return cursor.fetchall()
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

def upsert_status(status_id, nome_exibicao, cor_badge, ativo):
    db = conectar_bd()
    if not db: return False
    try:
        cursor = db.cursor()
        
        # Gerando o slug_tecnico dinamicamente a partir do nome
        slug = unicodedata.normalize('NFKD', nome_exibicao).encode('ASCII', 'ignore').decode('utf-8')
        slug = re.sub(r'[^a-zA-Z0-9]+', '_', slug).strip('_').lower()
        
        if status_id:
            query = "UPDATE status_protocolos SET nome_exibicao = %s, slug_tecnico = %s, cor_badge = %s, ativo = %s WHERE id = %s"
            cursor.execute(query, (nome_exibicao, slug, cor_badge, ativo, status_id))
        else:
            query = "INSERT INTO status_protocolos (nome_exibicao, slug_tecnico, cor_badge, ativo) VALUES (%s, %s, %s, %s)"
            cursor.execute(query, (nome_exibicao, slug, cor_badge, ativo))
            
        db.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Erro ao salvar status de protocolo: {err}")
        db.rollback()
        return False
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

# [Funções de Gestão de Opções de Estado]
def obter_opcoes_estado(categoria_id):
    db = conectar_bd()
    if not db: return []
    try:
        cursor = db.cursor(dictionary=True)
        query = "SELECT * FROM opcoes_estado WHERE categoria_id = %s ORDER BY id ASC"
        cursor.execute(query, (categoria_id,))
        return cursor.fetchall()
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

def upsert_opcao_estado(id, cat_id, descricao, dep, extra):
    db = conectar_bd()
    if not db: return False
    try:
        cursor = db.cursor()
        if id:
            query = """
                UPDATE opcoes_estado 
                SET descricao = %s, fator_depreciacao = %s, valor_fixo_extra = %s 
                WHERE id = %s
            """
            cursor.execute(query, (descricao, dep, extra, id))
        else:
            query = """
                INSERT INTO opcoes_estado (categoria_id, descricao, fator_depreciacao, valor_fixo_extra) 
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(query, (cat_id, descricao, dep, extra))
        db.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Erro ao salvar opção de estado: {err}")
        db.rollback()
        return False
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

# [Funções de Gestão de Perguntas de Conservação]
def obter_todas_perguntas():
    db = conectar_bd()
    if not db: return []
    try:
        cursor = db.cursor(dictionary=True)
        query = """
            SELECT p.id, p.texto_pergunta, p.categoria_id, p.tipo_resposta, p.impacto_valor,
                   c.nome AS nome_categoria
            FROM perguntas_conservacao p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            ORDER BY c.nome, p.id
        """
        cursor.execute(query)
        return cursor.fetchall()
    except Exception as e:
        print(f"Erro ao obter perguntas: {e}")
        return []
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

def upsert_pergunta(perg_id, texto, categoria_id, tipo, impacto):
    db = conectar_bd()
    if not db: return False
    try:
        cursor = db.cursor()
        if perg_id:
            query = """
                UPDATE perguntas_conservacao 
                SET texto_pergunta = %s, categoria_id = %s, tipo_resposta = %s, impacto_valor = %s
                WHERE id = %s
            """
            cursor.execute(query, (texto, categoria_id, tipo, impacto, perg_id))
        else:
            query = """
                INSERT INTO perguntas_conservacao (texto_pergunta, categoria_id, tipo_resposta, impacto_valor)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(query, (texto, categoria_id, tipo, impacto))
        db.commit()
        return True
    except Exception as e:
        print(f"Erro no upsert da pergunta: {e}")
        db.rollback()
        return False
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

# [Funções de Gestão de Usuários Admin]
def obter_todos_usuarios():
    db = conectar_bd()
    if not db: return []
    try:
        cursor = db.cursor(dictionary=True)
        query = """
            SELECT id, nome_completo, usuario_login, email, nivel_acesso, ativo, data_criacao, ultimo_login 
            FROM usuarios_admin 
            ORDER BY nome_completo ASC
        """
        cursor.execute(query)
        return cursor.fetchall()
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

def atualizar_permissoes_usuario(usr_id, nivel_acesso, ativo):
    db = conectar_bd()
    if not db: return False
    try:
        cursor = db.cursor()
        query = """
            UPDATE usuarios_admin 
            SET nivel_acesso = %s, ativo = %s 
            WHERE id = %s
        """
        cursor.execute(query, (nivel_acesso, ativo, usr_id))
        db.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Erro ao atualizar permissões do usuário: {err}")
        db.rollback()
        return False
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

def registrar_novo_usuario(nome_completo, usuario_login, email, senha_hash):
    db = conectar_bd()
    if not db: return False
    try:
        cursor = db.cursor()
        query = """
            INSERT INTO usuarios_admin (nome_completo, usuario_login, email, senha_hash, nivel_acesso, ativo, data_criacao)
            VALUES (%s, %s, %s, %s, 'OPERADOR', 0, NOW())
        """
        cursor.execute(query, (nome_completo, usuario_login, email, senha_hash))
        db.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Erro ao registrar novo usuário: {err}")
        db.rollback()
        return False
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

def validar_senha_atual(admin_id, senha_atual):
    db = conectar_bd()
    if not db: return False
    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT senha_hash FROM usuarios_admin WHERE id = %s", (admin_id,))
        usuario = cursor.fetchone()
        
        # Verifica se o usuário existe e se a senha digitada bate com o hash salvo
        if usuario and check_password_hash(usuario['senha_hash'], senha_atual):
            return True
        return False
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

def atualizar_senha_usuario(admin_id, nova_senha):
    db = conectar_bd()
    if not db: return False
    try:
        cursor = db.cursor()
        senha_hash = generate_password_hash(nova_senha)
        
        # Atualiza a senha e retira a trava de segurança (requer_nova_senha = 0)
        query = """
            UPDATE usuarios_admin 
            SET senha_hash = %s, requer_nova_senha = 0 
            WHERE id = %s
        """
        cursor.execute(query, (senha_hash, admin_id))
        db.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Erro ao atualizar senha do usuário: {err}")
        db.rollback()
        return False
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

# [Funções de Gestão de Dados Corporativos]
def obter_dados_empresa():
    db = conectar_bd()
    if not db: return None
    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM dados_empresa WHERE id = 1")
        return cursor.fetchone()
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

def salvar_dados_empresa(dados):
    db = conectar_bd()
    if not db: return False
    try:
        # Limpeza das máscaras antes de persistir no banco (apenas números)
        if dados.get('cnpj'):
            dados['cnpj'] = re.sub(r'\D', '', str(dados['cnpj']))
        if dados.get('cep'):
            dados['cep'] = re.sub(r'\D', '', str(dados['cep']))
        if dados.get('telefone_contato'):
            dados['telefone_contato'] = re.sub(r'\D', '', str(dados['telefone_contato']))

        cursor = db.cursor()
        query = """
            INSERT INTO dados_empresa (id, razao_social, nome_fantasia, cnpj, cep, logradouro, numero, complemento, bairro, cidade, estado_uf, telefone_contato, email_contato)
            VALUES (1, %(razao_social)s, %(nome_fantasia)s, %(cnpj)s, %(cep)s, %(logradouro)s, %(numero)s, %(complemento)s, %(bairro)s, %(cidade)s, %(estado_uf)s, %(telefone_contato)s, %(email_contato)s)
            ON DUPLICATE KEY UPDATE
            razao_social = VALUES(razao_social),
            nome_fantasia = VALUES(nome_fantasia),
            cnpj = VALUES(cnpj),
            cep = VALUES(cep),
            logradouro = VALUES(logradouro),
            numero = VALUES(numero),
            complemento = VALUES(complemento),
            bairro = VALUES(bairro),
            cidade = VALUES(cidade),
            estado_uf = VALUES(estado_uf),
            telefone_contato = VALUES(telefone_contato),
            email_contato = VALUES(email_contato)
        """
        cursor.execute(query, dados)
        db.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Erro ao salvar dados da empresa: {err}")
        db.rollback()
        return False
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()