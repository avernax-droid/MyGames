import mysql.connector
from mysql.connector import Error
from decimal import Decimal
import datetime
import smtplib
import json
import requests  # <-- ADICIONADO PARA A CONSULTA AO IBGE
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def conectar_bd():
    """
    Configuração para o ambiente WSL2/Ubuntu do MyGames.
    Usa 127.0.0.1 para evitar problemas de DNS (Porta 3307).
    """
    try:
        connection = mysql.connector.connect(
            host="127.0.0.1",
            port=3307,
            user="dev_gamer",
            password="projeto123",
            database="mygames_db"
        )
        return connection
    except Error as e:
        print(f"ERRO CRÍTICO: Falha na conexão com o MySQL (Porta 3307): {e}")
        return None

# --- MÓDULO DE IDENTIFICAÇÃO (ETAPA 1) ---

def salvar_lead(dados):
    """
    Insere ou updates os dados do cliente conforme colunas exatas do DB.
    Garante que CPF e CEP sejam tratados na persistência inicial se fornecidos.
    """
    db = conectar_bd()
    if not db: return None
    try:
        # CORREÇÃO: buffered=True adicionado para evitar dados pendentes no fetchone() do ELSE
        cursor = db.cursor(dictionary=True, buffered=True)
        
        whatsapp_limpo = ''.join(filter(str.isdigit, str(dados['whatsapp'])))
        cpf_limpo = ''.join(filter(str.isdigit, str(dados.get('cpf', '')))) if dados.get('cpf') else None
        cep_limpo = ''.join(filter(str.isdigit, str(dados.get('cep', '')))) if dados.get('cep') else None

        sql = """
            INSERT INTO clientes_usuarios 
            (nome_completo, email, whatsapp, cidade, estado_nome, estado_uf, origem_lead, cpf, cep) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
            nome_completo = VALUES(nome_completo),
            whatsapp = VALUES(whatsapp),
            cidade = VALUES(cidade),
            estado_nome = VALUES(estado_nome),
            estado_uf = VALUES(estado_uf),
            cpf = COALESCE(VALUES(cpf), cpf),
            cep = COALESCE(VALUES(cep), cep)
        """
        valores = (
            dados['nome_completo'], 
            dados['email'], 
            whatsapp_limpo,
            dados['cidade'], 
            dados.get('estado_nome'), 
            dados.get('estado_uf'),   
            dados['origem_lead'],
            cpf_limpo,      
            cep_limpo       
        )
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

# --- MÓDULO DE GESTÃO DE CLIENTES ---

def obter_cliente(cliente_id):
    db = conectar_bd()
    if not db: return {}
    try:
        # CORREÇÃO: buffered=True adicionado por segurança
        cursor = db.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT * FROM clientes_usuarios WHERE id = %s", (cliente_id,))
        return cursor.fetchone() or {}
    finally:
        if db.is_connected():
            cursor.close()
            db.close()

def obter_cliente_por_cpf(cpf_num):
    """
    Executa a busca exata utilizando o CPF puramente numérico
    direto contra a tabela de clientes do banco MySQL.
    """
    db = conectar_bd()
    if not db: return None
    try:
        # CORREÇÃO CRÍTICA: buffered=True resolve o erro Unread Result Found nesta consulta
        cursor = db.cursor(dictionary=True, buffered=True)
        sql = "SELECT * FROM clientes_usuarios WHERE cpf = %s"
        cursor.execute(sql, (cpf_num,))
        return cursor.fetchone()
    except Error as e:
        print(f"ERRO ao buscar cliente por CPF: {e}")
        return None
    finally:
        if db.is_connected():
            cursor.close()
            db.close()

