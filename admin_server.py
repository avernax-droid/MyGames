# ==============================================================================
# PROJETO: MyGames - Backoffice
# MÓDULO: admin_server.py
# DATA DE CRIAÇÃO: 30/05/2026
# TÍTULO: Servidor Web e Roteamento Flask
# FUNÇÃO: Servidor Controller principal do painel administrativo.
# Gerencia a autenticação via identidade do usuário, sessão e permissões RBAC.
#
# HISTÓRICO DE ALTERAÇÕES:
# - 30/05/2026: Criação do servidor controller inicial e rotas de autenticação.
# - 30/05/2026: Implementação de Controle de Acesso Baseado em Funções (RBAC).
# - 01/06/2026: Adição de rotas para gestão (CRUD) de Regiões de Atendimento e Catálogo.
# - 01/06/2026: Inserção da rota de detalhes de Protocolos (/protocolos/<id>).
# - 04/06/2026: Adição de rota proxy (/api/buscar_cidades) para consulta na API do IBGE.
# - 04/06/2026: Ajuste na rota /regioes/salvar para suportar requisições AJAX com retorno JSON.
# - 04/06/2026: Adição da rota /catalogo/salvar com upload seguro físico de fotos_oficiais (Werkzeug).
# - 04/06/2026: Adição da rota interna /api/buscar_produtos_nome para auto-completar de produtos.
# - 10/06/2026: Atualização da query de listagem de protocolos para suportar LEFT JOIN de status.
# - 10/06/2026: Injeção da lista dinâmica de status na rota de detalhes do protocolo.
# - 10/06/2026: Criação da rota POST /protocolos/atualizar_status/<id> para a esteira de gestão.
# - 10/06/2026: Criação da rota GET /esteira para exibir a Fila de Trabalho por gavetas.
# - 10/06/2026: Criação da rota GET /esteira/periciar/<id> para o Cockpit de Ação.
# - 10/06/2026: Criação da rota POST /esteira/salvar_pericia/<id> com redirecionamento de fluxo.
# - 11/06/2026: Atualização da rota POST /esteira/salvar_pericia/<id> para capturar o campo valor_avaliado.
# - 11/06/2026: Ajuste no app.run para host='0.0.0.0' visando suporte externo (Docker/Cloudflare).
# - 11/06/2026: Inserção de laço de conversão JSON -> Lista para fotos na rota /esteira/periciar.
# - 11/06/2026: Refatoração da rota /esteira/salvar_pericia/<id> para suportar requisições AJAX (UX silenciosa).
# - 11/06/2026: Refatoração da rota /protocolos para uso da função admin_engine.obter_todos_protocolos_listagem.
# ==============================================================================

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, jsonify
import mysql.connector
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
import os
import json
from functools import wraps
import requests
from dotenv import load_dotenv
import admin_engine

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# Diretório para upload das imagens do catálogo
DIRETORIO_CATALOGO = os.path.join(app.root_path, 'static', 'images', 'catalogo')
os.makedirs(DIRETORIO_CATALOGO, exist_ok=True)

# --- MATRIZ DE PERMISSÕES (RBAC) ---
PERMISSOES = {
    'Administrador': {
        'protocolos': ['read', 'update', 'delete', 'create'],
        'catalogo': ['read', 'update', 'delete', 'create'],
        'regioes': ['read', 'update', 'delete', 'create']
    },
    'Operador': {
        'protocolos': ['read', 'update'],
        'catalogo': ['read'],
        'regioes': []
    }
}

def conectar_bd():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        database=os.getenv("DB_NAME")
    )

