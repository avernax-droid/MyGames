# ==============================================================================
# PROJETO: MyGames - Backoffice
# MÓDULO: admin_server.py
# DATA DE CRIAÇÃO: 30/05/2026
# FUNÇÃO: Servidor Controller principal do painel administrativo.
# Gerencia a autenticação via identidade do usuário, sessão e permissões RBAC.
#
# HISTÓRICO DE ALTERAÇÕES:
# - 30/05/2026: Criação do servidor controller inicial e rotas de autenticação.
# - 30/05/2026: Implementação de Controle de Acesso Baseado em Funções (RBAC).
# - 30/05/2026: Criação da rota /protocolos com JOIN entre tabelas.
# - 01/06/2026: Criação de rota para servir arquivos de mídia externos.
# - 01/06/2026: Adição de rotas para gestão (CRUD) do Catálogo Mestre.
# - 01/06/2026: Adição de rotas para gestão (CRUD) de Regiões de Atendimento.
# - 01/06/2026: Refatoração do roteamento via url_for para correção de BuildErrors.
# - 01/06/2026: Restauração da integridade das rotas de Protocolos e Catálogo.
# - 01/06/2026: Correção da query de Protocolos (inclusão de valor_total_pix).
# - 01/06/2026: Inserção da rota de detalhes de Protocolos (/protocolos/<id>).
# - 01/06/2026: Inclusão do campo whatsapp como telefone na query da rota /protocolos.
# - 01/06/2026: Restauração da rota de mídia e lógica de parsing do json de fotos (fotos_validadas).
# ==============================================================================

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import mysql.connector
from werkzeug.security import check_password_hash
import os
import json
from functools import wraps
from dotenv import load_dotenv
import admin_engine

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

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
    db = conectar_bd()
    cursor = db.cursor(dictionary=True)
    query = """
        SELECT p.id, p.numero_protocolo, p.status, p.valor_total_pix, p.data_criacao,
               c.nome_completo as cliente_nome, c.whatsapp as cliente_telefone
        FROM protocolos_recompra p 
        JOIN clientes_usuarios c ON p.cliente_id = c.id 
        ORDER BY p.data_criacao DESC
    """
    cursor.execute(query)
    lista_protocolos = cursor.fetchall()
    db.close()
    return render_template('protocolos.html', protocolos=lista_protocolos)

@app.route('/protocolos/<int:protocolo_id>')
@requer_permissao('protocolos', 'read')
def detalhes_protocolo(protocolo_id):
    dados_protocolo = admin_engine.obter_cabecalho_protocolo(protocolo_id)
    if not dados_protocolo:
        flash('Protocolo não encontrado.', 'error')
        return redirect(url_for('listar_protocolos'))
    
    itens_protocolo = admin_engine.obter_itens_protocolo(protocolo_id)
    
    # --- RECONSTRUÇÃO DA LÓGICA DE TRATAMENTO DE FOTOS ---
    diretorio_uploads = os.getenv("DIRETORIO_UPLOADS_PERICIA", "")
    
    for item in itens_protocolo:
        item['fotos_validadas'] = []
        if item.get('fotos_json'):
            try:
                fotos = json.loads(item['fotos_json'])
                if isinstance(fotos, list):
                    for foto_nome in fotos:
                        # Verifica se o arquivo existe fisicamente
                        caminho_fisico = os.path.join(diretorio_uploads, foto_nome)
                        existe = os.path.exists(caminho_fisico) if diretorio_uploads else False
                        
                        item['fotos_validadas'].append({
                            'nome': foto_nome,
                            'existe_no_disco': existe,
                            'url_estatica': f"/uploads/pericia/{foto_nome}"
                        })
            except json.JSONDecodeError:
                pass # Ignora caso o JSON esteja malformado no banco
                
    return render_template('detalhes_protocolo.html', protocolo=dados_protocolo, itens=itens_protocolo)

@app.route('/catalogo')
@requer_permissao('catalogo', 'read')
def listar_catalogo():
    produtos = admin_engine.obter_catalogo_completo()
    categorias = admin_engine.obter_categorias()
    return render_template('catalogo.html', produtos=produtos, categorias=categorias)

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
    flash('Região salva com sucesso!' if sucesso else 'Erro ao salvar.', 'success' if sucesso else 'error')
    return redirect(url_for('listar_regioes'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- ROTA DE MÍDIA EXTERNA RESTAURADA ---
@app.route('/uploads/pericia/<path:filename>')
def servir_midia_externa(filename):
    diretorio_fotos = os.getenv("DIRETORIO_UPLOADS_PERICIA")
    return send_from_directory(diretorio_fotos, filename)

if __name__ == '__main__':
    app.run(debug=(os.getenv("FLASK_DEBUG") == "1"), port=int(os.getenv("PORTA_FLASK", 5002)))