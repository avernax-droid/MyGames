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
# - 10/06/2026: Formatação e inserção dos dados de postagem (e-ticket e rastreio) no corpo do e-mail de resumo.
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
# - 02/07/2026: Correção na função registrar_item_periciado substituindo a coluna inexistente 'quantidade' por 'qtd_declarada' no INSERT do banco de dados.
# - 04/07/2026: Atualização da dupla barreira em calcular_cotacao_final para permitir consoles desbloqueados específicos (PS1, PS2 e PS Vita).
# - 04/07/2026: Integração do campo valor_cred_base nas funções calcular_cotacao_final e buscar_produtos_por_categoria.
# - 05/07/2026: Correção na função enviar_email_resumo para multiplicar o valor unitário pela quantidade do item na listagem do e-mail.
# - 07/07/2026: Refatoração na função calcular_cotacao_final para remover a multiplicação por quantidade, garantindo o retorno estrito do valor unitário.
# - 09/07/2026: Refatoração na função enviar_email_resumo para remover credenciais SMTP hardcoded e parametrizar consumo seguro via variáveis de ambiente (.env).
# - 27/07/2026: Substituição da terminologia 'Logística Reversa' por 'Código de Rastreio', e formatação/exibição do CEP de destino no e-mail.
# - 27/07/2026: Implementação da Solução "Modo 1" (Workaround Portal Postal): Remoção da tag <reversa>1</reversa>. Empresa alocada na raiz (Destinatário) para viabilizar chave de busca por CEP no balcão, resultando em etiqueta espelhada. Cliente alocado no bloco <remetente>.
# - 28/07/2026: AJUSTE FINAL: Adição da tag <cartao_postagem>, <peso> e <dimensoes> para garantir faturamento no contrato e não reprovação do Portal Postal. Mantido Modo Espelhado.
# - 23/10/2026: Remoção da função consultar_municipios_ibge() e rotinas de cache, pois a busca foi descentralizada para o front-end, aliviando o servidor.
# - 23/10/2026: Implementação da função enviar_webhook_novo_protocolo para integração com o Agente de WhatsApp (Fluxo A), consumindo parâmetros dinâmicos do .env.
# - 24/10/2026: Refatoração da função gerar_codigo_rastreio para consumir a API REST/JSON dos Correios (Pré-postagem V1). Inclusão do mecanismo de autenticação OAuth2 (obter_token_correios) e remoção das bibliotecas XML.
# - 24/10/2026: Correção de validações PPN da API REST dos Correios: injeção de CPF/CNPJ obrigatórios, ajuste de logisticaReversa para 'N', formatação do cienteObjetoNaoProibido como numérico e formato de caixa (2).
# ==============================================================================

import mysql.connector
from mysql.connector import Error
from decimal import Decimal
import datetime
import smtplib
import json
import requests
import base64
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr 
import os
from dotenv import load_dotenv

load_dotenv()

# Configuração de log focada na validação da API dos Correios via terminal
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [CORREIOS] %(levelname)s - %(message)s')

TOKEN_CACHE = {"token": None, "expira_em": None}

