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
# - 13/06/2026: Migração da integração dos Correios para arquitetura SOAP/XML. Inclusão de roteamento dinâmico de serviço (PAC/SEDEX) por faixa de CEP.
# - 15/06/2026: Inclusão da função obter_dados_empresa para corrigir o AttributeError na geração do protocolo mobile.
# - 16/06/2026: Dinamização dos dados do remetente (e-mail e nome fantasia) no envio de e-mails, buscando da tabela dados_empresa com LIMIT 1.
# - 16/06/2026: Inclusão de formataddr para mascarar o remetente oficial do GMail com o Nome Fantasia da empresa na caixa de entrada do cliente.
# - 16/06/2026: Correção de autenticação WS-Security na integração SOAP dos Correios e roteamento dinâmico de URL de homologação/produção.
# - 16/06/2026: Ajuste na URL de homologação da integração Correios (adição do sufixo ?wsdl) para resolver erro HTTP 404.
# - 19/06/2026: Refatoração da função gerar_logistica_reversa para integração com o Portal Postal via SOAP (PrePostagemXml) e ajuste na chamada em finalizar_proposta.
# - 20/06/2026: Remoção da exibição do E-Ticket no corpo do e-mail de resumo e atualização das instruções de postagem.
# - 23/06/2026: Implementação da dupla barreira de validação em calcular_cotacao_final (Backend Business Rules).
# - 23/06/2026: Adição do xml.sax.saxutils (escape) para sanitização rigorosa de caracteres especiais na integração dos Correios.
# - 26/06/2026: Validação da dinamização do nome fantasia no e-mail (enviar_email_resumo) e remoção de strings "MyGames" hardcoded na integração dos Correios.
# - 02/07/2026: Correção na função registrar_item_periciado substituindo a coluna inexistente 'quantidade' por 'qtd_declarada' no INSERT do banco de dados.
# ==============================================================================

import mysql.connector
from mysql.connector import Error
from decimal import Decimal
import datetime
import smtplib
import json
import requests
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape # NOVO: Sanitização para o SOAP
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr 
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

def calcular_cotacao_final(produto_id, estado_id, multiplicador_regiao=1.00, quantidade=1, pergunta_extra=""):
    db = conectar_bd()
    if not db: return None
    try:
        cursor = db.cursor(dictionary=True, buffered=True)
        produto = obter_produto_por_id(produto_id)
        if not produto: return None
        
        cursor.execute("SELECT descricao, fator_depreciacao FROM opcoes_estado WHERE id = %s", (estado_id,))
        estado = cursor.fetchone()
        
        # -----------------------------------------------------------------
        # DUPLA BARREIRA DE VALIDAÇÃO (Regras de Negócio do Backend)
        # -----------------------------------------------------------------
        categoria_id_str = str(produto.get('categoria_id'))
        texto_estado = estado['descricao'].lower() if estado and estado.get('descricao') else ""
        texto_extra = str(pergunta_extra).lower()
        
        if categoria_id_str == '1': # Console
            if 'não funciona' in texto_estado:
                raise ValueError("Item recusado pela regra de negócio: Console não funciona.")
            if 'desbloqueado' in texto_extra:
                raise ValueError("Item recusado pela regra de negócio: Console desbloqueado.")
                
        elif categoria_id_str == '2': # Controle
            if 'pirata' in texto_extra:
                raise ValueError("Item recusado pela regra de negócio: Controle não original.")
                
        elif categoria_id_str == '4': # Jogo
            if 'não funciona' in texto_estado:
                raise ValueError("Item recusado pela regra de negócio: Jogo não funciona.")
                
        elif categoria_id_str == '3': # Acessório
            if 'pirata' in texto_extra:
                raise ValueError("Item recusado pela regra de negócio: Acessório não original.")
        # -----------------------------------------------------------------
        
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