def requer_permissao(modulo, acao='read'):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'admin_id' not in session: return redirect(url_for('login'))
            nivel = session.get('admin_nivel')
            permissoes_nivel = PERMISSOES.get(nivel, {})
            permissoes_modulo = permissoes_nivel.get(modulo, [])
            if acao not in permissoes_modulo:
                flash('Acesso negado.', 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- ROTAS CORE ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if 'admin_id' in session: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        usuario_login = request.form.get('usuario_login')
        senha = request.form.get('senha')
        db = conectar_bd()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios_admin WHERE usuario_login = %s AND ativo = 1", (usuario_login,))
        usuario = cursor.fetchone()
        db.close()
        if usuario and check_password_hash(usuario['senha_hash'], senha):
            session['admin_id'] = usuario['id']
            session['admin_nome'] = usuario['nome_completo']
            session['admin_nivel'] = usuario['nivel_acesso']
            return redirect(url_for('dashboard'))
        flash('Dados incorretos.', 'error')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'admin_id' not in session: return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/protocolos')
@requer_permissao('protocolos', 'read')
def listar_protocolos():
    lista_protocolos = admin_engine.obter_todos_protocolos_listagem()
    return render_template('protocolos.html', protocolos=lista_protocolos)

# --- ROTA: FILA DE TRABALHO (ESTEIRA) ---
@app.route('/esteira')
@app.route('/esteira/<int:status_id>')
@requer_permissao('protocolos', 'read')
def esteira_protocolos(status_id=None):
    resumo_status = admin_engine.obter_resumo_esteira()
    
    protocolos_filtrados = []
    if status_id:
        protocolos_filtrados = admin_engine.obter_protocolos_por_status(status_id)
        
    return render_template('esteira.html', 
                           resumo_status=resumo_status, 
                           protocolos=protocolos_filtrados, 
                           status_selecionado=status_id)

# --- ROTA: TELA DE PERÍCIA FOCADA (COCKPIT) ---
@app.route('/esteira/periciar/<int:protocolo_id>')
@requer_permissao('protocolos', 'update')
def periciar_na_esteira(protocolo_id):
    dados_protocolo = admin_engine.obter_cabecalho_protocolo(protocolo_id)
    if not dados_protocolo:
        flash('Protocolo não encontrado.', 'error')
        return redirect(url_for('esteira_protocolos'))
    
    itens_protocolo = admin_engine.obter_itens_protocolo(protocolo_id)
    
    for item in itens_protocolo:
        item['fotos'] = []
        if item.get('fotos_json'):
            try:
                fotos_lista = json.loads(item['fotos_json'])
                if isinstance(fotos_lista, list):
                    item['fotos'] = fotos_lista
            except json.JSONDecodeError:
                pass
                
    lista_status = admin_engine.buscar_status_ativos()
    
    return render_template('pericia_esteira.html', 
                           protocolo=dados_protocolo, 
                           itens=itens_protocolo, 
                           lista_status=lista_status)

# --- ROTA: SALVAR DECISÃO (COM SUPORTE AJAX) ---
@app.route('/esteira/salvar_pericia/<int:protocolo_id>', methods=['POST'])
@requer_permissao('protocolos', 'update')
def salvar_pericia_esteira(protocolo_id):
    status_id = request.form.get('status_id')
    laudo_tecnico = request.form.get('laudo_tecnico')
    valor_avaliado = request.form.get('valor_avaliado')

    is_ajax = request.headers.get('Accept') == 'application/json'

    if not status_id or not valor_avaliado:
        if is_ajax:
            return jsonify({'sucesso': False, 'mensagem': 'Status e Valor Avaliado são obrigatórios.'})
        flash('Status e Valor Avaliado são obrigatórios.', 'error')
        return redirect(url_for('periciar_na_esteira', protocolo_id=protocolo_id))

    sucesso = admin_engine.atualizar_status_protocolo(protocolo_id, status_id, laudo_tecnico, valor_avaliado)

    if is_ajax:
        return jsonify({'sucesso': sucesso})

    if not sucesso:
        flash('Erro interno ao salvar a perícia.', 'error')
        
    return redirect(url_for('periciar_na_esteira', protocolo_id=protocolo_id))

@app.route('/protocolos/<int:protocolo_id>')
@requer_permissao('protocolos', 'read')
def detalhes_protocolo(protocolo_id):
    dados_protocolo = admin_engine.obter_cabecalho_protocolo(protocolo_id)
    if not dados_protocolo:
        flash('Protocolo não encontrado.', 'error')
        return redirect(url_for('listar_protocolos'))
    
    itens_protocolo = admin_engine.obter_itens_protocolo(protocolo_id)
    diretorio_uploads = os.getenv("DIRETORIO_UPLOADS_PERICIA", "")
    
    for item in itens_protocolo:
        item['fotos_validadas'] = []
        if item.get('fotos_json'):
            try:
                fotos = json.loads(item['fotos_json'])
                if isinstance(fotos, list):
                    for foto_nome in fotos:
                        caminho_fisico = os.path.join(diretorio_uploads, foto_nome)
                        existe = os.path.exists(caminho_fisico) if diretorio_uploads else False
                        
                        item['fotos_validadas'].append({
                            'nome': foto_nome,
                            'existe_no_disco': existe,
                            'url_estatica': f"/uploads/pericia/{foto_nome}"
                        })
            except json.JSONDecodeError:
                pass
                
    lista_status = admin_engine.buscar_status_ativos()
    return render_template('detalhes_protocolo.html', protocolo=dados_protocolo, itens=itens_protocolo, lista_status=lista_status)

@app.route('/protocolos/atualizar_status/<int:protocolo_id>', methods=['POST'])
@requer_permissao('protocolos', 'update')
def atualizar_status_protocolo(protocolo_id):
    status_id = request.form.get('status_id')
    laudo_tecnico = request.form.get('laudo_tecnico')

    if not status_id:
        flash('Status inválido. Selecione uma etapa válida da esteira.', 'error')
        return redirect(url_for('detalhes_protocolo', protocolo_id=protocolo_id))

    sucesso = admin_engine.atualizar_status_protocolo(protocolo_id, status_id, laudo_tecnico)

    if sucesso:
        flash('Status do protocolo atualizado com sucesso!', 'success')
    else:
        flash('Erro interno ao atualizar o status do protocolo.', 'error')

    return redirect(url_for('detalhes_protocolo', protocolo_id=protocolo_id))

@app.route('/catalogo')
@requer_permissao('catalogo', 'read')
def listar_catalogo():
    produtos = admin_engine.obter_catalogo_completo()
    categorias = admin_engine.obter_categorias()
    return render_template('catalogo.html', produtos=produtos, categorias=categorias)

@app.route('/api/buscar_produtos_nome')
@requer_permissao('catalogo', 'read')
def api_buscar_produtos_nome():
    termo = request.args.get('q', '')
    if not termo or len(termo) < 2:
        return jsonify([])
    produtos = admin_engine.buscar_produtos_por_nome(termo)
    return jsonify(produtos)

@app.route('/catalogo/salvar', methods=['POST'])
@requer_permissao('catalogo', 'update')
def salvar_catalogo():
    produto_id = request.form.get('id')
    nome = request.form.get('nome_produto')
    categoria = request.form.get('categoria_id')
    plataforma = request.form.get('plataforma')
    valor_venda = request.form.get('valor_venda_ref')
    valor_pix = request.form.get('valor_pix_base')
    valor_cred = request.form.get('valor_cred_base')
    ativo = request.form.get('ativo')
    
    produto_id = int(produto_id) if produto_id and produto_id.isdigit() else None
    
    try:
        v_venda = float(valor_venda) if valor_venda else 0.0
        v_pix = float(valor_pix) if valor_pix else 0.0
        v_cred = float(valor_cred) if valor_cred else 0.0
    except ValueError:
        v_venda, v_pix, v_cred = 0.0, 0.0, 0.0

    foto_url_banco = None
    if 'foto_oficial' in request.files:
        arquivo = request.files['foto_oficial']
        if arquivo and arquivo.filename != '':
            nome_seguro = secure_filename(arquivo.filename)
            caminho_salvamento = os.path.join(DIRETORIO_CATALOGO, nome_seguro)
            arquivo.save(caminho_salvamento)
            foto_url_banco = f"/static/images/catalogo/{nome_seguro}"

    sucesso = admin_engine.salvar_produto_catalogo(
        produto_id, nome, categoria, plataforma, v_venda, v_pix, v_cred, int(ativo), foto_url_banco
    )
    
    if request.headers.get('Accept') == 'application/json':
        return jsonify({
            'sucesso': sucesso,
            'mensagem': 'Produto salvo com sucesso!' if sucesso else 'Erro ao salvar o produto.'
        })

    flash('Produto salvo com sucesso!' if sucesso else 'Erro ao salvar produto.', 'success' if sucesso else 'error')
    return redirect(url_for('listar_catalogo'))

@app.route('/regioes')
@requer_permissao('regioes', 'read')
def listar_regioes():
    lista_regioes = admin_engine.obter_todas_regioes()
    return render_template('regioes.html', regioes=lista_regioes)

@app.route('/regioes/salvar', methods=['POST'])
@requer_permissao('regioes', 'update')
def salvar_regiao():
    regiao_id = request.form.get('id')
    cidade = request.form.get('cidade')
    estado_uf = request.form.get('estado_uf')
    multiplicador_preco = request.form.get('multiplicador_preco')
    ativo = request.form.get('ativo')
    regiao_id = int(regiao_id) if regiao_id and regiao_id.isdigit() else None
    
    sucesso = admin_engine.salvar_regiao(regiao_id, cidade, estado_uf, float(multiplicador_preco), int(ativo))
    
    if request.headers.get('Accept') == 'application/json':
        return jsonify({
            'sucesso': sucesso, 
            'mensagem': 'Região salva com sucesso!' if sucesso else 'Erro ao salvar a região no banco de dados.'
        })

    flash('Região salva com sucesso!' if sucesso else 'Erro ao salvar.', 'success' if sucesso else 'error')
    return redirect(url_for('listar_regioes'))

@app.route('/api/buscar_cidades')
@requer_permissao('regioes', 'read')
def api_buscar_cidades():
    termo = request.args.get('q', '')
    if not termo or len(termo) < 3:
        return jsonify([])

    try:
        req = requests.get("https://servicodados.ibge.gov.br/api/v1/localidades/municipios", timeout=5)
        if req.status_code != 200:
             return jsonify([])
        dados = req.json()
    except: 
        return jsonify([])
        
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

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/uploads/pericia/<path:filename>')
def servir_midia_externa(filename):
    diretorio_fotos = os.getenv("DIRETORIO_UPLOADS_PERICIA")
    return send_from_directory(diretorio_fotos, filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=(os.getenv("FLASK_DEBUG") == "1"), port=int(os.getenv("PORTA_FLASK", 5002)))