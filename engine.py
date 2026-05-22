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

        sql = """INSERT INTO clientes_usuarios 
                 (nome_completo, email, whatsapp, cidade, estado_nome, estado_uf, origem_lead, cpf, cep) 
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                 ON DUPLICATE KEY UPDATE 
                 nome_completo = VALUES(nome_completo), whatsapp = VALUES(whatsapp),
                 cidade = VALUES(cidade), estado_nome = VALUES(estado_nome), estado_uf = VALUES(estado_uf),
                 cpf = COALESCE(VALUES(cpf), cpf), cep = COALESCE(VALUES(cep), cep)"""
        cursor.execute(sql, (dados['nome_completo'], dados['email'], whatsapp, dados['cidade'], 
                             dados.get('estado_nome'), dados.get('estado_uf'), dados['origem_lead'], cpf, cep))
        db.commit()
        
        if cursor.lastrowid: return cursor.lastrowid
        cursor.execute("SELECT id FROM clientes_usuarios WHERE email = %s", (dados['email'],))
        res = cursor.fetchone()
        return res['id'] if res else None
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

def calcular_cotacao_final(produto_id, estado_id):
    db = conectar_bd()
    if not db: return None
    try:
        cursor = db.cursor(dictionary=True, buffered=True)
        produto = obter_produto_por_id(produto_id)
        if not produto: return None
        
        cursor.execute("SELECT fator_depreciacao FROM opcoes_estado WHERE id = %s", (estado_id,))
        estado = cursor.fetchone()
        
        # Correção: Blindagem contra valores nulos/vazios e troca de vírgula por ponto
        fator_raw = estado['fator_depreciacao'] if estado and estado.get('fator_depreciacao') is not None else 1.0
        fator = Decimal(str(fator_raw).replace(',', '.'))
        
        base_raw = produto['valor_pix_base'] if produto.get('valor_pix_base') is not None else 0.0
        valor_final = Decimal(str(base_raw).replace(',', '.')) * fator
        
        return {"produto": produto['nome_produto'], "valor_final": float(valor_final)}
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
        for item in itens_avaliados:
            corpo += f"Produto: {item.get('produto_nome')}\n Valor: R$ {item['valor_pix_unitario']:.2f}\n"
        msg.attach(MIMEText(corpo, 'plain'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls(); server.login(remetente, senha); server.send_message(msg); server.quit()
        return True
    except: return False

def finalizar_proposta(dados_proposta):
    db = conectar_bd()
    if not db: return None
    try:
        cursor = db.cursor()
        agora = datetime.datetime.now()
        protocolo = f"MG-{agora.year}-{dados_proposta['cliente_id']}-{agora.strftime('%H%M%S')}"
        sql = "INSERT INTO protocolos_recompra (cliente_id, numero_protocolo, status, valor_total_pix, valor_total_credito, data_criacao) VALUES (%s, %s, 'Aberto', %s, %s, NOW())"
        cursor.execute(sql, (dados_proposta['cliente_id'], protocolo, dados_proposta['total_pix'], dados_proposta['total_cred']))
        p_id = cursor.lastrowid
        db.commit()
        return {"id": p_id, "numero": protocolo}
    finally:
        if db and db.is_connected(): cursor.close(); db.close()

# --- MÓDULO DE BUSCA ---

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