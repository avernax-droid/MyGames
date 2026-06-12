# ==============================================================================
# PROJETO: MyGames
# MÓDULO: engine.py
# DATA DE CRIAÇÃO: 28/05/2026
# TÍTULO: Motor de Regras e Integração de Banco de Dados
# FUNÇÃO: Módulo core do sistema responsável por toda a camada de persistência 
# de dados (MySQL), cálculos de perícia (depreciação de valores), integração com 
# APIs externas (IBGE) e envio de comunicações automatizadas (e-mail). Orquestra 
# a lógica entre o front-end e o banco de dados.
#
# HISTÓRICO DE ALTERAÇÕES:
# - 28/05/2026: Inclusão do cabeçalho padrão de documentação.
# - 29/05/2026: Implementação do multiplicador de preço por região de atendimento.
# - 29/05/2026: Exibição do bônus/ajuste regional no corpo do e-mail de resumo.
# - 29/05/2026: Inclusão da política de avaliação física presencial no corpo do e-mail.
# - 30/05/2026: Correção na função salvar_lead com lógica de UPSERT baseada em CPF para evitar duplicação de cadastros.
# - 02/06/2026: Remoção da exibição visual do bônus regional e preços riscados no corpo do e-mail.
# - 02/06/2026: Adição da função salvar_feedback_recusa para o fluxo V2.9.
# - 02/06/2026: Inclusão do valor total do lote no início do corpo do e-mail (enviar_email_resumo).
# - 04/06/2026: Inclusão do parâmetro quantidade na função calcular_cotacao_final para multiplicação correta de múltiplos itens.
# - 09/06/2026: Implementação da função de integração com API dos Correios (Logística Reversa) para validação via log.
# - 10/06/2026: Inclusão do interceptador Mock 'fake' e integração automática da logística reversa na criação do protocolo.
# - 10/06/2026: Hotfix na função calcular_cotacao_final para corrigir digitação no nome da coluna (fator_depreciacao).
# - 10/06/2026: Formatação e inserção dos dados de logística reversa (e-ticket e rastreio) no corpo do e-mail de resumo.
# - 11/06/2026: Inclusão de status_id = 1 na função finalizar_proposta.
# ==============================================================================

import mysql.connector
from mysql.connector import Error
from decimal import Decimal
import datetime
import smtplib
import json
import requests
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()

# Configuração de log focada na validação da API dos Correios via terminal
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [CORREIOS] %(levelname)s - %(message)s')

def conectar_bd():
    try:
        connection = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT")),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            database=os.getenv("DB_NAME")
        )
        return connection
    except Error as e:
        print(f"ERRO CRÍTICO: Falha na conexão com o MySQL: {e}")
        return None

# --- MÓDULO DE IDENTIFICAÇÃO ---

