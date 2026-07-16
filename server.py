# ==============================================================================
# PROJETO: MyGames
# MÓDULO: server.py
# DATA DE CRIAÇÃO: 28/05/2026
# TÍTULO: Servidor Web e Roteamento Flask
# FUNÇÃO: Controladora principal da aplicação web. Gerencia todas as rotas (endpoints)
# do sistema, controla o fluxo de sessão do usuário (stepper), processa formulários, 
# gerencia uploads de arquivos e integra as chamadas ao módulo 'engine.py'. 
# Atua como a camada de interface entre o usuário e a lógica de negócio.
#
# HISTÓRICO DE ALTERAÇÕES:
# - 28/05/2026: Inclusão do cabeçalho padrão de documentação.
# - 29/05/2026: Integração do multiplicador de preço por região nas rotas definir_regiao e cotar.
# - 30/05/2026: Implementação do fluxo de handoff remoto (QR Code) para envio de mídias via mobile.
# - 01/06/2026: Parametrização do diretório de uploads via .env e criação da rota de mídia.
# - 01/06/2026: Correção na rota /cotar para processar corretamente a quantidade e cálculo de Lotes.
# - 01/06/2026: Refatoração na rota /cotar para forçar tipagem de dados e correção de Multiplicador Duplo.
# - 02/06/2026: Ajuste na rota /pericia para capturar e mapear corretamente o nome do produto e categoria.
# - 02/06/2026: Correção de regra na rota /pericia para exibir "Jogos" no badge em vez de "Lote".
# - 02/06/2026: Adição das rotas /termos_oferta, /aceitar_termos e /descartar-lote-final (Fluxo V2.9).
# - 02/06/2026: Correção de UnboundLocalError na rota /cotar ao processar itens 'outro_cat_'.
# - 03/06/2026: Atualização dos IDs chumbados nas rotas /pericia e /cotar para realinhar com a correção do banco de dados (Jogo=4, Acessório=3).
# - 04/06/2026: Correção na rota /cotar para passar o parâmetro de quantidade à engine e remoção de multiplicação redundante.
# - 04/06/2026: Implementação de roteamento dinâmico para mobile (render_smart_template) usando a biblioteca user-agents.
# - 07/06/2026: Correção de colisão de nomes de arquivos em uploads simultâneos via mobile (uso de enumerate na rota /cotar).
# - 10/06/2026: Recebimento e repasse dos dados de logística reversa (e-ticket e rastreio) na rota /finalizar.
# - 10/06/2026: Inclusão dos campos e_ticket e codigo_rastreio no dicionário dados_email para envio por e-mail.
# - 15/06/2026: Integração da rota /finalizar com a tabela dados_empresa para exibição dinâmica no sucesso.html.
# - 16/06/2026: Tratamento seguro da variável nome_fantasia na rota /finalizar com fallback para evitar erros de renderização no Jinja2.
# - 19/06/2026: Inclusão do repasse da variável categoria_nome na rota /cotar para exibição dinâmica no resultado.html.
# - 20/06/2026: Correção na injeção do dicionário de contatos na rota /finalizar para exibição correta no sucesso.html.
# - 22/06/2026: Criação do filtro customizado Jinja2 'moeda_real' para formatação global de valores monetários.
# - 22/06/2026: Criação do filtro customizado Jinja2 'mascara_telefone' para formatação de telefone/whatsapp na camada visual.
# - 22/06/2026: Implementação do Flask-Session (filesystem) para resolver estouro de limite de cookies e persistir o carrinho no servidor.
# - 23/06/2026: Atualização da rota /cotar para capturar 'pergunta_extra' do frontend e tratamento de exceção (ValueError) para a dupla barreira de validação do motor.
# - 25/06/2026: Extração dinâmica da URL do YouTube do .env na rota index para o modal de vídeo em boas_vindas.html.
# - 04/07/2026: Alteração na rota /resumo para calcular total_lote baseado no crédito e injetar a flag bloqueio_valor para a trava de R$ 300,00.
# - 04/07/2026: Alteração na rota /pericia para incluir a regra de exceção e injeção da flag 'permite_desbloqueio' para consoles (PS1, PS2 e PS Vita).
# - 04/07/2026: Refatoração da rota /cotar para utilizar valor_final_pix e valor_final_cred oficiais vindos do engine.py.
# - 06/07/2026: Correção de KeyError na rota /cotar aplicando tratamento seguro (.get) para extrair valores ausentes em itens 'Sob Consulta'.
# - 06/07/2026: Implementação de exceção para itens sob consulta (is_outros) na trava de valor mínimo de R$ 300,00 na rota /resumo.
# - 07/07/2026: Refatoração na rota /cotar para remover divisão manual de quantidades e corrigir estruturação do dicionário para itens lote (PIX e Crédito).
# - 07/07/2026: Correção na rota /resumo para calcular o total_lote utilizando valor_pix_unitario, alinhando com a intenção de venda do usuário e travando corretamente em R$ 300,00.
# - 15/07/2026: Adição da diretiva MAX_CONTENT_LENGTH (50MB) para alinhar limite de upload do Flask com Nginx em produção.
# ==============================================================================