def obter_dados_empresa():
    """
    Busca os dados da empresa (nome, cnpj, etc) no banco de dados 
    para a geração do protocolo e envio de e-mails.
    """
    db = conectar_bd()
    if not db: 
        return None
        
    try:
        cursor = db.cursor(dictionary=True)
        # Busca o primeiro registro na tabela dados_empresa
        cursor.execute("SELECT * FROM dados_empresa LIMIT 1")
        resultado = cursor.fetchone()
        
        if not resultado:
            print("AVISO: A tabela 'dados_empresa' está vazia no banco de dados!")
            
        return resultado
    except Exception as e:
        print(f"Erro ao buscar dados da empresa: {e}")
        return None
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

def enviar_email_resumo(cliente, dados_email, itens_avaliados):
    try:
        # Busca dados da empresa para dinamizar o envio
        empresa = obter_dados_empresa()
        nome_fantasia = empresa.get('nome_fantasia', 'Loja') if empresa else 'Loja'
        
        # Mantemos o login com a conta base do SMTP configurada
        remetente_login, senha = "avernax@gmail.com", "nmmawgxrhuyzfpoe"
        
        # O SEGREDO ESTÁ AQUI: Formatamos o remetente para exibir o "Nome Fantasia"
        # Ex: "Rock Laser" <avernax@gmail.com>
        msg = MIMEMultipart()
        msg['From'] = formataddr((nome_fantasia, remetente_login))
        msg['To'] = cliente['email']
        msg['Subject'] = f"Confirmação {nome_fantasia} - Protocolo {dados_email['protocolo']}"
        
        corpo = f"Olá {cliente['nome_completo']},\n\n"
        corpo += f"Protocolo: {dados_email['protocolo']}\n"
        corpo += f"Valor Total do Lote (PIX): R$ {dados_email.get('total_pix', 0.0):.2f}\n\n"
        
        # INCLUSÃO DA SEÇÃO DE LOGÍSTICA REVERSA NO CORPO DO E-MAIL
        if dados_email.get('codigo_rastreio'):
            corpo += "--------------------------------------------------------\n"
            corpo += "📦 DADOS DE POSTAGEM (LOGÍSTICA REVERSA):\n"
            corpo += f" Código de Rastreio dos Correios: {dados_email['codigo_rastreio']}\n"
            corpo += "\n Instruções: Embale os itens com segurança, dirija-se\n"
            corpo += " a uma agência dos Correios e informe o código de rastreio acima.\n"
            corpo += f" O envio é faturado diretamente para a conta comercial\n"
            corpo += f" da {nome_fantasia}, sendo 100% gratuito para você.\n"
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
        
        corpo += f"Atenciosamente,\nEquipe {nome_fantasia}"
            
        msg.attach(MIMEText(corpo, 'plain', 'utf-8'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remetente_login, senha)
        server.send_message(msg)
        server.quit()
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
        
        # Ajuste para integrar itens avaliados garantindo o formato seguro da API
        itens_avaliados = dados_proposta.get('itens', [])
        if not itens_avaliados:
            itens_avaliados = [{'produto_nome': 'Produtos Diversos', 'quantidade': 1, 'valor_pix_unitario': 0.00}]
            
        e_ticket, codigo_rastreio = gerar_logistica_reversa(dados_remetente, protocolo, itens_avaliados)
        
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

def gerar_logistica_reversa(dados_remetente, numero_protocolo, itens_avaliados):
    """
    Integração com Web Service do Portal Postal (Correios AGF).
    Utiliza o método PrePostagemXml (Sem Sequência Lógica).
    """
    # Credenciais fixas da agência (Portal Postal)
    cod_agencia = os.getenv('CORREIOS_AGENCIA')
    login_ws    = os.getenv('CORREIOS_USER')
    senha_ws    = os.getenv('CORREIOS_PASS')
    url_soap    = "http://www.portalpostal.com.br/axis2/services/PrePostagemWS"
    ambiente = os.getenv('CORREIOS_AMBIENTE')
    
    if ambiente == "fake":
        logging.info("MODO FAKE ATIVADO: Simulando resposta do Portal Postal...")
        return "888888888", "BR987654321BR"

    # Busca nome da empresa para aplicar nas variáveis genéricas caso necessário
    empresa = obter_dados_empresa()
    nome_fantasia = empresa.get('nome_fantasia', 'Loja') if empresa else 'Loja'

    # Roteamento Dinâmico de Serviço (CEP)
    cep_cliente = ''.join(filter(str.isdigit, str(dados_remetente.get('cep', ''))))
    servico_correios = "PAC" # Fallback padrão
    
    if cep_cliente and len(cep_cliente) == 8:
        if int(cep_cliente) < 20000000:
            servico_correios = "SEDEX"
            logging.info(f"Roteamento: CEP {cep_cliente} classificado como SEDEX")
        else:
            logging.info(f"Roteamento: CEP {cep_cliente} classificado como PAC")

    # 1. Construção dinâmica do conteúdo (Itens Periciados) COM SANITIZAÇÃO
    xml_itens = ""
    for item in itens_avaliados:
        # O escape() protege contra &, < e >, convertendo para &amp;, &lt;, &gt;
        # Substituí o "Item MyGames" por "Item {nome_fantasia}"
        descricao_limpa = escape(str(item.get('produto_nome', f'Item {nome_fantasia}')))[:100]
        if len(descricao_limpa) < 5:
            descricao_limpa = descricao_limpa.ljust(5, 'x')
            
        xml_itens += f"""
        <item>
            <descricao>{descricao_limpa}</descricao>
            <quantidade>{escape(str(item.get('quantidade', 1)))}</quantidade>
            <valor>{escape(str(item.get('valor_pix_unitario', '0.00')))}</valor>
        </item>"""

    # 2. Construção do XML interno de postagem COM SANITIZAÇÃO
    # Substituí o "Cliente MyGames" por "Cliente {nome_fantasia}"
    nome_seguro = escape(str(dados_remetente.get('nome', f'Cliente {nome_fantasia}')))[:100]
    logradouro_seguro = escape(str(dados_remetente.get('logradouro', '')))[:100]
    numero_seguro = escape(str(dados_remetente.get('numero', '')))[:10]
    complemento_seguro = escape(str(dados_remetente.get('complemento', '')))[:100]
    bairro_seguro = escape(str(dados_remetente.get('bairro', '')))[:100]
    cidade_seguro = escape(str(dados_remetente.get('cidade', '')))[:100]
    uf_seguro = escape(str(dados_remetente.get('uf', '')))[:2]

    xml_dados_postagem = f"""<portalpostal>
    <pre_postagem>
        <chave>{numero_protocolo}</chave>
        <nome>{nome_seguro}</nome>
        <cep>{cep_cliente}</cep>
        <endereco>{logradouro_seguro}</endereco>
        <numero>{numero_seguro}</numero>
        <complemento>{complemento_seguro}</complemento>
        <bairro>{bairro_seguro}</bairro>
        <cidade>{cidade_seguro}</cidade>
        <estado>{uf_seguro}</estado>
        <servico>{servico_correios}</servico>
        <conteudo>{xml_itens}</conteudo>
    </pre_postagem>
</portalpostal>"""

# 3. Construção do Envelope SOAP com CDATA e Namespace corrigido (pos)
    soap_payload = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:pos="http://postagem/xsd">
       <soapenv:Header/>
       <soapenv:Body>
          <pos:PrePostagemXml>
             <pos:xml><![CDATA[{xml_dados_postagem}]]></pos:xml>
             <pos:codAgencia>{cod_agencia}</pos:codAgencia>
             <pos:login>{login_ws}</pos:login>
             <pos:senha>{senha_ws}</pos:senha>
          </pos:PrePostagemXml>
       </soapenv:Body>
    </soapenv:Envelope>"""

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": "urn:PrePostagemXml"
    }
    
    try:
        logging.info("Enviando requisição SOAP para o Portal Postal...")
        resp = requests.post(url_soap, data=soap_payload.encode('utf-8'), headers=headers, timeout=15)
        
        if resp.status_code == 200:
            root = ET.fromstring(resp.text)
            
            # Navega no XML de retorno para encontrar a resposta
            codigo_rastreio = None
            detalhes_erro = None
            
            for elem in root.iter():
                # O XML devolvido fica embutido na resposta SOAP
                if 'PrePostagemXmlReturn' in elem.tag or 'return' in elem.tag:
                    retorno_xml_str = elem.text
                    if retorno_xml_str:
                        retorno_root = ET.fromstring(retorno_xml_str)
                        for postagem in retorno_root.findall('.//postagem'):
                            codigo_rastreio = postagem.findtext('codigo_rastreio')
                            if codigo_rastreio == 'erro':
                                detalhes_erro = postagem.findtext('detalhes')
                                codigo_rastreio = None
                        
                        for erro in retorno_root.findall('.//erro'):
                            detalhes_erro = erro.text

            if codigo_rastreio:
                logging.info(f"SUCESSO! Código de Rastreio gerado: {codigo_rastreio}")
                # O Portal Postal não usa E-ticket da mesma forma, retornamos o rastreio
                return codigo_rastreio, codigo_rastreio
            else:
                logging.error(f"Falha ao gerar etiqueta no Portal Postal. Motivo: {detalhes_erro}")
                return None, None
        else:
            logging.error(f"Falha na integração HTTP {resp.status_code}: {resp.text}")
            return None, None

    except requests.exceptions.RequestException as e:
        logging.error(f"Erro de conexão com o Portal Postal: {e}")
        return None, None
    except ET.ParseError as e:
        logging.error(f"Erro ao processar XML de retorno: {e}")
        return None, None
    except Exception as e:
        logging.error(f"Erro interno no processamento: {e}")
        return None, None# ==============================================================================
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
# - 13/06/2026: Migração da integração dos Correios para arquitetura SOAP/XML. Inclusão de roteamento dinâmico de serviço (PAC/SEDEX) por faixa de CEP.
# - 15/06/2026: Inclusão da função obter_dados_empresa para corrigir o AttributeError na geração do protocolo mobile.
# - 16/06/2026: Dinamização dos dados do remetente (e-mail e nome fantasia) no envio de e-mails, buscando da tabela dados_empresa com LIMIT 1.
# - 16/06/2026: Inclusão de formataddr para mascarar o remetente oficial do GMail com o Nome Fantasia da empresa na caixa de entrada do cliente.
# - 16/06/2026: Correção de autenticação WS-Security na integração SOAP dos Correios e roteamento dinâmico de URL de homologação/produção.
# - 16/06/2026: Ajuste na URL de homologação da integração Correios (adição do sufixo ?wsdl) para resolver erro HTTP 404.
# - 19/06/2026: Refatoração da função gerar_logistica_reversa para integração com o Portal Postal via SOAP (PrePostagemXml) e ajuste na chamada em finalizar_proposta.
# - 20/06/2026: Remoção da exibição do E-Ticket no corpo do e-mail de resumo e atualização das instruções de postagem.
# - 23/06/2026: Implementação da dupla barreira de validação em calcular_cotacao_final (Backend Business Rules).
# - 23/06/2026: Adição do xml.sax.saxutils (escape) para sanitização rigorosa de caracteres especiais na integração dos Correios.
# - 26/06/2026: Validação da dinamização do nome fantasia no e-mail (enviar_email_resumo) e remoção de strings "MyGames" hardcoded na integração dos Correios.
# - 26/06/2026: Refatoração da função enviar_email_resumo para formato HTML rico, aplicando o template de cópia do PDF (com negritos e caixa alta) e listagem dinâmica de produtos.
# ==============================================================================

import mysql.connector
from mysql.connector import Error
from decimal import Decimal
import datetime
import smtplib
import json
import requests
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr 
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

def calcular_cotacao_final(produto_id, estado_id, multiplicador_regiao=1.00, quantidade=1, pergunta_extra=""):
    db = conectar_bd()
    if not db: return None
    try:
        cursor = db.cursor(dictionary=True, buffered=True)
        produto = obter_produto_por_id(produto_id)
        if not produto: return None
        
        cursor.execute("SELECT descricao, fator_depreciacao FROM opcoes_estado WHERE id = %s", (estado_id,))
        estado = cursor.fetchone()
        
        # -----------------------------------------------------------------
        # DUPLA BARREIRA DE VALIDAÇÃO (Regras de Negócio do Backend)
        # -----------------------------------------------------------------
        categoria_id_str = str(produto.get('categoria_id'))
        texto_estado = estado['descricao'].lower() if estado and estado.get('descricao') else ""
        texto_extra = str(pergunta_extra).lower()
        
        if categoria_id_str == '1': # Console
            if 'não funciona' in texto_estado:
                raise ValueError("Item recusado pela regra de negócio: Console não funciona.")
            if 'desbloqueado' in texto_extra:
                raise ValueError("Item recusado pela regra de negócio: Console desbloqueado.")
                
        elif categoria_id_str == '2': # Controle
            if 'pirata' in texto_extra:
                raise ValueError("Item recusado pela regra de negócio: Controle não original.")
                
        elif categoria_id_str == '4': # Jogo
            if 'não funciona' in texto_estado:
                raise ValueError("Item recusado pela regra de negócio: Jogo não funciona.")
                
        elif categoria_id_str == '3': # Acessório
            if 'pirata' in texto_extra:
                raise ValueError("Item recusado pela regra de negócio: Acessório não original.")
        # -----------------------------------------------------------------
        
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
        # CORREÇÃO: O campo no banco de dados se chama 'qtd_declarada', não 'quantidade'.
        sql = "INSERT INTO itens_periciados (protocolo_id, produto_id, qtd_declarada, fotos_json, comentarios, valor_pix_unitario, valor_cred_unitario) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        
        # Mantemos o item.get('quantidade', 1) pois é assim que a chave trafega no JSON/Sessão do Front-end
        cursor.execute(sql, (
            protocolo_id, 
            item['produto_id'], 
            item.get('quantidade', 1), 
            item.get('fotos_json'), 
            item.get('comentarios', ''), 
            item['valor_pix_unitario'], 
            item['valor_cred_unitario']
        ))
        db.commit()
        return True
    finally:
        if db and db.is_connected(): cursor.close(); db.close()

# --- MÓDULO DE FINALIZAÇÃO ---

def obter_dados_empresa():
    """
    Busca os dados da empresa (nome, cnpj, etc) no banco de dados 
    para a geração do protocolo e envio de e-mails.
    """
    db = conectar_bd()
    if not db: 
        return None
        
    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM dados_empresa LIMIT 1")
        resultado = cursor.fetchone()
        
        if not resultado:
            print("AVISO: A tabela 'dados_empresa' está vazia no banco de dados!")
            
        return resultado
    except Exception as e:
        print(f"Erro ao buscar dados da empresa: {e}")
        return None
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

def enviar_email_resumo(cliente, dados_email, itens_avaliados):
    try:
        # Busca dados da empresa para dinamizar o envio
        empresa = obter_dados_empresa()
        nome_fantasia = empresa.get('nome_fantasia', 'Loja') if empresa else 'Loja'
        
        # Mantemos o login com a conta base do SMTP configurada
        remetente_login, senha = "avernax@gmail.com", "nmmawgxrhuyzfpoe"
        
        msg = MIMEMultipart('alternative')
        msg['From'] = formataddr((nome_fantasia, remetente_login))
        msg['To'] = cliente['email']
        msg['Subject'] = f"Confirmação {nome_fantasia} - Protocolo {dados_email['protocolo']}"

        # Preparação da lista de itens em HTML
        html_itens = "<p><strong>ÍTENS INCLUÍDOS NA VENDA:</strong></p>"
        tem_analise_manual = False
        
        for item in itens_avaliados:
            html_itens += f"<p><strong>Produto:</strong> {item.get('produto_nome')}<br>"
            if item.get('is_outros'):
                html_itens += "<strong>Valor:</strong> Sob Consulta</p>"
                tem_analise_manual = True
            else:
                valor_final = float(item['valor_pix_unitario'])
                html_itens += f"<strong>Valor:</strong> R$ {valor_final:.2f}</p>"

        # Adiciona aviso caso haja itens manuais
        aviso_manual_html = ""
        if tem_analise_manual:
            aviso_manual_html = """
            <br>
            <p><strong>AVISO SOBRE ITENS SOB CONSULTA:</strong></p>
            <p>Notamos que o seu lote contém itens que não estão cadastrados em nosso sistema padrão. 
            Nossa equipe técnica avaliará as informações e fotos enviadas, e entrará em contato 
            com você em até 24 horas úteis para apresentar a oferta final destes itens.</p>
            <br>
            """

        # Bloco de Logística Reversa (se houver código)
        html_logistica = ""
        if dados_email.get('codigo_rastreio'):
            html_logistica = f"""
            <p>O próximo passo é você embalar todos os itens numa caixa e se dirigir a unidade dos CORREIOS mais próxima de sua residência juntamente com o código de <strong>LOGÍSTICA REVERSA</strong> apresentado abaixo.</p>
            <p><strong>ATENÇÃO: Você não deve realizar nenhum pagamento, o custo do envio é por nossa conta!</strong></p>
            <p><strong>DADOS DE POSTAGEM (LOGÍSTICA REVERSA):</strong><br>
            <strong>Código de Rastreio dos Correios:</strong> {dados_email['codigo_rastreio']}</p>
            <p><strong>Instruções:</strong> Embale os itens com segurança, dirija-se a uma agência dos Correios e informe o código de rastreio acima.<br>
            O envio é faturado diretamente para a conta comercial da <strong>{nome_fantasia}</strong>, sendo 100% gratuito para você.</p>
            """

        # Construção final do corpo do HTML (idêntico ao PDF)
        corpo_html = f"""
        <div style="font-family: Arial, sans-serif; font-size: 14px; color: #333; line-height: 1.5;">
            <p>Olá {cliente['nome_completo']},</p>
            <p>Muito obrigado por realizar a venda de seu Game Usado para a <strong>{nome_fantasia}</strong>!</p>
            <p>Segue seu protocolo abaixo para acompanhamento do processo:</p>
            <p>
                <strong>Protocolo:</strong> {dados_email['protocolo']}<br>
                <strong>Valor Total do Lote (PIX):</strong> R$ {dados_email.get('total_pix', 0.0):.2f}
            </p>
            
            {html_logistica}
            
            {html_itens}
            
            {aviso_manual_html}
            
            <p>Assim que recebermos os itens, os mesmos passarão pela nossa <strong>PERÍCIA TÉCNICA</strong> e vamos te enviar o <strong>LAUDO</strong> e realizar o <strong>PAGAMENTO</strong> em até 48 horas úteis após o envio deste laudo.</p>
            <p>Caso haja qualquer divergência nas informações ou falha encontrada na perícia, nossa equipe entrará em contato com você!</p>
            
            <p><strong>POLÍTICA DE AVALIAÇÃO FÍSICA:</strong><br>
            Lembramos que as cotações acima são pré-avaliações baseadas nas informações fornecidas e considerando os produtos em perfeito estado de funcionamento sem itens faltantes.<br><br>
            A aprovação da oferta e o pagamento final estão sujeitos à conferência e avaliação técnica presencial pela nossa equipe, assim que os produtos forem recebidos em nossa empresa via Correios.</p>
            
            <p>A <strong>{nome_fantasia}</strong> atua a mais de 34 anos no mercado tendo atendido dezenas de milhares de clientes satisfeitos.</p>
            <p>É um grande prazer tê-lo como nosso cliente.</p>
            
            <br>
            <p>Atenciosamente,<br>Equipe <strong>{nome_fantasia}</strong></p>
        </div>
        """
            
        msg.attach(MIMEText(corpo_html, 'html', 'utf-8'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remetente_login, senha)
        server.send_message(msg)
        server.quit()
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
        
        # Ajuste para integrar itens avaliados garantindo o formato seguro da API
        itens_avaliados = dados_proposta.get('itens', [])
        if not itens_avaliados:
            itens_avaliados = [{'produto_nome': 'Produtos Diversos', 'quantidade': 1, 'valor_pix_unitario': 0.00}]
            
        e_ticket, codigo_rastreio = gerar_logistica_reversa(dados_remetente, protocolo, itens_avaliados)
        
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

def gerar_logistica_reversa(dados_remetente, numero_protocolo, itens_avaliados):
    """
    Integração com Web Service do Portal Postal (Correios AGF).
    Utiliza o método PrePostagemXml (Sem Sequência Lógica).
    """
    # Credenciais fixas da agência (Portal Postal)
    cod_agencia = os.getenv('CORREIOS_AGENCIA')
    login_ws    = os.getenv('CORREIOS_USER')
    senha_ws    = os.getenv('CORREIOS_PASS')
    url_soap    = "http://www.portalpostal.com.br/axis2/services/PrePostagemWS"
    ambiente = os.getenv('CORREIOS_AMBIENTE')
    
    if ambiente == "fake":
        logging.info("MODO FAKE ATIVADO: Simulando resposta do Portal Postal...")
        return "888888888", "BR987654321BR"

    # Busca nome da empresa para aplicar nas variáveis genéricas caso necessário
    empresa = obter_dados_empresa()
    nome_fantasia = empresa.get('nome_fantasia', 'Loja') if empresa else 'Loja'

    # Roteamento Dinâmico de Serviço (CEP)
    cep_cliente = ''.join(filter(str.isdigit, str(dados_remetente.get('cep', ''))))
    servico_correios = "PAC" # Fallback padrão
    
    if cep_cliente and len(cep_cliente) == 8:
        if int(cep_cliente) < 20000000:
            servico_correios = "SEDEX"
            logging.info(f"Roteamento: CEP {cep_cliente} classificado como SEDEX")
        else:
            logging.info(f"Roteamento: CEP {cep_cliente} classificado como PAC")

    # 1. Construção dinâmica do conteúdo (Itens Periciados) COM SANITIZAÇÃO
    xml_itens = ""
    for item in itens_avaliados:
        # O escape() protege contra &, < e >, convertendo para &amp;, &lt;, &gt;
        # Substituí o "Item MyGames" por "Item {nome_fantasia}"
        descricao_limpa = escape(str(item.get('produto_nome', f'Item {nome_fantasia}')))[:100]
        if len(descricao_limpa) < 5:
            descricao_limpa = descricao_limpa.ljust(5, 'x')
            
        xml_itens += f"""
        <item>
            <descricao>{descricao_limpa}</descricao>
            <quantidade>{escape(str(item.get('quantidade', 1)))}</quantidade>
            <valor>{escape(str(item.get('valor_pix_unitario', '0.00')))}</valor>
        </item>"""

    # 2. Construção do XML interno de postagem COM SANITIZAÇÃO
    # Substituí o "Cliente MyGames" por "Cliente {nome_fantasia}"
    nome_seguro = escape(str(dados_remetente.get('nome', f'Cliente {nome_fantasia}')))[:100]
    logradouro_seguro = escape(str(dados_remetente.get('logradouro', '')))[:100]
    numero_seguro = escape(str(dados_remetente.get('numero', '')))[:10]
    complemento_seguro = escape(str(dados_remetente.get('complemento', '')))[:100]
    bairro_seguro = escape(str(dados_remetente.get('bairro', '')))[:100]
    cidade_seguro = escape(str(dados_remetente.get('cidade', '')))[:100]
    uf_seguro = escape(str(dados_remetente.get('uf', '')))[:2]

    xml_dados_postagem = f"""<portalpostal>
    <pre_postagem>
        <chave>{numero_protocolo}</chave>
        <nome>{nome_seguro}</nome>
        <cep>{cep_cliente}</cep>
        <endereco>{logradouro_seguro}</endereco>
        <numero>{numero_seguro}</numero>
        <complemento>{complemento_seguro}</complemento>
        <bairro>{bairro_seguro}</bairro>
        <cidade>{cidade_seguro}</cidade>
        <estado>{uf_seguro}</estado>
        <servico>{servico_correios}</servico>
        <conteudo>{xml_itens}</conteudo>
    </pre_postagem>
</portalpostal>"""

# 3. Construção do Envelope SOAP com CDATA e Namespace corrigido (pos)
    soap_payload = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:pos="http://postagem/xsd">
       <soapenv:Header/>
       <soapenv:Body>
          <pos:PrePostagemXml>
             <pos:xml><![CDATA[{xml_dados_postagem}]]></pos:xml>
             <pos:codAgencia>{cod_agencia}</pos:codAgencia>
             <pos:login>{login_ws}</pos:login>
             <pos:senha>{senha_ws}</pos:senha>
          </pos:PrePostagemXml>
       </soapenv:Body>
    </soapenv:Envelope>"""

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": "urn:PrePostagemXml"
    }
    
    try:
        logging.info("Enviando requisição SOAP para o Portal Postal...")
        resp = requests.post(url_soap, data=soap_payload.encode('utf-8'), headers=headers, timeout=15)
        
        if resp.status_code == 200:
            root = ET.fromstring(resp.text)
            
            # Navega no XML de retorno para encontrar a resposta
            codigo_rastreio = None
            detalhes_erro = None
            
            for elem in root.iter():
                # O XML devolvido fica embutido na resposta SOAP
                if 'PrePostagemXmlReturn' in elem.tag or 'return' in elem.tag:
                    retorno_xml_str = elem.text
                    if retorno_xml_str:
                        retorno_root = ET.fromstring(retorno_xml_str)
                        for postagem in retorno_root.findall('.//postagem'):
                            codigo_rastreio = postagem.findtext('codigo_rastreio')
                            if codigo_rastreio == 'erro':
                                detalhes_erro = postagem.findtext('detalhes')
                                codigo_rastreio = None
                        
                        for erro in retorno_root.findall('.//erro'):
                            detalhes_erro = erro.text

            if codigo_rastreio:
                logging.info(f"SUCESSO! Código de Rastreio gerado: {codigo_rastreio}")
                # O Portal Postal não usa E-ticket da mesma forma, retornamos o rastreio
                return codigo_rastreio, codigo_rastreio
            else:
                logging.error(f"Falha ao gerar etiqueta no Portal Postal. Motivo: {detalhes_erro}")
                return None, None
        else:
            logging.error(f"Falha na integração HTTP {resp.status_code}: {resp.text}")
            return None, None

    except requests.exceptions.RequestException as e:
        logging.error(f"Erro de conexão com o Portal Postal: {e}")
        return None, None
    except ET.ParseError as e:
        logging.error(f"Erro ao processar XML de retorno: {e}")
        return None, None
    except Exception as e:
        logging.error(f"Erro interno no processamento: {e}")
        return None, None