def salvar_lead(dados):
    db = conectar_bd()
    if not db: return None
    try:
        cursor = db.cursor(dictionary=True, buffered=True)
        whatsapp = ''.join(filter(str.isdigit, str(dados['whatsapp'])))
        cpf = ''.join(filter(str.isdigit, str(dados.get('cpf', '')))) if dados.get('cpf') else None
        cep = ''.join(filter(str.isdigit, str(dados.get('cep', '')))) if dados.get('cep') else None

        cliente_existente_id = None

        # Passo 1: Verifica se o lead já existe pelo CPF
        if cpf:
            cursor.execute("SELECT id FROM clientes_usuarios WHERE cpf = %s LIMIT 1", (cpf,))
            res = cursor.fetchone()
            if res:
                cliente_existente_id = res['id']

        # Passo 2: UPSERT manual
        if cliente_existente_id:
            # UPDATE: Se achou, atualiza os dados para não duplicar
            sql_update = """UPDATE clientes_usuarios SET 
                            nome_completo = %s, email = %s, whatsapp = %s, 
                            cidade = %s, estado_nome = %s, estado_uf = %s, 
                            origem_lead = %s, cep = COALESCE(%s, cep)
                            WHERE id = %s"""
            cursor.execute(sql_update, (
                dados['nome_completo'], dados['email'], whatsapp, 
                dados['cidade'], dados.get('estado_nome'), dados.get('estado_uf'), 
                dados['origem_lead'], cep, cliente_existente_id
            ))
            db.commit()
            return cliente_existente_id
        else:
            # INSERT: Se não achou (ou não tem CPF ainda), cria um novo registro
            sql_insert = """INSERT INTO clientes_usuarios 
                     (nome_completo, email, whatsapp, cidade, estado_nome, estado_uf, origem_lead, cpf, cep) 
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            cursor.execute(sql_insert, (
                dados['nome_completo'], dados['email'], whatsapp, 
                dados['cidade'], dados.get('estado_nome'), dados.get('estado_uf'), 
                dados['origem_lead'], cpf, cep
            ))
            db.commit()
            return cursor.lastrowid

    except Error as e:
        print(f"ERRO: Falha ao persistir lead: {e}")
        return None
    finally:
        if db and db.is_connected(): cursor.close(); db.close()

# --- MÓDULO DE GESTÃO DE CLIENTES ---

def obter_cliente(cliente_id):
    db = conectar_bd()
    if not db: return {}
    try:
        cursor = db.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT * FROM clientes_usuarios WHERE id = %s", (cliente_id,))
        return cursor.fetchone() or {}
    finally:
        if db and db.is_connected(): cursor.close(); db.close()

def obter_cliente_por_cpf(cpf_num):
    db = conectar_bd()
    if not db: return None
    try:
        cursor = db.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT * FROM clientes_usuarios WHERE cpf = %s", (cpf_num,))
        return cursor.fetchone()
    finally:
        if db and db.is_connected(): cursor.close(); db.close()

def atualizar_cadastro_completo(cliente_id, dados):
    db = conectar_bd()
    if not db: return False
    try:
        cursor = db.cursor()
        cpf = ''.join(filter(str.isdigit, str(dados.get('cpf', ''))))
        cep = ''.join(filter(str.isdigit, str(dados.get('cep', ''))))
        whatsapp = ''.join(filter(str.isdigit, str(dados.get('whatsapp', ''))))
        sql = "UPDATE clientes_usuarios SET cpf = %s, cep = %s, whatsapp = %s, endereco = %s, numero = %s, complemento = %s, bairro = %s, chave_pix = %s WHERE id = %s"
        cursor.execute(sql, (cpf, cep, whatsapp, dados.get('endereco'), dados.get('numero'), dados.get('complemento'), dados.get('bairro'), dados.get('chave_pix'), cliente_id))
        db.commit()
        return True
    finally:
        if db and db.is_connected(): cursor.close(); db.close()

# --- MÓDULO DE PERÍCIA E CÁLCULOS ---

def obter_produto_por_id(produto_id):
    db = conectar_bd()
    if not db: return None
    try:
        cursor = db.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT * FROM catalogo_mestre WHERE id = %s", (produto_id,))
        return cursor.fetchone()
    finally:
        if db and db.is_connected(): cursor.close(); db.close()

def calcular_cotacao_final(produto_id, estado_id, multiplicador_regiao=1.00, quantidade=1):
    db = conectar_bd()
    if not db: return None
    try:
        cursor = db.cursor(dictionary=True, buffered=True)
        produto = obter_produto_por_id(produto_id)
        if not produto: return None
        
        # HOTFIX: Corrigido de factor_depreciacao para fator_depreciacao
        cursor.execute("SELECT fator_depreciacao FROM opcoes_estado WHERE id = %s", (estado_id,))
        estado = cursor.fetchone()
        
        fator_raw = estado['fator_depreciacao'] if estado and estado.get('fator_depreciacao') is not None else 1.0
        fator = Decimal(str(fator_raw).replace(',', '.'))
        multiplicador = Decimal(str(multiplicador_regiao))
        qtd = Decimal(str(quantidade))
        
        base_raw = produto['valor_pix_base'] if produto.get('valor_pix_base') is not None else 0.0
        valor_final = Decimal(str(base_raw).replace(',', '.')) * fator * multiplicador * qtd
        
        return {
            "produto": produto['nome_produto'], 
            "valor_final": float(valor_final),
            "multiplicador_aplicado": float(multiplicador_regiao),
            "quantidade_considerada": int(quantidade)
        }
    finally:
        if db and db.is_connected(): cursor.close(); db.close()

def registrar_item_periciado(protocolo_id, item):
    db = conectar_bd()
    if not db: return False
    try:
        cursor = db.cursor(dictionary=True)
        sql = "INSERT INTO itens_periciados (protocolo_id, produto_id, quantidade, fotos_json, comentarios, valor_pix_unitario, valor_cred_unitario) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        cursor.execute(sql, (protocolo_id, item['produto_id'], item.get('quantidade', 1), item.get('fotos_json'), item.get('comentarios', ''), item['valor_pix_unitario'], item['valor_cred_unitario']))
        db.commit()
        return True
    finally:
        if db and db.is_connected(): cursor.close(); db.close()

# --- MÓDULO DE FINALIZAÇÃO ---

def enviar_email_resumo(cliente, dados_email, itens_avaliados):
    try:
        remetente, senha = "avernax@gmail.com", "nmmawgxrhuyzfpoe"
        msg = MIMEMultipart()
        msg['From'], msg['To'], msg['Subject'] = remetente, cliente['email'], f"Confirmação MyGames - Protocolo {dados_email['protocolo']}"
        
        corpo = f"Olá {cliente['nome_completo']},\n\n"
        corpo += f"Protocolo: {dados_email['protocolo']}\n"
        corpo += f"Valor Total do Lote (PIX): R$ {dados_email.get('total_pix', 0.0):.2f}\n\n"
        
        # INCLUSÃO DA SEÇÃO DE LOGÍSTICA REVERSA NO CORPO DO E-MAIL
        if dados_email.get('e_ticket') or dados_email.get('codigo_rastreio'):
            corpo += "--------------------------------------------------------\n"
            corpo += "📦 DADOS DE POSTAGEM (LOGÍSTICA REVERSA):\n"
            if dados_email.get('e_ticket'):
                corpo += f" Código de Postagem (E-Ticket): {dados_email['e_ticket']}\n"
            if dados_email.get('codigo_rastreio'):
                corpo += f" Código de Rastreio dos Correios: {dados_email['codigo_rastreio']}\n"
            corpo += "\n Instruções: Embale os itens com segurança, dirija-se\n"
            corpo += " a uma agência dos Correios e informe o E-Ticket acima.\n"
            corpo += " O envio é faturado diretamente para a conta comercial\n"
            corpo += " da MyGames, sendo 100% gratuito para você.\n"
            corpo += "--------------------------------------------------------\n\n"

        tem_analise_manual = False
        
        for item in itens_avaliados:
            corpo += f"Produto: {item.get('produto_nome')}\n"
            if item.get('is_outros'):
                corpo += " Valor: Sob Consulta\n\n"
                tem_analise_manual = True
            else:
                valor_final = float(item['valor_pix_unitario'])
                corpo += f" Valor: R$ {valor_final:.2f}\n\n"
        
        if tem_analise_manual:
            corpo += "--------------------------------------------------------\n"
            corpo += "AVISO SOBRE ITENS SOB CONSULTA:\n"
            corpo += "Notamos que o seu lote contém itens que não estão cadastrados em nosso sistema padrão.\n"
            corpo += "Nossa equipe técnica avaliará as informações e fotos enviadas, e entrará em contato "
            corpo += "com você em até 24 horas úteis para apresentar a oferta final destes itens.\n"
            corpo += "--------------------------------------------------------\n\n"
            
        corpo += "--------------------------------------------------------\n"
        corpo += "POLÍTICA DE AVALIAÇÃO FÍSICA:\n"
        corpo += "Lembramos que as cotações acima são pré-avaliações baseadas nas \n"
        corpo += "informações fornecidas. A aprovação da oferta e o pagamento final \n"
        corpo += "estão sujeitos à conferência e avaliação técnica presencial pela \n"
        corpo += "nossa equipe, assim que os produtos forem recebidos em nossa \n"
        corpo += "empresa via Correios.\n"
        corpo += "--------------------------------------------------------\n\n"
        
        corpo += "Atenciosamente,\nEquipe MyGames"
            
        msg.attach(MIMEText(corpo, 'plain', 'utf-8'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls(); server.login(remetente, senha); server.send_message(msg); server.quit()
        return True
    except Exception as e: 
        print(f"Erro ao enviar email: {e}")
        return False

def finalizar_proposta(dados_proposta):
    db = conectar_bd()
    if not db: return None
    try:
        cursor = db.cursor()
        agora = datetime.datetime.now()
        protocolo = f"MG-{agora.year}-{dados_proposta['cliente_id']}-{agora.strftime('%H%M%S')}"
        
        canal_id = dados_proposta.get('canal_aquisicao_id')
        
        cliente = obter_cliente(dados_proposta['cliente_id'])
        
        dados_remetente = {
            "nome": cliente.get('nome_completo', ''),
            "cep": cliente.get('cep', ''),
            "logradouro": cliente.get('endereco', ''),
            "numero": cliente.get('numero', ''),
            "complemento": cliente.get('complemento', ''),
            "bairro": cliente.get('bairro', ''),
            "cidade": cliente.get('cidade', ''),
            "uf": cliente.get('estado_uf', ''),
            "ddd": "11",  
            "telefone": cliente.get('whatsapp', '')
        }
        
        e_ticket, codigo_rastreio = gerar_logistica_reversa(dados_remetente)
        
        # SQL ALTERADO PARA INCLUIR status_id = 1
        sql = """INSERT INTO protocolos_recompra 
                  (cliente_id, numero_protocolo, status, status_id, valor_total_pix, valor_total_credito, data_criacao, canal_aquisicao_id, e_ticket, codigo_rastreio) 
                  VALUES (%s, %s, 'Aberto', 1, %s, %s, NOW(), %s, %s, %s)"""
        
        cursor.execute(sql, (
            dados_proposta['cliente_id'], 
            protocolo, 
            dados_proposta['total_pix'], 
            dados_proposta['total_cred'], 
            canal_id,
            e_ticket,
            codigo_rastreio
        ))
        
        p_id = cursor.lastrowid
        db.commit()
        
        return {
            "id": p_id, 
            "numero": protocolo,
            "e_ticket": e_ticket,
            "codigo_rastreio": codigo_rastreio
        }
    finally:
        if db and db.is_connected(): cursor.close(); db.close()

# --- MÓDULO DE FEEDBACK E RECUSA ---

def salvar_feedback_recusa(dados):
    db = conectar_bd()
    if not db: return False
    try:
        cursor = db.cursor()
        sql = """INSERT INTO feedbacks_recusa 
                  (sessao_uuid, motivo_texto, cidade_informada, estado_uf, canal_aquisicao, 
                   valor_oferta_recusada, itens_carrinho_json, user_agent, ip_origem, data_recusa) 
                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())"""
        
        valores = (
            dados.get('sessao_uuid'),
            dados.get('motivo_texto'),
            dados.get('cidade_informada'),
            dados.get('estado_uf'),
            dados.get('canal_aquisicao'),
            dados.get('valor_oferta_recusada', 0.0),
            dados.get('itens_carrinho_json'),
            dados.get('user_agent'),
            dados.get('ip_origem')
        )
        
        cursor.execute(sql, valores)
        db.commit()
        return True
    except Error as e:
        print(f"ERRO: Falha ao salvar feedback de recusa: {e}")
        return False
    finally:
        if db and db.is_connected(): cursor.close(); db.close()

# --- MÓDULO DE BUSCA ---

def obter_multiplicador_regiao(cidade, estado_uf):
    db = conectar_bd()
    if not db: return 1.00
    try:
        cursor = db.cursor(dictionary=True, buffered=True)
        query = "SELECT multiplicador_preco FROM regioes_atendimento WHERE cidade = %s AND estado_uf = %s AND ativo = 1"
        cursor.execute(query, (cidade, estado_uf))
        res = cursor.fetchone()
        
        if res and res.get('multiplicador_preco') is not None:
            return float(res['multiplicador_preco'])
            
        return 1.00
    except Error as e:
        print(f"ERRO: Falha ao buscar multiplicador de região: {e}")
        return 1.00
    finally:
        if db and db.is_connected(): cursor.close(); db.close()

def buscar_produtos_por_categoria(categoria_id):
    db = conectar_bd()
    if not db: return []
    try:
        cursor = db.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT id, nome_produto, plataforma, foto_oficial_url, valor_pix_base FROM catalogo_mestre WHERE categoria_id = %s AND ativo = 1 ORDER BY nome_produto", (categoria_id,))
        return cursor.fetchall()
    finally:
        if db and db.is_connected(): cursor.close(); db.close()

def buscar_opcoes_pericia(categoria_id):
    db = conectar_bd()
    if not db: return []
    try:
        cursor = db.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT id, descricao FROM opcoes_estado WHERE categoria_id = %s ORDER BY exibir_ordem, id", (categoria_id,))
        return cursor.fetchall()
    finally:
        if db and db.is_connected(): cursor.close(); db.close()

def consultar_municipios_ibge():
    try:
        return requests.get("https://servicodados.ibge.gov.br/api/v1/localidades/municipios", timeout=5).json()
    except: return []

def buscar_canais_aquisicao():
    db = conectar_bd()
    if not db: return []
    try:
        cursor = db.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT id, nome_exibicao FROM canais_aquisicao WHERE ativo = 1")
        return cursor.fetchall()
    finally:
        if db and db.is_connected(): cursor.close(); db.close()

# --- INTEGRAÇÃO CORREIOS ---

def gerar_logistica_reversa(dados_remetente):
    cnpj = os.getenv('CORREIOS_CNPJ')
    contrato = os.getenv('CORREIOS_CONTRATO')
    cartao = os.getenv('CORREIOS_CARTAO_POSTAGEM')
    usuario = os.getenv('CORREIOS_USER')
    senha = os.getenv('CORREIOS_PASS')
    ambiente = os.getenv('CORREIOS_AMBIENTE', 'homologacao')
    
    # ==========================================
    # MOCK (SIMULAÇÃO DE RESPOSTA)
    # ==========================================
    if ambiente == "fake":
        logging.info("MODO FAKE ATIVADO: Simulando resposta da API dos Correios...")
        e_ticket_fake = "888888888"
        rastreio_fake = "BR987654321BR"
        logging.info(f"SUCESSO (FAKE)! E-ticket: {e_ticket_fake} | Rastreio: {rastreio_fake}")
        return e_ticket_fake, rastreio_fake

    base_url = "https://apihom.correios.com.br" if ambiente == "homologacao" else "https://api.correios.com.br"
    
    # ==========================================
    # FASE A: Autenticação (Gerando o Token)
    # ==========================================
    logging.info("Solicitando Token de Autenticação OAuth2...")
    token_url = f"{base_url}/token/v1/autentica/cartaopostagem"
    
    try:
        auth = (usuario, senha)
        payload_auth = {"numero": cartao}
        
        resp_auth = requests.post(token_url, json=payload_auth, auth=auth)
        resp_auth.raise_for_status()
        
        token = resp_auth.json().get('token')
        logging.info("Token de acesso gerado com sucesso.")
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Falha na autenticação: {e}")
        if e.response is not None:
             logging.error(f"Detalhe: {e.response.text}")
        return None, None

    # ==========================================
    # FASE B: Disparo do Payload de Logística
    # ==========================================
    logging.info("Montando e enviando payload de autorização de postagem...")
    reversa_url = f"{base_url}/logistica-reversa/v1/reversas"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "contrato": contrato,
        "cartaoPostagem": cartao,
        "destinatario": {
            "cnpj": cnpj,
            "nome": "MyGames - Laboratório de Perícia",
            "ddd": "11",
            "telefone": "999999999", 
            "cep": "02042010", 
            "logradouro": "Av Leoncio de Magalhaes",
            "numero": "179",
            "complemento": "Galpão",
            "bairro": "Jardim Sao Paulo",
            "cidade": "São Paulo",
            "uf": "SP"
        },
        "remetente": dados_remetente,
        "coletas_solicitadas": [
            {
                "tipo": "A", 
                "servico": "PAC", 
                "peso": "3000" 
            }
        ]
    }
    
    try:
        resp_reversa = requests.post(reversa_url, headers=headers, json=payload)
        resp_reversa.raise_for_status()
        
        dados_retorno = resp_reversa.json()
        
        e_ticket = dados_retorno.get('autorizacao_postagem')
        codigo_rastreio = dados_retorno.get('codigo_rastreio')
        
        logging.info(f"SUCESSO! E-ticket: {e_ticket} | Rastreio: {codigo_rastreio}")
        return e_ticket, codigo_rastreio
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Falha na geração da Logística Reversa: {e}")
        if e.response is not None:
             logging.error(f"Resposta dos Correios: {e.response.text}")
        return None, None