import os
import json
import uuid
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime
from user_agents import parse # Biblioteca para detecção precisa do dispositivo
from flask_session import Session # NOVO: Importação para gerenciamento de sessão no servidor

# 1. Carrega variáveis de ambiente ANTES de importar o engine
load_dotenv(override=True)

# 2. Agora o engine entra, já enxergando as credenciais do banco mygames_dev
import engine  

app = Flask(__name__)
app.secret_key = 'mygames_key_2026'

# --- LIMITE DE UPLOAD ---
# Define o teto máximo de upload do Flask para 50MB, alinhado ao Nginx
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 

# --- NOVA CONFIGURAÇÃO DE SESSÃO NO SERVIDOR ---
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_FILE_DIR'] = os.path.join(app.root_path, 'flask_session')
Session(app)

# --- FUNÇÃO CORE DE ROTEAMENTO MOBILE ---
def render_smart_template(template_name, **context):
    """
    Inspeciona o User-Agent. Se for mobile, tenta renderizar o template da pasta 'mobile/'.
    Faz fallback automático para o template padrão caso a versão mobile não exista.
    """
    ua_string = request.headers.get('User-Agent', '')
    user_agent = parse(ua_string)
    
    if user_agent.is_mobile:
        mobile_template = f"mobile/{template_name}"
        caminho_template = os.path.join(app.root_path, 'templates', 'mobile', template_name)
        
        # Só direciona se o arquivo HTML mobile realmente existir na pasta
        if os.path.exists(caminho_template):
            return render_template(mobile_template, **context)
            
    # Se for desktop ou se o template mobile não existir, carrega o original
    return render_template(template_name, **context)

