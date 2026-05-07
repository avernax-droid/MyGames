from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import engine  # Importa o motor de lógica e banco de dados
import datetime

app = Flask(__name__)
app.secret_key = 'mygames_key_2026' # Chave para criptografia de sessão

# --- ROTAS DE NAVEGAÇÃO ---

@app.route('/')
def index():
    """
    Etapa 1: Identificação do Cliente.
    """
    return render_template('selecao.html', fase_atual=1)

@app.route('/selecionar', methods=['POST'])
def selecionar():
    """
    Processa o lead e redireciona para a busca.
    """
    dados_lead = {
        'nome_completo': request.form.get('nome_completo'),
        'email': request.form.get('email'),
        'whatsapp': request.form.get('whatsapp'),
        'cidade': request.form.get('cidade'),
        'estado_nome': request.form.get('estado_nome'), 
        'estado_uf': request.form.get('estado_uf'),     
        'origem_lead': request.form.get('origem_lead', 'Direto')
    }

    cliente_id = engine.salvar_lead(dados_lead)

    if cliente_id:
        session['cliente_id'] = cliente_id
        session['player_nome'] = dados_lead['nome_completo']
        session['player_email'] = dados_lead['email']
        return redirect(url_for('busca'))
    else:
        return "Erro ao processar identificação.", 500

@app.route('/busca')
def busca():
    """
    Etapa 2: Seleção do Produto.
    """
    if 'cliente_id' not in session:
        return redirect(url_for('index'))
    
    return render_template('busca.html', fase_atual=2)

# --- ETAPA 3: AVALIAÇÃO TÉCNICA (PERÍCIA) ---

@app.route('/pericia/<int:produto_id>')
def pericia(produto_id):
    """
    Etapa 3: Estado de Conservação.
    """
    if 'cliente_id' not in session:
        return redirect(url_for('index'))

    opcoes = engine.buscar_opcoes_pericia()
    session['produto_selecionado_id'] = produto_id
    
    return render_template('pericia.html', opcoes=opcoes, produto_id=produto_id, fase_atual=3)

@app.route('/cotar', methods=['POST'])
def cotar():
    """
    Etapa 4: Oferta Final.
    """
    if 'cliente_id' not in session or 'produto_selecionado_id' not in session:
        return redirect(url_for('index'))

    estado_id = request.form.get('estado_id')
    produto_id = session.get('produto_selecionado_id')

    session['estado_conservacao_id'] = estado_id

    resultado = engine.calcular_cotacao_final(produto_id, estado_id)

    if resultado:
        session['produto_nome'] = resultado['produto']
        session['valor_final'] = resultado['valor_final']
        return render_template('resultado.html', cotacao=resultado, fase_atual=4)
    else:
        return "Erro ao calcular cotação final.", 500

# --- ETAPA 5: FIREWALL DE CADASTRO E FINALIZAÇÃO ---

@app.route('/finalizar', methods=['POST'])
def finalizar():
    """
    Etapa 5: Validação rigorosa e fechamento automático com e-mail.
    """
    if 'cliente_id' not in session:
        return redirect(url_for('index'))

    cliente_id = session.get('cliente_id')

    if request.form.get('cadastro_completado') == '1':
        dados_cadastro = {
            'cpf': request.form.get('cpf'),
            'cep': request.form.get('cep'),
            'endereco': request.form.get('endereco'),
            'numero': request.form.get('numero'),
            'bairro': request.form.get('bairro'),
            'complemento': request.form.get('complemento'),
            'chave_pix': request.form.get('chave_pix')
        }
        engine.atualizar_cadastro_completo(cliente_id, dados_cadastro)
    
    cliente = engine.obter_cliente(cliente_id)
    campos_obrigatorios = ['cpf', 'cep', 'endereco', 'numero', 'bairro', 'chave_pix']
    
    if any(not cliente.get(campo) for campo in campos_obrigatorios):
        return render_template('cadastro_complementar.html', cliente=cliente, fase_atual=5)

    dados_finais = {
        'cliente_id': cliente_id,
        'produto_id': session.get('produto_selecionado_id'),
        'produto_nome': session.get('produto_nome'),
        'valor_final': session.get('valor_final'),
        'data_agendada': request.form.get('data_entrega'),
        'periodo': request.form.get('periodo_entrega')
    }

    protocolo = engine.finalizar_proposta(dados_finais)

    if protocolo:
        dados_finais['protocolo'] = protocolo
        # DISPARO DE E-MAIL PELO BACK-END (Agora Real via engine.py)
        engine.enviar_email_resumo(cliente, dados_finais)
        return render_template('sucesso.html', fase_atual=5)
    else:
        return "Erro ao finalizar o agendamento no sistema.", 500

# --- API E GESTÃO DE SESSÃO ---

@app.route('/novo_agendamento')
def novo_agendamento():
    """ Limpa dados do produto anterior para permitir nova avaliação do mesmo cliente """
    session.pop('produto_selecionado_id', None)
    session.pop('produto_nome', None)
    session.pop('valor_final', None)
    session.pop('estado_conservacao_id', None)
    session.pop('ultimo_protocolo', None)
    session.pop('data_entrega', None)
    session.pop('periodo_entrega', None)
    return redirect(url_for('busca'))

@app.route('/sair')
def sair():
    """ 
    PONTUAL: Limpa totalmente a sessão para forçar novo login/identificação.
    Resolve a falha onde o firewall era pulado por conta de sessão persistente.
    """
    session.clear()
    return redirect(url_for('index'))

@app.route('/api/buscar_produtos')
def api_buscar_produtos():
    termo = request.args.get('q', '')
    produtos = engine.buscar_produtos_catalogo(termo)
    return jsonify(produtos)

if __name__ == '__main__':
    app.run(debug=True, port=5000)