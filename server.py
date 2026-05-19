import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.utils import secure_filename
from datetime import datetime
import engine  # Motor de lógica e banco de dados
import json

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
    if 'itens_avaliados' not in session:
        session['itens_avaliados'] = []
    return render_template('busca.html', fase_atual=1)

@app.route('/busca')
def busca():
    if 'itens_avaliados' not in session:
        session['itens_avaliados'] = []
    return render_template('busca.html', fase_atual=1)

@app.route('/pericia/<int:produto_id>')
def pericia(produto_id):
    produto = engine.obter_produto_por_id(produto_id)
    
    tipo_produto = 'Console'
    if produto:
        nome = produto.get('nome_produto', '').upper()
        if any(x in nome for x in ['JOGO', 'CD', 'DVD', 'MIDIA']):
            tipo_produto = 'Jogo'
    
    opcoes = engine.buscar_opcoes_pericia(tipo_produto)
    session['produto_selecionado_id'] = produto_id
    
    return render_template('pericia.html', opcoes=opcoes, produto_id=produto_id, fase_atual=1)

# 3ª TELA: CÁLCULO E EXIBIÇÃO DA COTAÇÃO
@app.route('/cotar', methods=['POST'])
def cotar():
    produto_id = session.get('produto_selecionado_id')
    estado_id = request.form.get('estado_id')
    comentarios = request.form.get('comentarios', '')
    
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

    resultado = engine.calcular_cotacao_final(produto_id, estado_id)

    if resultado:
        produto_info = engine.obter_produto_por_id(produto_id)
        foto_url_final = produto_info.get('foto_oficial_url') if produto_info else None
        resultado['foto_url'] = foto_url_final

        tipo_produto = 'Console'
        if produto_info:
            nome = produto_info.get('nome_produto', '').upper()
            if any(x in nome for x in ['JOGO', 'CD', 'DVD', 'MIDIA']):
                tipo_produto = 'Jogo'
        
        opcoes = engine.buscar_opcoes_pericia(tipo_produto)
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
            'foto_url': foto_url_final
        }
        
        lista_atual = session.get('itens_avaliados', [])
        lista_atual.append(novo_item)
        session['itens_avaliados'] = lista_atual
        session['item_atual'] = novo_item 
        
        return render_template('resultado.html', cotacao=resultado, fase_atual=2)
    
    return "Erro ao calcular cotação.", 500

# 4ª TELA: NOVO RESUMO DO LOTE (Carrinho antes da identificação)
@app.route('/resumo')
def resumo():
    itens = session.get('itens_avaliados', [])
    if not itens:
        return redirect(url_for('busca'))
    
    total_lote = sum(item['valor_pix_unitario'] for item in itens)
    return render_template('resumo_lote.html', itens=itens, total_lote=total_lote, fase_atual=4)

# Rota de descarte total das avaliações do lote limpando a Session
@app.route('/descartar-lote')
def descartar_lote():
    session.pop('itens_avaliados', None)
    session.pop('item_atual', None)
    session.pop('produto_selecionado_id', None)
    return redirect(url_for('busca'))

# Rota assíncrona para ejetar apenas a última avaliação sem redirecionar a página
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
        return redirect(url_for('busca'))
    
    return render_template('cadastro_complementar.html', fase_atual=5, cliente={})

@app.route('/finalizar-lote', methods=['POST'])
def finalizar_lote():
    itens = session.get('itens_avaliados', [])
    if not itens:
        return redirect(url_for('busca'))
    
    # HIGIENIZAÇÃO DE STRINGS: Extrai apenas números puros eliminando qualquer tipo de máscara
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
        
    return "Erro na identificação do lote.", 500

# 6ª TELA: PROCESSAMENTO DE PROTOCOLO E FINALIZAÇÃO
@app.route('/finalizar', methods=['GET', 'POST'])
def finalizar():
    if 'cliente_id' not in session:
        return redirect(url_for('identificacao'))

    cliente_id = session.get('cliente_id')
    itens = session.get('itens_avaliados', [])

    if not itens:
        return redirect(url_for('busca'))

    cliente = engine.obter_cliente(cliente_id)
    
    total_pix = sum(item['valor_pix_unitario'] for item in itens)
    total_cred = sum(item['valor_cred_unitario'] for item in itens)

    dados_protocolo = {
        'cliente_id': cliente_id,
        'total_pix': total_pix,
        'total_cred': total_cred
    }

    res_protocolo = engine.finalizar_proposta(dados_protocolo)

    if res_protocolo:
        for item in itens:
            engine.registrar_item_periciado(res_protocolo['id'], item)
        
        dados_email = {
            'protocolo': res_protocolo['numero'],
            'quantidade_itens': len(itens),
            'total_pix': total_pix
        }
        
        # AJUSTE CRÍTICO: Passando a lista real de itens avaliados para detalhar no corpo do e-mail
        engine.enviar_email_resumo(cliente, dados_email, itens)
        
        # AJUSTE DE CORREÇÃO: Passando o valor total real do lote para exibição no HTML final
        return render_template('sucesso.html', protocolo=res_protocolo['numero'], total_lote=total_pix, fase_atual=6)
    
    return "Erro ao finalizar agendamento.", 500

# ROTA DE API: Consulta cliente via CPF (Foco estrito em dado puro numérico)
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
    termo = request.args.get('q', '')
    produtos = engine.buscar_produtos_catalogo(termo)
    return jsonify(produtos)

if __name__ == '__main__':
    app.run(debug=True, port=5000)