# --- FILTROS CUSTOMIZADOS PARA O JINJA2 ---
@app.template_filter('from_json')
def from_json_filter(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return []
    return value

# NOVO FILTRO: Formatação global de moeda para o padrão brasileiro
@app.template_filter('moeda_real')
def moeda_real_filter(valor):
    try:
        # Força conversão para float, formata com 2 casas decimais e troca ponto por vírgula
        return f"{float(valor):.2f}".replace('.', ',')
    except (ValueError, TypeError):
        return "0,00"

# NOVO FILTRO: Formatação de máscara para telefone/whatsapp na camada visual
@app.template_filter('mascara_telefone')
def mascara_telefone_filter(valor):
    if not valor:
        return ""
    
    # Remove tudo que não for número (garantia extra)
    numero_limpo = ''.join(filter(str.isdigit, str(valor)))
    
    # Máscara para celular com 11 dígitos: (XX) XXXXX-XXXX
    if len(numero_limpo) == 11:
        return f"({numero_limpo[:2]}) {numero_limpo[2:7]}-{numero_limpo[7:]}"
    
    # Máscara para telefone fixo com 10 dígitos: (XX) XXXX-XXXX
    elif len(numero_limpo) == 10:
        return f"({numero_limpo[:2]}) {numero_limpo[2:6]}-{numero_limpo[6:]}"
    
    # Retorna o valor original se não bater o tamanho esperado
    return valor

# --- CONFIGURAÇÃO DE UPLOADS ---
UPLOAD_FOLDER = os.getenv("DIRETORIO_UPLOADS_PERICIA", 'static/uploads/pericia')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if UPLOAD_FOLDER:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- ROTAS DE NAVEGAÇÃO ---

@app.route('/')
def index():
    session.clear()
    canais_do_banco = engine.buscar_canais_aquisicao() 
    
    # Captura a URL do .env (fallback de segurança caso não exista no .env)
    youtube_raw_url = os.getenv('YOUTUBE_URL_COMO_FUNCIONA', 'https://youtu.be/1P4PEJKoAAM')
    
    # Extrai o ID do vídeo (pega a última parte da URL e limpa possíveis parâmetros como ?si=...)
    video_id_raw = youtube_raw_url.split('/')[-1]
    video_id = video_id_raw.split('?')[0]
    
    # Monta a URL no formato embed exigido pelo iframe do HTML
    url_video_embed = f"https://www.youtube.com/embed/{video_id}?autoplay=1"
    
    return render_smart_template(
        'boas_vindas.html', 
        canais=canais_do_banco,
        url_video_como_funciona=url_video_embed
    )

@app.route('/definir_regiao', methods=['POST'])
def definir_regiao():
    cidade = request.form.get('cidade')
    estado_uf = request.form.get('estado_uf')
    
    session['cidade_usuario'] = cidade
    session['uf_usuario'] = estado_uf
    session['canal_aquisicao_id'] = request.form.get('canal_aquisicao_id') 
    session['multiplicador_regiao'] = engine.obter_multiplicador_regiao(cidade, estado_uf)
    
    return redirect(url_for('produto'))

@app.route('/produto')
def produto():
    if 'itens_avaliados' not in session:
        session['itens_avaliados'] = []
    return render_smart_template('produto.html', fase_atual=1)

@app.route('/pericia/<produto_id>')
def pericia(produto_id):
    if str(produto_id).startswith('cat_') or str(produto_id).startswith('outro_cat_'):
        categoria_id = str(produto_id).split('_')[-1]
        id_oficial = produto_id
        session['is_outros'] = str(produto_id).startswith('outro_cat_')
        
        if str(produto_id).startswith('cat_'):
            if str(categoria_id) == '4':
                produto_nome = "Lote de Jogos"
                categoria_nome = "Jogos"
            else:
                produto_nome = "Lote"
                categoria_nome = "Lote"
        else:
            produto_nome = "Produto não listado"
            categoria_nome = "Outros"
    else:
        session['is_outros'] = False
        produto = engine.obter_produto_por_id(produto_id)
        if not produto:
            return redirect(url_for('produto'))
        categoria_id = produto.get('categoria_id')
        id_oficial = produto['id']
        produto_nome = produto.get('nome_produto', 'Produto')
        
        mapa_categorias = {
            '1': 'Console',
            '2': 'Controle',
            '3': 'Acessório',
            '4': 'Jogo'
        }
        categoria_nome = mapa_categorias.get(str(categoria_id), 'Outros')
    
    opcoes = engine.buscar_opcoes_pericia(categoria_id)
    session['produto_selecionado_id'] = id_oficial
    session['produto_nome'] = produto_nome
    session['categoria_nome'] = categoria_nome
    
    token_sessao = str(uuid.uuid4())
    
    # Nova Regra: Exceção para consoles desbloqueados (PS1, PS2, PS Vita)
    permite_desbloqueio = False
    if str(categoria_id) == '1' or categoria_nome == 'Console':
        nome_lower = produto_nome.lower()
        excecoes = ['ps1', 'playstation 1', 'ps2', 'playstation 2', 'vita']
        if any(exc in nome_lower for exc in excecoes):
            permite_desbloqueio = True
    else:
        # Se não for console, a regra de desbloqueio não se aplica (liberado por padrão ou irrelevante)
        permite_desbloqueio = True 
    
    return render_smart_template(
        'pericia.html', 
        opcoes=opcoes, 
        produto_id=id_oficial, 
        fase_atual=1, 
        categoria_id=categoria_id, 
        token_sessao=token_sessao,
        produto_nome=produto_nome,
        categoria_nome=categoria_nome,
        permite_desbloqueio=permite_desbloqueio
    )

# 3ª TELA: CÁLCULO E EXIBIÇÃO DA COTAÇÃO
@app.route('/cotar', methods=['POST'])
def cotar():
    produto_id = session.get('produto_selecionado_id')
    estado_id = request.form.get('estado_id')
    comentarios = request.form.get('comentarios', '')
    pergunta_extra = request.form.get('pergunta_extra', '') 
    
    qtd_fisica_str = str(request.form.get('qtd_fisica', '1')).strip()
    qtd_digital_str = str(request.form.get('qtd_digital', '0')).strip()
    
    try:
        qtd_fisica = int(qtd_fisica_str) if qtd_fisica_str.isdigit() else 1
    except ValueError:
        qtd_fisica = 1
        
    try:
        qtd_digital = int(qtd_digital_str) if qtd_digital_str.isdigit() else 0
    except ValueError:
        qtd_digital = 0

    fotos_salvas = []
    
    if 'fotos' in request.files:
        files = request.files.getlist('fotos')
        for idx, file in enumerate(files):
            if file and allowed_file(file.filename):
                ts = datetime.now().strftime("%H%M%S")
                cli_prefix = session.get('cliente_id', 'anon')
                filename = secure_filename(f"cli{cli_prefix}_prod{produto_id}_{ts}_{idx}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                fotos_salvas.append(filename)

    token_sessao = request.form.get('token_sessao')
    if token_sessao:
        pasta_token = os.path.join(app.config['UPLOAD_FOLDER'], token_sessao)
        if os.path.exists(pasta_token):
            for idx, file_name in enumerate(os.listdir(pasta_token)):
                if allowed_file(file_name):
                    ts = datetime.now().strftime("%H%M%S")
                    cli_prefix = session.get('cliente_id', 'anon')
                    novo_nome = secure_filename(f"cli{cli_prefix}_prod{produto_id}_{ts}_mobile_{idx}_{file_name}")
                    
                    caminho_antigo = os.path.join(pasta_token, file_name)
                    caminho_novo = os.path.join(app.config['UPLOAD_FOLDER'], novo_nome)
                    
                    os.rename(caminho_antigo, caminho_novo)
                    fotos_salvas.append(novo_nome)
            try:
                os.rmdir(pasta_token)
            except Exception:
                pass

    multiplicador = session.get('multiplicador_regiao', 1.00)
    qtd_final_calculo = qtd_fisica

    if str(produto_id).startswith('cat_') or str(produto_id).startswith('outro_cat_'):
        session['is_outros'] = str(produto_id).startswith('outro_cat_')
        categoria_id_str = str(produto_id).split('_')[-1]
        
        try:
            cat_id_int = int(categoria_id_str)
        except ValueError:
            cat_id_int = 4 
            
        if str(produto_id).startswith('cat_'):
            
            if qtd_digital > 0:
                comentarios += f" [Mídia Digital informada: {qtd_digital} un]"
                
            try:
                est_id_int = int(estado_id) if estado_id else 0
            except ValueError:
                est_id_int = 0

            try:
                resultado_unitario = engine.calcular_cotacao_final(cat_id_int, est_id_int, multiplicador, quantidade=qtd_final_calculo, pergunta_extra=pergunta_extra)
            except ValueError as e:
                return f"Bloqueio de Segurança: {str(e)}", 403
            
            if resultado_unitario and resultado_unitario.get('valor_final') is not None:
                 # CORREÇÃO: Resgata explicitamente PIX e Crédito do motor
                 valor_unitario_pix = float(resultado_unitario.get('valor_final_pix', resultado_unitario.get('valor_final', 0.0)))
                 valor_unitario_cred = float(resultado_unitario.get('valor_final_cred', resultado_unitario.get('valor_final', 0.0)))
                 resultado = {
                    "produto": f"Lote de Jogos ({qtd_final_calculo}x)",
                    "valor_final": valor_unitario_pix, 
                    "valor_final_pix": valor_unitario_pix,
                    "valor_final_cred": valor_unitario_cred,
                    "multiplicador_aplicado": multiplicador
                 }
            else:
                resultado = {
                    "produto": f"Lote de Jogos ({qtd_final_calculo}x)",
                    "valor_final": 0.0,
                    "valor_final_pix": 0.0,
                    "valor_final_cred": 0.0,
                    "multiplicador_aplicado": multiplicador
                }
        else:
            resultado = {
                "produto": "Produto não listado",
                "valor_final": 0.0,
                "valor_final_pix": 0.0,
                "valor_final_cred": 0.0,
                "multiplicador_aplicado": multiplicador
            }
            
        foto_url_final = None
    else:
        session['is_outros'] = False
        try:
            prod_id_int = int(produto_id)
            est_id_int = int(estado_id) if estado_id else 0
        except ValueError:
            prod_id_int = produto_id
            est_id_int = estado_id

        try:
            resultado = engine.calcular_cotacao_final(prod_id_int, est_id_int, multiplicador, quantidade=qtd_final_calculo, pergunta_extra=pergunta_extra)
        except ValueError as e:
            return f"Bloqueio de Segurança: {str(e)}", 403
            
        produto_info = engine.obter_produto_por_id(prod_id_int)
        categoria_id = produto_info.get('categoria_id') if produto_info else 1
        foto_url_final = produto_info.get('foto_oficial_url') if produto_info else None

    if resultado:
        resultado['foto_url'] = foto_url_final
        
        opcoes = engine.buscar_opcoes_pericia(categoria_id if 'categoria_id' in locals() else cat_id_int)
        descricao_estado = "Estado Selecionado"
        if opcoes:
            for op in opcoes:
                if str(op.get('id')) == str(estado_id):
                    descricao_estado = op.get('descricao')
                    break
        
        resultado['descricao'] = descricao_estado

        # CORREÇÃO CIRÚRGICA: Remoção da divisão por quantidade. 
        # O motor agora devolve o valor unitário purificado.
        valor_unit_pix = float(resultado.get('valor_final_pix', resultado.get('valor_final', 0.0)))
        valor_unit_cred = float(resultado.get('valor_final_cred', resultado.get('valor_final', 0.0)))

        novo_item = {
            'produto_id': produto_id,
            'produto_nome': resultado['produto'],
            'valor_pix_unitario': valor_unit_pix,
            'valor_cred_unitario': valor_unit_cred,
            'fotos_json': json.dumps(fotos_salvas), 
            'comentarios': comentarios,
            'quantidade': qtd_final_calculo, # Quantidade preservada para uso futuro no carrinho e e-mail
            'estado_descricao': descricao_estado,
            'foto_url': foto_url_final,
            'is_outros': session.get('is_outros', False),
            'multiplicador_aplicado': resultado.get('multiplicador_aplicado', 1.00)
        }
        
        lista_atual = session.get('itens_avaliados', [])
        lista_atual.append(novo_item)
        session['itens_avaliados'] = lista_atual
        session['item_atual'] = novo_item 
        
        cat_nome = session.get('categoria_nome', 'Produto')
        
        # --- ADICIONE ESTA LINHA AQUI ---
        # Multiplicamos o valor unitário pela quantidade apenas para o visual da tela de resultado
        resultado['valor_final'] = valor_unit_pix * qtd_final_calculo
        
        return render_smart_template('resultado.html', cotacao=resultado, fase_atual=2, categoria_nome=cat_nome)
    
    return "Erro ao calcular cotação.", 500


# 4ª TELA: NOVO RESUMO DO LOTE
@app.route('/resumo')
def resumo():
    itens = session.get('itens_avaliados', [])
    if not itens:
        return redirect(url_for('produto'))
    
    # CORREÇÃO: O total do lote e a validação agora consideram estritamente o valor PIX (venda real)
    total_lote = sum(item['valor_pix_unitario'] * item.get('quantidade', 1) for item in itens)
    
    # NOVA EXCEÇÃO: Identifica se existe algum item configurado como "Sob Consulta" (fora do catálogo mestre)
    tem_item_sob_consulta = any(item.get('is_outros') for item in itens)
    
    # A trava de valor mínimo só será ativada se o total for menor que R$ 300,00 E não houver itens sob consulta
    bloqueio_valor = total_lote < 300.0 and not tem_item_sob_consulta
    
    return render_smart_template('resumo_lote.html', itens=itens, total_lote=total_lote, bloqueio_valor=bloqueio_valor, fase_atual=4)

@app.route('/descartar-lote')
def descartar_lote():
    session.pop('itens_avaliados', None)
    session.pop('item_atual', None)
    session.pop('produto_selecionado_id', None)
    return redirect(url_for('produto'))

@app.route('/descartar-atual')
def descartar_atual():
    lista_atual = session.get('itens_avaliados', [])
    if lista_atual:
        lista_atual.pop()
        session['itens_avaliados'] = lista_atual
    session.pop('item_atual', None)
    session.pop('produto_selecionado_id', None)
    return jsonify({'status': 'sucesso', 'mensagem': 'Avaliação descartada com sucesso.'})


# ==============================================================================
# 4.5 TELA: TERMOS DA OFERTA E BARREIRA DE VALIDAÇÃO (NOVO FLUXO V2.9)
# ==============================================================================
@app.route('/termos_oferta')
def termos_oferta():
    itens = session.get('itens_avaliados', [])
    if not itens:
        return redirect(url_for('produto'))
    return render_smart_template('termos_oferta.html', fase_atual=4)

@app.route('/aceitar_termos', methods=['POST'])
def aceitar_termos():
    return redirect(url_for('identificacao'))

@app.route('/descartar-lote-final', methods=['POST'])
def descartar_lote_final():
    dados = request.get_json()
    motivo = dados.get('motivo', '') if dados else ''
    
    itens = session.get('itens_avaliados', [])
    
    ip_origem = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip_origem and ',' in ip_origem:
        ip_origem = ip_origem.split(',')[0].strip()

    valor_oferta = sum(item['valor_pix_unitario'] * item.get('quantidade', 1) for item in itens) if itens else 0.0
    
    dados_feedback = {
        'sessao_uuid': str(uuid.uuid4()),
        'motivo_texto': motivo,
        'cidade_informada': session.get('cidade_usuario', ''),
        'estado_uf': session.get('uf_usuario', ''),
        'canal_aquisicao': session.get('canal_aquisicao_id', ''),
        'valor_oferta_recusada': valor_oferta,
        'itens_carrinho_json': json.dumps(itens),
        'user_agent': request.headers.get('User-Agent', ''),
        'ip_origem': ip_origem
    }
    
    try:
        engine.salvar_feedback_recusa(dados_feedback)
    except Exception as e:
        print(f"Erro ao salvar feedback de recusa: {e}")
        
    session.pop('itens_avaliados', None)
    session.pop('item_atual', None)
    session.pop('produto_selecionado_id', None)
    
    return jsonify({'status': 'sucesso', 'mensagem': 'Lote descartado e feedback registrado com sucesso.'}), 200


# 5ª TELA: CADASTRO COMPLETO UNIFICADO
@app.route('/identificacao', methods=['GET'])
def identificacao():
    itens = session.get('itens_avaliados', [])
    if not itens:
        return redirect(url_for('produto'))
    
    return render_smart_template('cadastro_complementar.html', fase_atual=5, cliente={})

@app.route('/finalizar-lote', methods=['POST'])
def finalizar_lote():
    itens = session.get('itens_avaliados', [])
    if not itens:
        return redirect(url_for('produto'))
    
    cpf_puro = ''.join(filter(str.isdigit, request.form.get('cpf', '')))
    cep_puro = ''.join(filter(str.isdigit, request.form.get('cep', '')))
    whatsapp_puro = ''.join(filter(str.isdigit, request.form.get('whatsapp', '')))
        
    dados_cadastro_lote = {
        'nome_completo': request.form.get('nome'),  
        'email': request.form.get('email'),
        'whatsapp': whatsapp_puro,  
        'cidade': request.form.get('cidade'),
        'estado_nome': request.form.get('estado_nome'),
        'estado_uf': request.form.get('estado_uf'),
        'cpf': cpf_puro,  
        'cep': cep_puro,  
        'endereco': request.form.get('endereco'),
        'numero': request.form.get('numero'),
        'complemento': request.form.get('complemento'),
        'bairro': request.form.get('bairro'),
        'chave_pix': request.form.get('chave_pix'),
        'origem_lead': request.form.get('origem_lead', 'Direto')
    }

    cliente_id = engine.salvar_lead(dados_cadastro_lote)

    if cliente_id:
        engine.atualizar_cadastro_completo(cliente_id, dados_cadastro_lote)
        
        session['cliente_id'] = cliente_id
        session['player_nome'] = dados_cadastro_lote['nome_completo']
        session['player_email'] = dados_cadastro_lote['email']
        
        return redirect(url_for('finalizar'))
        
    return "Erro na identificacao do lote.", 500

# 6ª TELA: PROCESSAMENTO DE PROTOCOLO E FINALIZAÇÃO
@app.route('/finalizar', methods=['GET', 'POST'])
def finalizar():
    if 'cliente_id' not in session:
        return redirect(url_for('identificacao'))

    cliente_id = session.get('cliente_id')
    itens = session.get('itens_avaliados', [])

    if not itens:
        return redirect(url_for('produto'))

    cliente = engine.obter_cliente(cliente_id)
    
    total_pix = sum(item['valor_pix_unitario'] * item.get('quantidade', 1) for item in itens)
    total_cred = sum(item['valor_cred_unitario'] * item.get('quantidade', 1) for item in itens)

    dados_protocolo = {
        'cliente_id': cliente_id,
        'total_pix': total_pix,
        'total_cred': total_cred,
        'canal_aquisicao_id': session.get('canal_aquisicao_id') 
    }

    res_protocolo = engine.finalizar_proposta(dados_protocolo)

    if res_protocolo:
        for item in itens:
            produto_id_original = item.get('produto_id')
            item['produto_id'] = int(produto_id_original) if str(produto_id_original).isdigit() else 0
            
            engine.registrar_item_periciado(res_protocolo['id'], item)
        
        e_ticket = res_protocolo.get('e_ticket')
        codigo_rastreio = res_protocolo.get('codigo_rastreio')

        # Busca dados atualizados da empresa na tabela dados_empresa
        empresa = engine.obter_dados_empresa()
        
        # Fallback seguro: se a tabela estiver vazia, define um padrão
        nome_fantasia_seguro = empresa.get('nome_fantasia', 'MyGames') if empresa else 'MyGames'

        dados_email = {
            'protocolo': res_protocolo['numero'],
            'quantidade_itens': len(itens),
            'total_pix': total_pix,
            'e_ticket': e_ticket,
            'codigo_rastreio': codigo_rastreio
        }
        
        # Envia o e-mail
        engine.enviar_email_resumo(cliente, dados_email, itens)
        
        return render_smart_template(
            'sucesso.html', 
            protocolo=res_protocolo['numero'], 
            total_lote=total_pix, 
            fase_atual=6,
            e_ticket=e_ticket,
            codigo_rastreio=codigo_rastreio,
            nome_fantasia=nome_fantasia_seguro,
            dados_empresa=empresa,
            empresa=empresa 
        )
    
    return "Erro ao finalizar agendamento.", 500

@app.route('/api/obter_cliente_por_cpf')
def api_obter_cliente_por_cpf():
    cpf_raw = request.args.get('cpf', '')
    cpf_limpo = ''.join(filter(str.isdigit, cpf_raw))
    
    if not cpf_limpo or len(cpf_limpo) != 11:
        return jsonify({'sucesso': False, 'existe': False})
        
    try:
        cliente_dados = engine.obter_cliente_por_cpf(cpf_limpo)
        
        if cliente_dados:
            return jsonify({
                'sucesso': True,
                'existe': True,
                'cliente': {
                    'nome_completo': cliente_dados.get('nome_completo', ''),
                    'nome': cliente_dados.get('nome_completo', ''),  
                    'email': cliente_dados.get('email', ''),
                    'whatsapp': cliente_dados.get('whatsapp', ''),
                    'cep': cliente_dados.get('cep', ''),
                    'bairro': cliente_dados.get('bairro', ''),
                    'endereco': cliente_dados.get('endereco', ''),
                    'numero': cliente_dados.get('numero', ''),
                    'complemento': cliente_dados.get('complemento', ''),
                    'cidade': cliente_dados.get('cidade', ''),
                    'estado_uf': cliente_dados.get('estado_uf', ''),
                    'estado_nome': cliente_dados.get('estado_nome', ''),
                    'chave_pix': cliente_dados.get('chave_pix', '')
                }
            })
    except Exception as e:
        print(f"Erro na API de CPF: {e}")
        
    return jsonify({'sucesso': False, 'existe': False})

@app.route('/sair')
def sair():
    session.clear()
    return redirect(url_for('index'))

@app.route('/api/buscar_produtos')
def api_buscar_produtos():
    categoria_id = request.args.get('categoria_id', '')
    if not categoria_id:
        return jsonify([])
    produtos = engine.buscar_produtos_por_categoria(categoria_id)
    return jsonify(produtos)

@app.route('/api/buscar_cidades')
def api_buscar_cidades():
    termo = request.args.get('q', '')
    if not termo or len(termo) < 3:
        return jsonify([])

    dados = engine.consultar_municipios_ibge()
    cidades_filtradas = []
    
    if dados:
        for m in dados:
            nome_cidade = m.get('nome', '')
            if termo.lower() in nome_cidade.lower():
                micro = m.get('microrregiao') or {}
                meso = micro.get('mesorregiao') or {}
                uf_obj = meso.get('UF') or {}
                uf = uf_obj.get('sigla', '??')
                
                cidades_filtradas.append({'cidade': nome_cidade, 'uf': uf})
                if len(cidades_filtradas) >= 8:
                    break

    return jsonify(cidades_filtradas)

# --- ENDPOINTS DE HANDOFF E UPLOAD REMOTO (MOBILE) ---

@app.route('/upload-remoto/<token>', methods=['GET'])
def tela_upload_mobile(token):
    return render_smart_template('upload_mobile.html', token=token)

@app.route('/api/upload-mobile/<token>', methods=['POST'])
def receber_fotos_mobile(token):
    if 'fotos_pericia' not in request.files:
        return jsonify({'erro': 'Nenhuma foto enviada'}), 400

    arquivos = request.files.getlist('fotos_pericia')
    pasta_token = os.path.join(app.config['UPLOAD_FOLDER'], token)
    os.makedirs(pasta_token, exist_ok=True)
    
    fotos_salvas_count = 0
    for arquivo in arquivos:
        if arquivo and allowed_file(arquivo.filename):
            nome_seguro = secure_filename(arquivo.filename)
            caminho_completo = os.path.join(pasta_token, nome_seguro)
            arquivo.save(caminho_completo)
            fotos_salvas_count += 1

    if fotos_salvas_count == 0:
        return jsonify({'erro': 'Nenhum arquivo válido foi salvo'}), 400

    return jsonify({'sucesso': True, 'quantidade': fotos_salvas_count}), 200

@app.route('/api/status-upload/<token>', methods=['GET'])
def checar_status_upload(token):
    pasta_token = os.path.join(app.config['UPLOAD_FOLDER'], token)
    if os.path.exists(pasta_token):
        fotos = [f for f in os.listdir(pasta_token) if allowed_file(f)]
        if len(fotos) > 0:
            caminhos = [f"/media/pericia/{token}/{foto}" for foto in fotos]
            return jsonify({'status': 'concluido', 'fotos': caminhos}), 200
            
    return jsonify({'status': 'aguardando'}), 200

@app.route('/media/pericia/<path:nome_arquivo>')
def media_pericia(nome_arquivo):
    return send_from_directory(app.config['UPLOAD_FOLDER'], nome_arquivo)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)