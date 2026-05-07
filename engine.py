import mysql.connector
from mysql.connector import Error
from decimal import Decimal
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def conectar_bd():
    """
    Configuração para o ambiente WSL2/Ubuntu do MyGames.
    Usa 127.0.0.1 para evitar problemas de DNS do 'localhost'.
    """
    try:
        connection = mysql.connector.connect(
            host="127.0.0.1",
            port=3307,            # Porta definida para o projeto
            user="dev_gamer",     # Usuário criado para segurança
            password="projeto123", # Senha definida no setup
            database="mygames_db" # Nome correto do schema
        )
        return connection
    except Error as e:
        print(f"ERRO CRÍTICO: Falha na conexão com o MySQL (Porta 3307): {e}")
        return None

# --- MÓDULO DE IDENTIFICAÇÃO (ETAPA 1) ---

def salvar_lead(dados):
    """
    Insere ou atualiza os dados do cliente na tabela clientes_usuarios.
    """
    db = conectar_bd()
    if not db: return None
    try:
        cursor = db.cursor(dictionary=True)
        sql = """
            INSERT INTO clientes_usuarios 
            (nome_completo, email, whatsapp, cidade, estado_nome, estado_uf, origem_lead) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
            nome_completo = VALUES(nome_completo),
            whatsapp = VALUES(whatsapp),
            cidade = VALUES(cidade),
            estado_nome = VALUES(estado_nome),
            estado_uf = VALUES(estado_uf)
        """
        valores = (dados['nome_completo'], dados['email'], dados['whatsapp'], 
                   dados['cidade'], dados['estado_nome'], dados['estado_uf'], dados['origem_lead'])
        cursor.execute(sql, valores)
        db.commit()
        
        if cursor.lastrowid:
            return cursor.lastrowid
        else:
            cursor.execute("SELECT id FROM clientes_usuarios WHERE email = %s", (dados['email'],))
            res = cursor.fetchone()
            return res['id'] if res else None
    except Error as e:
        print(f"ERRO: Falha ao persistir lead: {e}")
        return None
    finally:
        if db.is_connected():
            cursor.close()
            db.close()

# --- MÓDULO DE GESTÃO DE CLIENTES (PONTUAL PARA ETAPA 5) ---

def obter_cliente(cliente_id):
    """
    PONTUAL: Recupera todos os dados de um cliente específico para validação de cadastro.
    """
    db = conectar_bd()
    if not db: return {}
    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM clientes_usuarios WHERE id = %s", (cliente_id,))
        return cursor.fetchone() or {}
    finally:
        if db.is_connected():
            cursor.close()
            db.close()

def atualizar_cadastro_completo(cliente_id, dados):
    """
    PONTUAL: Atualiza os dados sensíveis e de endereço do cliente.
    """
    db = conectar_bd()
    if not db: return False
    try:
        cursor = db.cursor()
        sql = """
            UPDATE clientes_usuarios 
            SET cpf = %s, cep = %s, endereco = %s, numero = %s, 
                complemento = %s, bairro = %s, chave_pix = %s
            WHERE id = %s
        """
        valores = (
            dados.get('cpf'), dados.get('cep'), dados.get('endereco'),
            dados.get('numero'), dados.get('complemento'), dados.get('bairro'),
            dados.get('chave_pix'), cliente_id
        )
        cursor.execute(sql, valores)
        db.commit()
        return True
    except Error as e:
        print(f"ERRO ao atualizar cadastro: {e}")
        return False
    finally:
        if db.is_connected():
            cursor.close()
            db.close()

# --- MÓDULO DE FINALIZAÇÃO E E-MAIL ---