def atualizar_cadastro_completo(cliente_id, dados):
    """
    Atualiza dados do Level 5 usando a nomenclatura correta da tabela.
    Garante persistência de dados higienizados sem máscaras de string.
    """
    db = conectar_bd()
    if not db: return False
    try:
        cursor = db.cursor()
        
        cpf_limpo = ''.join(filter(str.isdigit, str(dados.get('cpf', ''))))
        cep_limpo = ''.join(filter(str.isdigit, str(dados.get('cep', ''))))
        whatsapp_limpo = ''.join(filter(str.isdigit, str(dados.get('whatsapp', ''))))

        sql = """
            UPDATE clientes_usuarios 
            SET cpf = %s, cep = %s, whatsapp = %s, endereco = %s, numero = %s,
                complemento = %s, bairro = %s, chave_pix = %s
            WHERE id = %s
        """
        valores = (
            cpf_limpo, 
            cep_limpo,
            whatsapp_limpo,
            dados.get('endereco'), 
            dados.get('numero'), 
            dados.get('complemento'), 
            dados.get('bairro'),
            dados.get('chave_pix'), 
            cliente_id
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

# --- MÓDULO DE PERÍCIA E CÁLCULOS ---

def obter_produto_por_id(produto_id):
    db = conectar_bd()
    if not db: return None
    try:
        cursor = db.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT * FROM catalogo_mestre WHERE id = %s", (produto_id,))
        return cursor.fetchone()
    finally:
        if db.is_connected():
            cursor.close()
            db.close()

def calcular_cotacao_final(produto_id, estado_id):
    db = conectar_bd()
    if not db: return None
    try:
        cursor = db.cursor(dictionary=True, buffered=True)
        
        # CORREÇÃO VISUAL: obter_produto_por_id abre e fecha a própria conexão internamente,
        # o que gerava conflitos se o cursor principal desta função estivesse aberto.
        produto = obter_produto_por_id(produto_id)
        if not produto: return None
        
        cursor.execute("SELECT fator_depreciacao FROM opcoes_estado WHERE id = %s", (estado_id,))
        estado = cursor.fetchone()
        fator = Decimal(str(estado['fator_depreciacao'])) if estado else Decimal('1.0')

        valor_final = Decimal(str(produto['valor_pix_base'])) * fator

        return {
            "produto": produto['nome_produto'],
            "valor_final": float(valor_final)
        }
    except Exception as e:
        print(f"ERRO no cálculo de cotação: {e}")
        return None
    finally:
        if db.is_connected():
            cursor.close()
            db.close()

def registrar_item_periciado(protocolo_id, item):
    """
    Grava o item na tabela itens_periciados vinculando ao protocolo.
    """
    db = conectar_bd()
    if not db: return False
    try:
        cursor = db.cursor()
        sql = """
            INSERT INTO itens_periciados 
            (protocolo_id, produto_id, quantidade, fotos_json, comentarios, 
             valor_pix_unitario, valor_cred_unitario) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        valores = (
            protocolo_id, 
            item['produto_id'], 
            item.get('quantidade', 1),
            item.get('fotos_json'), 
            item.get('comentarios', ''),
            item['valor_pix_unitario'], 
            item['valor_cred_unitario']
        )
        cursor.execute(sql, valores)
        db.commit()
        return True
    except Error as e:
        print(f"ERRO ao registrar item periciado: {e}")
        return False
    finally:
        if db.is_connected():
            cursor.close()
            db.close()

# --- MÓDULO DE FINALIZAÇÃO E E-MAIL ---

def enviar_email_resumo(cliente, dados_email, itens_avaliados):
    """
    Monta um demonstrativo financeiro detalhado com todos os produtos avaliados,
    seus respectivos estados físicos e comentários da perícia.
    """
    try:
        remetente = "avernax@gmail.com" 
        senha_app = "nmmawgxrhuyzfpoe" 
        destinatario = cliente['email']
        
        msg = MIMEMultipart()
        msg['From'] = remetente
        msg['To'] = destinatario
        msg['Subject'] = f"Confirmação MyGames - Protocolo {dados_email['protocolo']}"
        
        corpo = f"Olá {cliente['nome_completo']},\n\n"
        corpo += f"Sua proposta de venda em lote foi registrada com sucesso!\n"
        corpo += f"Número do Protocolo: {dados_email['protocolo']}\n"
        corpo += f"Quantidade de Itens: {dados_email['quantidade_itens']}\n\n"
        corpo += "========================================================\n"
        corpo += "            DEMONSTRATIVO DOS ITENS AVALIADOS          \n"
        corpo += "========================================================\n\n"
        
        for i, item in enumerate(itens_avaliados, 1):
            nome_item = item.get('produto_nome') or item.get('produto_name') or 'Item'
            corpo += f"{i}. Produto: {nome_item}\n"
            corpo += f"  Estado Periciado: {item.get('estado_descricao', 'Não especificado')}\n"
            if item.get('comentarios'):
                corpo += f"  Notas do Perito: {item['comentarios']}\n"
            corpo += f"  Valor de Compra: R$ {item['valor_pix_unitario']:.2f} (PIX)\n"
            corpo += "--------------------------------------------------------\n"
            
        corpo += f"\nVALOR TOTAL CONSOLIDADO DO LOTE: R$ {dados_email['total_pix']:.2f}\n\n"
        corpo += "Obrigado por vender na MyGames!"
        
        msg.attach(MIMEText(corpo, 'plain'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remetente, senha_app)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"ERRO NO ENVIO DE E-MAIL DETALHADO: {e}")
        return False

def finalizar_proposta(dados_proposta):
    db = conectar_bd()
    if not db: return None
    try:
        cursor = db.cursor()
        agora = datetime.datetime.now()
        timestamp = agora.strftime("%H%M%S")
        protocolo = f"MG-{agora.year}-{dados_proposta['cliente_id']}-{timestamp}"
        
        # CORREÇÃO CRÍTICA: Tabela alterada de 'protocols_recompra' para 'protocolos_recompra'
        sql = """
            INSERT INTO protocolos_recompra 
            (cliente_id, numero_protocolo, status, valor_total_pix, valor_total_credito, data_criacao) 
            VALUES (%s, %s, 'Aberto', %s, %s, NOW())
        """
        valores = (dados_proposta['cliente_id'], protocolo, dados_proposta['total_pix'], dados_proposta['total_cred'])
        cursor.execute(sql, valores)
        protocolo_id = cursor.lastrowid
        db.commit()
        return {"id": protocolo_id, "numero": protocolo}
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
        cursor = db.cursor(dictionary=True, buffered=True)
        query = """
            SELECT id, nome_produto, plataforma, foto_oficial_url, valor_pix_base, valor_cred_base
            FROM catalogo_mestre 
            WHERE (nome_produto LIKE %s OR plataforma LIKE %s OR sku_interno LIKE %s)
            AND ativo = 1 LIMIT 10
        """
        like_termo = f"%{termo}%"
        cursor.execute(query, (like_termo, like_termo, like_termo))
        return cursor.fetchall()
    finally:
        if db.is_connected():
            cursor.close()
            db.close()

def buscar_opcoes_pericia(tipo_produto='Todos'):
    db = conectar_bd()
    if not db: return []
    try:
        cursor = db.cursor(dictionary=True, buffered=True)
        query = """
            SELECT o.id, o.descricao, o.fator_depreciacao, c.nome_categoria 
            FROM opcoes_estado o
            JOIN categorias_avaliacao c ON o.categoria_id = c.id
            WHERE c.tipo_produto = %s OR c.tipo_produto = 'Todos'
            ORDER BY c.id, o.exibir_ordem
        """
        cursor.execute(query, (tipo_produto,))
        return cursor.fetchall()
    except Error as e:
        print(f"ERRO ao buscar opções: {e}")
        return []
    finally:
        if db.is_connected():
            cursor.close()
            db.close()

# --- MÓDULO DE INTEGRAÇÃO EXTERNA ---

def consultar_municipios_ibge():
    """
    Acessa a API oficial do IBGE para trazer a lista de cidades brasileiras.
    Retorna o JSON bruto para que a rota no server.py faça a filtragem otimizada.
    """
    url = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
    try:
        # Definindo um timeout para não travar a thread do Flask caso o IBGE caia
        response = requests.get(url, timeout=5)
        response.raise_for_status() 
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"ERRO ao consultar API do IBGE: {e}")
        return []