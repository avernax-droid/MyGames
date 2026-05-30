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
# ==============================================================================

import os
import json
import uuid
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
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
UPLOAD_FOLDER = 'static/uploads/pericia'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- ROTAS DE NAVEGAÇÃO ---

@app.route('/')
def index():
    session.clear()
    # NOVO: Busca os canais no banco
    canais_do_banco = engine.buscar_canais_aquisicao() 
    # ALTERADO: Envia a lista 'canais' para o HTML renderizar os botões
    return render_template('boas_vindas.html', canais=canais_do_banco)

@app.route('/definir_regiao', methods=['POST'])
def definir_regiao():
    cidade = request.form.get('cidade')
    estado_uf = request.form.get('estado_uf')
    
    session['cidade_usuario'] = cidade
    session['uf_usuario'] = estado_uf
    # NOVO: Captura o canal escolhido no HTML e guarda na sessão para gravar depois
    session['canal_aquisicao_id'] = request.form.get('canal_aquisicao_id') 
    
    # NOVO: Busca e salva o multiplicador de preço da região na sessão
    session['multiplicador_regiao'] = engine.obter_multiplicador_regiao(cidade, estado_uf)
    
    return redirect(url_for('produto'))

@app.route('/produto')
def produto():
    if 'itens_avaliados' not in session:
        session['itens_avaliados'] = []
    return render_template('produto.html', fase_atual=1)

@app.route('/pericia/<produto_id>')
def pericia(produto_id):
    # Intercepta os IDs especiais criados no passo anterior (Jogos e Outros)
    if str(produto_id).startswith('cat_') or str(produto_id).startswith('outro_cat_'):
        categoria_id = str(produto_id).split('_')[-1]
        id_oficial = produto_id
        
        # FOCO DA ALTERAÇÃO: Define a flag com base no prefixo 'outro_cat_'
        session['is_outros'] = str(produto_id).startswith('outro_cat_')
    else:
        # FOCO DA ALTERAÇÃO: Garante que se for um produto normal, a flag permaneça falsa
        session['is_outros'] = False
        produto = engine.obter_produto_por_id(produto_id)
        if not produto:
            return redirect(url_for('produto'))
        categoria_id = produto.get('categoria_id')
        id_oficial = produto['id']
    
    opcoes = engine.buscar_opcoes_pericia(categoria_id)
    
    session['produto_selecionado_id'] = id_oficial
    
    # Geração do token de handoff único para esta sessão de upload remoto
    token_sessao = str(uuid.uuid4())
    
    return render_template('pericia.html', opcoes=opcoes, produto_id=id_oficial, fase_atual=1, categoria_id=categoria_id, token_sessao=token_sessao)

# 3ª TELA: CÁLCULO E EXIBIÇÃO DA COTAÇÃO
@app.route('/cotar', methods=['POST'])
def cotar():
    produto_id = session.get('produto_selecionado_id')
    estado_id = request.form.get('estado_id')
    comentarios = request.form.get('comentarios', '')
    
    fotos_salvas = []
    
    # 1. Processa fotos enviadas diretamente via upload local do Desktop
    if 'fotos' in request.files:
        files = request.files.getlist('fotos')
        for file in files:
            if file and allowed_file(file.filename):
                ts = datetime.now().strftime("%H%M%S")
                cli_prefix = session.get('cliente_id', 'anon')
                filename = secure_filename(f"cli{cli_prefix}_prod{produto_id}_{ts}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                fotos_salvas.append(filename)

    # 2. Processa fotos recebidas de forma remota via celular (Mobile Handoff)
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
            
            # Remove o diretório temporário do token após mover os arquivos
            try:
                os.rmdir(pasta_token)
            except Exception:
                pass

    # Lida com o cálculo dependendo se é um produto real ou genérico
    if str(produto_id).startswith('cat_') or str(produto_id).startswith('outro_cat_'):
        # FOCO DA ALTERAÇÃO: Mantém ou atualiza a flag de controle da sessão ativa
        session['is_outros'] = str(produto_id).startswith('outro_cat_')
        resultado = {
            "produto": "Lote de Jogos" if str(produto_id).startswith('cat_') else "Produto não listado",
            "valor_final": 0.0,
            "multiplicador_aplicado": 1.00
        }
        categoria_id = str(produto_id).split('_')[-1]
        foto_url_final = None
    else:
        # FOCO DA ALTERAÇÃO: Força falso se for um fluxo padrão de produto catalogado
        session['is_outros'] = False
        
        # NOVO: Resgata o multiplicador da sessão (fallback 1.00)
        multiplicador = session.get('multiplicador_regiao', 1.00)
        resultado = engine.calcular_cotacao_final(produto_id, estado_id, multiplicador)
        
        produto_info = engine.obter_produto_por_id(produto_id)
        categoria_id = produto_info.get('categoria_id') if produto_info else 1
        foto_url_final = produto_info.get('foto_oficial_url') if produto_info else None

    if resultado:
        resultado['foto_url'] = foto_url_final
        
        opcoes = engine.buscar_opcoes_pericia(categoria_id)
        descricao_estado = "Estado Selecionado"
        if opcoes:
            for op in opcoes:
                if str(op.get('id')) == str(estado_id):
                    descricao_estado = op.get('descricao')
                    break
        
        resultado['descricao'] = descricao_estado

        novo_item = {
            'produto_id': produto_id,
            'produto_nome': resultado['produto'],
            'valor_pix_unitario': resultado['valor_final'],
            'valor_cred_unitario': resultado['valor_final'] * 1.2,
            'fotos_json': json.dumps(fotos_salvas), 
            'comentarios': comentarios,
            'quantidade': 1,
            'estado_descricao': descricao_estado,
            'foto_url': foto_url_final,
            # FOCO DA ALTERAÇÃO: Registra no próprio dicionário do item se ele veio do fluxo de "Outros"
            'is_outros': session.get('is_outros', False),
            # NOVO: Grava o multiplicador no item
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
    
    total_lote = sum(item['valor_pix_unitario'] for item in itens)
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
    
    total_pix = sum(item['valor_pix_unitario'] for item in itens)
    total_cred = sum(item['valor_cred_unitario'] for item in itens)

    dados_protocolo = {
        'cliente_id': cliente_id,
        'total_pix': total_pix,
        'total_cred': total_cred,
        # NOVO: Injeta o ID resgatado da sessão no dicionário
        'canal_aquisicao_id': session.get('canal_aquisicao_id') 
    }

    res_protocolo = engine.finalizar_proposta(dados_protocolo)

    if res_protocolo:
        for item in itens:
            # CORREÇÃO: Garante que o ID seja numérico para o banco de dados
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
    # Rota acessada pelo celular via QR Code (Gera uma página de upload minimalista)
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
    
    # Se o diretório com o token existe, verifica se há mídias salvas nele
    if os.path.exists(pasta_token):
        fotos = [f for f in os.listdir(pasta_token) if allowed_file(f)]
        if len(fotos) > 0:
            caminhos = [f"/static/uploads/pericia/{token}/{foto}" for foto in fotos]
            return jsonify({'status': 'concluido', 'fotos': caminhos}), 200
            
    return jsonify({'status': 'aguardando'}), 200


if __name__ == '__main__':
    app.run(debug=True, port=5000)