def enviar_email_resumo(cliente, dados_finais):
    """
    ENVIO REAL: Utiliza o servidor SMTP do Gmail para enviar o protocolo.
    PONTUAL: Alterado de simulação para envio real conforme solicitado.
    """
    try:
        # PONTUAL: Substitua pelas suas credenciais geradas no Google Account
        remetente = "avernax@gmail.com" 
        senha_app = "nmmawgxrhuyzfpoe" 
        
        destinatario = cliente['email']
        protocolo = dados_finais['protocolo']
        
        msg = MIMEMultipart()
        msg['From'] = remetente
        msg['To'] = destinatario
        msg['Subject'] = f"Confirmação de Agendamento MyGames - {protocolo}"
        
        corpo = f"""
        Olá {cliente['nome_completo']},

        Seu agendamento no MyGames foi concluído com sucesso!

        --- DETALHES DA PROPOSTA ---
        Protocolo: {protocolo}
        Item: {dados_finais['produto_nome']}
        Valor Final: R$ {dados_finais['valor_final']:.2f}
        Data da Entrega: {dados_finais['data_agendada']}
        Período: {dados_finais['periodo']}
        ----------------------------

        Nossa equipe entrará em contato em breve para os próximos passos.
        """
        msg.attach(MIMEText(corpo, 'plain'))

        # Conexão segura com o SMTP do Gmail
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remetente, senha_app)
        server.send_message(msg)
        server.quit()
        
        print(f"--- [OK] E-MAIL ENVIADO PARA: {destinatario} ---")
        return True
    except Exception as e:
        print(f"--- [ERRO] FALHA NO ENVIO REAL: {e} ---")
        return False

def finalizar_proposta(dados):
    """
    Registra o protocolo final e retorna o número gerado.
    """
    db = conectar_bd()
    if not db: return None
    try:
        cursor = db.cursor()
        
        agora = datetime.datetime.now()
        timestamp = agora.strftime("%H%M%S")
        protocolo = f"MG-{agora.year}-{dados['cliente_id']}{dados['produto_id']}-{timestamp}"
        
        sql = """
            INSERT INTO protocolos_recompra 
            (cliente_id, numero_protocolo, status, data_criacao) 
            VALUES (%s, %s, 'Aberto', NOW())
        """
        cursor.execute(sql, (dados['cliente_id'], protocolo))
        db.commit()
        
        from flask import session
        session['ultimo_protocolo'] = protocolo
        
        return protocolo
    except Error as e:
        print(f"ERRO ao finalizar proposta: {e}")
        return None
    finally:
        if db.is_connected():
            cursor.close()
            db.close()

# --- MÓDULO DE CATÁLOGO E BUSCA ---

def buscar_produtos_catalogo(termo):
    db = conectar_bd()
    if not db: return []
    try:
        cursor = db.cursor(dictionary=True)
        query = """
            SELECT id, nome_produto, plataforma, foto_oficial_url 
            FROM catalogo_mestre 
            WHERE (nome_produto LIKE %s OR plataforma LIKE %s)
            AND ativo = 1 LIMIT 10
        """
        like_termo = f"%{termo}%"
        cursor.execute(query, (like_termo, like_termo))
        return cursor.fetchall()
    finally:
        if db.is_connected():
            cursor.close()
            db.close()

# --- MÓDULO DE PERÍCIA E CÁLCULO ---

def buscar_opcoes_pericia(categoria_id=None):
    db = conectar_bd()
    if not db: return []
    try:
        cursor = db.cursor(dictionary=True)
        query = "SELECT id, descricao, fator_depreciacao FROM opcoes_estado ORDER BY exibir_ordem"
        cursor.execute(query)
        return cursor.fetchall()
    finally:
        if db.is_connected():
            cursor.close()
            db.close()

def calcular_cotacao_final(produto_id, id_opcao_estado):
    db = conectar_bd()
    if not db: return None
    try:
        cursor = db.cursor(dictionary=True)
        query = """
            SELECT c.nome_produto, c.valor_pix_base, o.descricao, o.fator_depreciacao
            FROM catalogo_mestre c
            CROSS JOIN opcoes_estado o
            WHERE c.id = %s AND o.id = %s
        """
        cursor.execute(query, (produto_id, id_opcao_estado))
        resultado = cursor.fetchone()
        if resultado:
            valor_base = Decimal(str(resultado['valor_pix_base']))
            fator = Decimal(str(resultado['fator_depreciacao']))
            valor_final = valor_base * fator
            return {
                "produto": resultado['nome_produto'],
                "estado": resultado['descricao'],
                "valor_final": float(valor_final)
            }
        return None
    finally:
        if db.is_connected():
            cursor.close()
            db.close()