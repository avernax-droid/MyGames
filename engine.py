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
# ==============================================================================

import mysql.connector
from mysql.connector import Error
from decimal import Decimal
import datetime
import smtplib
import json
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()

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

def calcular_cotacao_final(produto_id, estado_id, multiplicador_regiao=1.00):
    db = conectar_bd()
    if not db: return None
    try:
        cursor = db.cursor(dictionary=True, buffered=True)
        produto = obter_produto_por_id(produto_id)
        if not produto: return None
        
        cursor.execute("SELECT fator_depreciacao FROM opcoes_estado WHERE id = %s", (estado_id,))
        estado = cursor.fetchone()
        
        fator_raw = estado['fator_depreciacao'] if estado and estado.get('fator_depreciacao') is not None else 1.0
        fator = Decimal(str(fator_raw).replace(',', '.'))
        multiplicador = Decimal(str(multiplicador_regiao))
        
        base_raw = produto['valor_pix_base'] if produto.get('valor_pix_base') is not None else 0.0
        valor_final = Decimal(str(base_raw).replace(',', '.')) * fator * multiplicador
        
        return {
            "produto": produto['nome_produto'], 
            "valor_final": float(valor_final),
            "multiplicador_aplicado": float(multiplicador_regiao)
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
        
        corpo = f"Olá {cliente['nome_completo']},\n\nProtocolo: {dados_email['protocolo']}\n\n"
        
        tem_analise_manual = False
        
        for item in itens_avaliados:
            corpo += f"Produto: {item.get('produto_nome')}\n"
            if item.get('is_outros'):
                corpo += " Valor: Sob Consulta\n\n"
                tem_analise_manual = True
            else:
                mult = float(item.get('multiplicador_aplicado', 1.0))
                valor_final = float(item['valor_pix_unitario'])
                
                if mult != 1.0:
                    valor_original = valor_final / mult
                    if mult > 1.0:
                        corpo += " ✨ Bônus Regional Aplicado!\n"
                    else:
                        corpo += " 📍 Preço Ajustado à sua Região\n"
                    corpo += f" De: R$ {valor_original:.2f} | Por: R$ {valor_final:.2f}\n\n"
                else:
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
        
        sql = "INSERT INTO protocolos_recompra (cliente_id, numero_protocolo, status, valor_total_pix, valor_total_credito, data_criacao, canal_aquisicao_id) VALUES (%s, %s, 'Aberto', %s, %s, NOW(), %s)"
        
        cursor.execute(sql, (dados_proposta['cliente_id'], protocolo, dados_proposta['total_pix'], dados_proposta['total_cred'], canal_id))
        
        p_id = cursor.lastrowid
        db.commit()
        return {"id": p_id, "numero": protocolo}
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