def obter_token_correios():
    global TOKEN_CACHE
    
    cliente_id = os.getenv('CORREIOS_CLIENT_ID', '').strip()
    cliente_secret = os.getenv('CORREIOS_CLIENT_SECRET', '').strip()
    cartao_postagem = os.getenv('CORREIOS_CARTAO_POSTAGEM', '').strip()
    
    if not cliente_id or not cliente_secret:
        logging.error("Credenciais CORREIOS_CLIENT_ID ou CORREIOS_CLIENT_SECRET ausentes no .env")
        return None

    if TOKEN_CACHE["token"] and TOKEN_CACHE["expira_em"] and TOKEN_CACHE["expira_em"] > datetime.datetime.now() + datetime.timedelta(minutes=5):
        return TOKEN_CACHE["token"]

    url_token = "https://api.correios.com.br/token/v1/autentica/cartaopostagem"
    auth_str = f"{cliente_id}:{cliente_secret}"
    auth_base64 = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
    
    headers = {
        "Authorization": f"Basic {auth_base64}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    payload = {"numero": cartao_postagem}
    
    try:
        resp = requests.post(url_token, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        token = data.get("token") or data.get("access_token")
        TOKEN_CACHE["token"] = token
        TOKEN_CACHE["expira_em"] = datetime.datetime.now() + datetime.timedelta(seconds=data.get("expires_in", 28800))
        return token
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro na API de autenticação Correios: {e}")
        return None

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

        if cpf:
            cursor.execute("SELECT id FROM clientes_usuarios WHERE cpf = %s LIMIT 1", (cpf,))
            res = cursor.fetchone()
            if res:
                cliente_existente_id = res['id']

        if cliente_existente_id:
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
        
        categoria_id_str = str(produto.get('categoria_id'))
        texto_estado = estado['descricao'].lower() if estado and estado.get('descricao') else ""
        texto_extra = str(pergunta_extra).lower()
        
        if categoria_id_str == '1':
            if 'não funciona' in texto_estado:
                raise ValueError("Item recusado pela regra de negócio: Console não funciona.")
            if 'desbloqueado' in texto_extra:
                nome_lower = produto.get('nome_produto', '').lower()
                excecoes = ['ps1', 'playstation 1', 'ps2', 'playstation 2', 'vita']
                if not any(exc in nome_lower for exc in excecoes):
                    raise ValueError("Item recusado pela regra de negócio: Este modelo de console não é aceito desbloqueado.")
        elif categoria_id_str == '2':
            if 'pirata' in texto_extra:
                raise ValueError("Item recusado pela regra de negócio: Controle não original.")
        elif categoria_id_str == '4':
            if 'não funciona' in texto_estado:
                raise ValueError("Item recusado pela regra de negócio: Jogo não funciona.")
        elif categoria_id_str == '3':
            if 'pirata' in texto_extra:
                raise ValueError("Item recusado pela regra de negócio: Acessório não original.")
        
        fator_raw = estado['fator_depreciacao'] if estado and estado.get('fator_depreciacao') is not None else 1.0
        fator = Decimal(str(fator_raw).replace(',', '.'))
        multiplicador = Decimal(str(multiplicador_regiao))
        
        base_pix_raw = produto['valor_pix_base'] if produto.get('valor_pix_base') is not None else 0.0
        base_cred_raw = produto['valor_cred_base'] if produto.get('valor_cred_base') is not None else 0.0
        
        valor_unitario_pix = Decimal(str(base_pix_raw).replace(',', '.')) * fator * multiplicador
        valor_unitario_cred = Decimal(str(base_cred_raw).replace(',', '.')) * fator * multiplicador
        
        return {
            "produto": produto['nome_produto'], 
            "valor_final": float(valor_unitario_pix),
            "valor_final_pix": float(valor_unitario_pix),
            "valor_final_cred": float(valor_unitario_cred),
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
        sql = "INSERT INTO itens_periciados (protocolo_id, produto_id, qtd_declarada, fotos_json, comentarios, valor_pix_unitario, valor_cred_unitario) VALUES (%s, %s, %s, %s, %s, %s, %s)"
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
    db = conectar_bd()
    if not db: return None
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
        if db and db.is_connected(): cursor.close(); db.close()

def enviar_email_resumo(cliente, dados_email, itens_avaliados):
    try:
        empresa = obter_dados_empresa()
        nome_fantasia = empresa.get('nome_fantasia', 'Loja') if empresa else 'Loja'
        cartao_postagem = os.getenv('CORREIOS_CARTAO_POSTAGEM', '')
        
        cep_bruto = ''.join(filter(str.isdigit, str(empresa.get('cep', '')))) if empresa else ''
        cep_empresa_formatado = f"{cep_bruto[:5]}-{cep_bruto[5:]}" if len(cep_bruto) == 8 else cep_bruto

        remetente_login = os.getenv('EMAIL_USER')
        senha = os.getenv('EMAIL_PASS')
        host_smtp = os.getenv('EMAIL_HOST')
        porta_smtp = int(os.getenv('EMAIL_PORT', 587))
        
        msg = MIMEMultipart('alternative')
        msg['From'] = formataddr((nome_fantasia, remetente_login))
        msg['To'] = cliente['email']
        msg['Subject'] = f"Confirmação {nome_fantasia} - Protocolo {dados_email['protocolo']}"

        html_itens = "<p><strong>ÍTENS INCLUÍDOS NA VENDA:</strong></p>"
        tem_analise_manual = False
        
        for item in itens_avaliados:
            quantidade = int(item.get('quantidade', 1))
            html_itens += f"<p><strong>Produto:</strong> {item.get('produto_nome')} (Qtd: {quantidade})<br>"
            
            if item.get('is_outros'):
                html_itens += "<strong>Valor:</strong> Sob Consulta</p>"
                tem_analise_manual = True
            else:
                valor_final = float(item['valor_pix_unitario']) * quantidade
                html_itens += f"<strong>Valor:</strong> R$ {valor_final:.2f}</p>"

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

        html_logistica = ""
        if dados_email.get('codigo_rastreio'):
            html_logistica = f"""
            <p>O próximo passo é você embalar todos os itens numa caixa e se dirigir a unidade dos CORREIOS mais próxima.</p>
            <p><strong>ATENÇÃO: Você não deve realizar nenhum pagamento. O custo do envio é por nossa conta!</strong></p>
            <p><strong>DADOS DE POSTAGEM:</strong><br>
            <strong>1. Código de Postagem:</strong> {dados_email['codigo_rastreio']}<br>
            <strong>2. CEP de Destino OBRIGATÓRIO:</strong> {cep_empresa_formatado}</p>
            <p><strong>Instrução para o Atendente:</strong> "Postagem Pré-Paga por Contrato". Informe o <strong>Código</strong> e o <strong>CEP de Destino</strong> acima para localizar a postagem.<br>
            O envio é faturado diretamente para a conta comercial da <strong>{nome_fantasia}</strong>, Cartão {cartao_postagem}.</p>
            """

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
            
            <p>Assim que recebermos os itens, os mesmos passarão pela nossa <strong>PERÍCIA TÉCNICA</strong> e vamos te enviar o <strong>LAUDO</strong> e realizar o <strong>PAGAMENTO</strong> em até 48 hours úteis após o envio deste laudo.</p>
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
        
        server = smtplib.SMTP(host_smtp, porta_smtp)
        server.starttls()
        server.login(remetente_login, senha)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e: 
        import traceback
        logging.error(f"FALHA CRÍTICA NO SMTP: {str(e)}")
        logging.error(traceback.format_exc())
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
            "telefone": cliente.get('whatsapp', ''),
            "cpf": cliente.get('cpf', '') 
        }
        
        itens_avaliados = dados_proposta.get('itens', [])
        if not itens_avaliados:
            itens_avaliados = [{'produto_nome': 'Produtos Diversos', 'quantidade': 1, 'valor_pix_unitario': 0.00}]
            
        e_ticket, codigo_rastreio = gerar_codigo_rastreio(dados_remetente, protocolo, itens_avaliados)
        
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
        cursor.execute("SELECT id, nome_produto, plataforma, foto_oficial_url, valor_pix_base, valor_cred_base FROM catalogo_mestre WHERE categoria_id = %s AND ativo = 1 ORDER BY nome_produto", (categoria_id,))
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

def buscar_canais_aquisicao():
    db = conectar_bd()
    if not db: return []
    try:
        cursor = db.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT id, nome_exibicao FROM canais_aquisicao WHERE ativo = 1")
        return cursor.fetchall()
    finally:
        if db and db.is_connected(): cursor.close(); db.close()

# --- INTEGRAÇÃO CORREIOS - MODO ESPELHADO ---

def gerar_codigo_rastreio(dados_remetente, numero_protocolo, itens_avaliados):
    """
    Integração com a API REST Oficial dos Correios (Pré-postagem V1).
    MODO ESPELHADO: Empresa = Destinatário | Cliente = Remetente
    O cliente postará a caixa sem custos, informando o código no balcão.
    """
    ambiente = os.getenv('CORREIOS_AMBIENTE')
    
    if ambiente == "fake":
        logging.info("MODO FAKE ATIVADO: Simulando resposta da API REST dos Correios...")
        codigo_fake = "ET" + str(datetime.datetime.now().strftime('%H%M%S'))
        return codigo_fake, codigo_fake

    # Dados da Empresa (Destinatário Físico)
    empresa = obter_dados_empresa() or {}
    nome_fantasia = empresa.get('nome_fantasia', 'Loja')
    cep_empresa = ''.join(filter(str.isdigit, str(empresa.get('cep', ''))))
    cnpj_empresa = ''.join(filter(str.isdigit, str(empresa.get('cnpj', os.getenv('CORREIOS_CNPJ', '')))))
    cartao_postagem = os.getenv('CORREIOS_CARTAO_POSTAGEM')
    
    # Dados do Cliente (Remetente Logístico)
    cep_cliente = ''.join(filter(str.isdigit, str(dados_remetente.get('cep', ''))))
    cpf_cliente = ''.join(filter(str.isdigit, str(dados_remetente.get('cpf', ''))))

    # --- ROTEAMENTO INTELIGENTE DE SERVIÇO (PAC/SEDEX) ---
    codigo_servico = "03220" # PAC
    if cep_cliente and len(cep_cliente) == 8:
        if int(cep_cliente) < 20000000:
            codigo_servico = "03298" # SEDEX
            logging.info(f"Roteamento REST: CEP {cep_cliente} classificado como SEDEX (03298)")
        else:
            logging.info(f"Roteamento REST: CEP {cep_cliente} classificado como PAC (03220)")

    # --- PROCESSAMENTO DE ITENS E PESO CUBADO ---
    peso_total = 0.5
    itens_formatados = []
    
    for item in itens_avaliados:
        qtd = int(item.get('quantidade', 1))
        peso_total += qtd * 0.2
        valor_item = float(item.get('valor_pix_unitario', '0.00'))
        
        itens_formatados.append({
            "conteudo": str(item.get('produto_nome', 'Game Usado'))[:100],
            "quantidade": str(qtd),
            "valor": f"{valor_item:.2f}"
        })

    # --- CONSTRUÇÃO DO PAYLOAD JSON (Request Body) ---
    payload = {
        "codigoServico": codigo_servico,
        "numeroCartaoPostagem": cartao_postagem,
        "observacao": numero_protocolo,
        "logisticaReversa": "N", 
        "embalagem": "S",
        "cienteObjetoNaoProibido": 1, # CORREÇÃO: O servidor Java dos Correios espera o número 1 (True), e não a letra "S"
        "pesoInformado": str(int(peso_total * 1000)),
        "codigoFormatoObjetoInformado": "2", 
        "alturaInformada": "10",
        "larguraInformada": "20",
        "comprimentoInformado": "30",
        
        "remetente": {
            "nome": str(dados_remetente.get('nome', f'Cliente {nome_fantasia}'))[:100],
            "cpfCnpj": cpf_cliente, 
            "dddCelular": str(dados_remetente.get('telefone', ''))[:2] if len(str(dados_remetente.get('telefone', ''))) > 2 else "11",
            "celular": str(dados_remetente.get('telefone', ''))[2:11] if len(str(dados_remetente.get('telefone', ''))) > 2 else "999999999",
            "endereco": {
                "cep": cep_cliente,
                "logradouro": str(dados_remetente.get('logradouro', ''))[:100],
                "numero": str(dados_remetente.get('numero', ''))[:10],
                "complemento": str(dados_remetente.get('complemento', ''))[:100],
                "bairro": str(dados_remetente.get('bairro', ''))[:100],
                "cidade": str(dados_remetente.get('cidade', ''))[:100],
                "uf": str(dados_remetente.get('uf', ''))[:2]
            }
        },
        
        "destinatario": {
            "nome": nome_fantasia[:100],
            "cpfCnpj": cnpj_empresa,
            "endereco": {
                "cep": cep_empresa,
                "logradouro": str(empresa.get('logradouro', ''))[:100],
                "numero": str(empresa.get('numero', ''))[:10],
                "complemento": str(empresa.get('complemento', ''))[:100],
                "bairro": str(empresa.get('bairro', ''))[:100],
                "cidade": str(empresa.get('cidade', ''))[:100],
                "uf": str(empresa.get('estado_uf', ''))[:2]
            }
        },
        "itensDeclaracaoConteudo": itens_formatados
    }

    token = obter_token_correios() 
    if not token:
        logging.error("Falha ao gerar Token OAuth2 dos Correios.")
        return None, None

    url_api = "https://api.correios.com.br/prepostagem/v1/prepostagens"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    try:
        resp = requests.post(url_api, json=payload, headers=headers, timeout=20)
        
        if resp.status_code in (200, 201):
            dados_resposta = resp.json()
            codigo_rastreio = dados_resposta.get('codigoObjeto')
            e_ticket = dados_resposta.get('eticket', codigo_rastreio)
            
            if codigo_rastreio:
                logging.info(f"SUCESSO REST! Código de Postagem: {codigo_rastreio}")
                return e_ticket, codigo_rastreio 
            else:
                logging.error(f"Sucesso HTTP, mas JSON sem código de rastreio: {resp.text}")
                return None, None
                
        elif resp.status_code == 400:
            logging.error(f"Erro 400 - Validação dos Correios: {resp.json().get('msgs', resp.text)}")
            return None, None
        else:
            logging.error(f"Falha na integração REST HTTP {resp.status_code}: {resp.text}")
            return None, None

    except Exception as e:
        logging.error(f"Erro interno no processamento JSON: {e}")
        return None, None

# --- INTEGRAÇÃO AGENTE WHATSAPP (FLUXO A) ---

def enviar_webhook_novo_protocolo(protocolo, cliente, itens_avaliados, total_pix, codigo_rastreio):
    """
    Monta o payload JSON e dispara o Gatilho A (Novo Protocolo) para o Agente de WhatsApp.
    """
    url_webhook = os.getenv('WEBHOOK_AGENTE_URL_A')
    
    if not url_webhook:
        logging.warning("WEBHOOK_AGENTE_URL_A não configurada no .env. Webhook não enviado.")
        return False

    ambiente = os.getenv('AMBIENTE_EXECUCAO', 'homologacao')
    telefone_limpo = ''.join(filter(str.isdigit, str(cliente.get('whatsapp', ''))))
    
    produtos_formatados = []
    for item in itens_avaliados:
        qtd = int(item.get('quantidade', 1))
        valor_un = float(item.get('valor_pix_unitario', 0.0))
        produtos_formatados.append({
            "nome": str(item.get('produto_nome', 'Produto')),
            "quantidade": qtd,
            "valor_unitario": valor_un,
            "valor_total": valor_un * qtd
        })

    payload = {
        "evento": "novo_protocolo",
        "dados": {
            "protocolo": str(protocolo),
            "cliente": str(cliente.get('nome_completo', '')),
            "email": str(cliente.get('email', '')),
            "telefone": telefone_limpo,
            "valor_total_cotacao": float(total_pix),
            "codigo_rastreio": str(codigo_rastreio) if codigo_rastreio else "",
            "ambiente": ambiente,
            "produtos": produtos_formatados
        }
    }

    headers = {
        "Content-Type": "application/json"
    }
    
    token_envio = os.getenv('AGENTE_TOKEN_ENVIO')
    if token_envio:
        headers["Authorization"] = f"Bearer {token_envio}"

    try:
        logging.info(f"Disparando Webhook (Fluxo A) para o Agente de WhatsApp. Protocolo: {protocolo}")
        resposta = requests.post(url_webhook, json=payload, headers=headers, timeout=3)
        
        if resposta.status_code in [200, 201]:
            logging.info("Webhook (Fluxo A) enviado com sucesso.")
            return True
        else:
            logging.error(f"Falha ao enviar Webhook (Fluxo A). Status: {resposta.status_code} - Resposta: {resposta.text}")
            return False
            
    except requests.exceptions.Timeout:
        logging.error("Timeout ao enviar Webhook (Fluxo A) para o Agente de WhatsApp.")
        return False
    except Exception as e:
        logging.error(f"Erro inesperado ao enviar Webhook (Fluxo A): {e}")
        return False