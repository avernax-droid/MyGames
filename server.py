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
# ==============================================================================

import os
import json
import uuid
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime

# 1. Carrega variáveis de ambiente ANTES de importar o engine
load_dotenv()

# 2. Agora o engine entra, já enxergando as credenciais do banco mygames_dev
import engine  

app = Flask(__name__)
app.secret_key = 'mygames_key_2026'

# --- FILTROS CUSTOMIZADOS PARA O JINJA2 ---
@app.template_filter('from_json')
def from_json_filter(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return []
    return value

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
    return render_template('boas_vindas.html', canais=canais_do_banco)

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
    return render_template('produto.html', fase_atual=1)

@app.route('/pericia/<produto_id>')
def pericia(produto_id):
    if str(produto_id).startswith('cat_') or str(produto_id).startswith('outro_cat_'):
        categoria_id = str(produto_id).split('_')[-1]
        id_oficial = produto_id
        session['is_outros'] = str(produto_id).startswith('outro_cat_')
        
        if str(produto_id).startswith('cat_'):
            # CORREÇÃO: Atualizado para o ID correto da categoria de Jogos (4)
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
        
        # CORREÇÃO: Atualizados os IDs 3 (Acessório) e 4 (Jogo) para o padrão do banco
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
    
    return render_template(
        'pericia.html', 
        opcoes=opcoes, 
        produto_id=id_oficial, 
        fase_atual=1, 
        categoria_id=categoria_id, 
        token_sessao=token_sessao,
        produto_nome=produto_nome,
        categoria_nome=categoria_nome
    )

# 3ª TELA: CÁLCULO E EXIBIÇÃO DA COTAÇÃO
@app.route('/cotar', methods=['POST'])
def cotar():
    produto_id = session.get('produto_selecionado_id')
    estado_id = request.form.get('estado_id')
    comentarios = request.form.get('comentarios', '')
    
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
        for file in files:
            if file and allowed_file(file.filename):
                ts = datetime.now().strftime("%H%M%S")
                cli_prefix = session.get('cliente_id', 'anon')
                filename = secure_filename(f"cli{cli_prefix}_prod{produto_id}_{ts}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                fotos_salvas.append(filename)

    token_sessao = request.form.get('token_sessao')
    if token_sessao:
        pasta_token = os.path.join(app.config['UPLOAD_FOLDER'], token_sessao)
        if os.path.exists(pasta_token):
            for file_name in os.listdir(pasta_token):
                if allowed_file(file_name):
                    ts = datetime.now().strftime("%H%M%S")
                    cli_prefix = session.get('cliente_id', 'anon')
                    novo_nome = secure_filename(f"cli{cli_prefix}_prod{produto_id}_{ts}_mobile_{file_name}")
                    
                    caminho_antigo = os.path.join(pasta_token, file_name)
                    caminho_novo = os.path.join(app.config['UPLOAD_FOLDER'], novo_nome)
                    
                    os.rename(caminho_antigo, caminho_novo)
                    fotos_salvas.append(novo_nome)
            try:
                os.rmdir(pasta_token)
            except Exception:
                pass

    multiplicador = session.get('multiplicador_regiao', 1.00)
    qtd_final_calculo = 1

    if str(produto_id).startswith('cat_') or str(produto_id).startswith('outro_cat_'):
        session['is_outros'] = str(produto_id).startswith('outro_cat_')
        categoria_id_str = str(produto_id).split('_')[-1]
        
        try:
            cat_id_int = int(categoria_id_str)
        except ValueError:
            cat_id_int = 4 # CORREÇÃO: Alterado fallback de 3 para 4
            
        if str(produto_id).startswith('cat_'):
            qtd_final_calculo = qtd_fisica
            
            if qtd_digital > 0:
                comentarios += f" [Mídia Digital informada: {qtd_digital} un]"
                
            try:
                est_id_int = int(estado_id) if estado_id else 0
            except ValueError:
                est_id_int = 0

            resultado_unitario = engine.calcular_cotacao_final(cat_id_int, est_id_int, multiplicador)
            
            if resultado_unitario and resultado_unitario.get('valor_final') is not None:
                 valor_lote = float(resultado_unitario['valor_final']) * qtd_final_calculo
                 resultado = {
                    "produto": f"Lote de Jogos ({qtd_final_calculo}x)",
                    "valor_final": valor_lote,
                    "multiplicador_aplicado": multiplicador
                 }
            else:
                resultado = {
                    "produto": f"Lote de Jogos ({qtd_final_calculo}x)",
                    "valor_final": 0.0,
                    "multiplicador_aplicado": multiplicador
                }
        else:
            resultado = {
                "produto": "Produto não listado",
                "valor_final": 0.0,
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

        resultado = engine.calcular_cotacao_final(prod_id_int, est_id_int, multiplicador)
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

        qtd_divisor = qtd_final_calculo if qtd_final_calculo > 0 else 1
        valor_unit_real = float(resultado['valor_final']) / qtd_divisor

        novo_item = {
            'produto_id': produto_id,
            'produto_nome': resultado['produto'],
            'valor_pix_unitario': valor_unit_real,
            'valor_cred_unitario': valor_unit_real * 1.2,
            'fotos_json': json.dumps(fotos_salvas), 
            'comentarios': comentarios,
            'quantidade': qtd_final_calculo,
            'estado_descricao': descricao_estado,
            'foto_url': foto_url_final,
            'is_outros': session.get('is_outros', False),
            'multiplicador_aplicado': resultado.get('multiplicador_aplicado', 1.00)
        }
        
        lista_atual = session.get('itens_avaliados', [])
        lista_atual.append(novo_item)
        session['itens_avaliados'] = lista_atual
        session['item_atual'] = novo_item 
        
        return render_template('resultado.html', cotacao=resultado, fase_atual=2)
    
    return "Erro ao calcular cotação.", 500

# 4ª TELA: NOVO RESUMO DO LOTE
@app.route('/resumo')
def resumo():
    itens = session.get('itens_avaliados', [])
    if not itens:
        return redirect(url_for('produto'))
    
    total_lote = sum(item['valor_pix_unitario'] * item.get('quantidade', 1) for item in itens)
    return render_template('resumo_lote.html', itens=itens, total_lote=total_lote, fase_atual=4)

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
    return render_template('termos_oferta.html', fase_atual=4)

@app.route('/aceitar_termos', methods=['POST'])
def aceitar_termos():
    # Ao confirmar aceite, o usuário é direcionado para a tela de Identificação
    return redirect(url_for('identificacao'))

@app.route('/descartar-lote-final', methods=['POST'])
def descartar_lote_final():
    dados = request.get_json()
    motivo = dados.get('motivo', '') if dados else ''
    
    itens = session.get('itens_avaliados', [])
    
    # Captura o IP real, respeitando arquitetura de Proxy/Docker (Ngrok)
    ip_origem = request.headers.get('X-Forwarded-For', request.remote_addr)
    # Se houver múltiplos IPs no X-Forwarded-For, pega o primeiro (origem real)
    if ip_origem and ',' in ip_origem:
        ip_origem = ip_origem.split(',')[0].strip()

    valor_oferta = sum(item['valor_pix_unitario'] * item.get('quantidade', 1) for item in itens) if itens else 0.0
    
    # Prepara o objeto de dados para o UPSERT no Banco
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
        # A chamada ao banco vai persistir a rejeição
        engine.salvar_feedback_recusa(dados_feedback)
    except Exception as e:
        print(f"Erro ao salvar feedback de recusa: {e}")
        
    # Limpa a sessão independentemente do sucesso do banco, garantindo o descarte
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
    
    return render_template('cadastro_complementar.html', fase_atual=5, cliente={})

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
        
    return "Erro na identification do lote.", 500

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
        
        dados_email = {
            'protocolo': res_protocolo['numero'],
            'quantidade_itens': len(itens),
            'total_pix': total_pix
        }
        
        engine.enviar_email_resumo(cliente, dados_email, itens)
        
        return render_template('sucesso.html', protocolo=res_protocolo['numero'], total_lote=total_pix, fase_atual=6)
    
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
    return render_template('upload_mobile.html', token=token)

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
    app.run(debug=True, port=5000)