# ==============================================================================
# PROJETO: MyGames - Backoffice
# MÓDULO: admin_server.py
# DATA DE CRIAÇÃO: 30/05/2026
# FUNÇÃO: Servidor Controller principal do painel administrativo.
# Gerencia a autenticação via identidade do usuário, sessão e permissões RBAC.
#
# HISTÓRICO DE ALTERAÇÕES:
# - 30/05/2026: Criação do servidor controller inicial e rotas de autenticação.
# - 30/05/2026: Substituição do HTML de texto provisório pela renderização do dashboard.
# - 30/05/2026: Implementação de Controle de Acesso Baseado em Funções (RBAC) e Decorator.
# - 30/05/2026: Migração da autenticação de E-mail para Identidade do Usuário (usuario_login).
# - 30/05/2026: Criação da rota /protocolos com JOIN entre tabelas.
# - 30/05/2026: Adição da rota protegida para visualização detalhada de um protocolo específico.
# - 01/06/2026: Criação de rota para servir arquivos de mídia externos (volume compartilhado).
# - 01/06/2026: Adição das rotas controller para a visualização e salvamento (UPSERT) do Catálogo Mestre.
# - 01/06/2026: Correção e expansão da rota /catalogo/salvar para receber e converter os novos campos: 
#               plataforma, valor_venda_ref e valor_cred_base vindos do formulário do Modal.
# ==============================================================================

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import mysql.connector
from werkzeug.security import check_password_hash
import os
from functools import wraps
from dotenv import load_dotenv

# Importa o motor de dados do backoffice que processará as regras de negócio
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

# --- DECORATOR GUARDIÃO ---
def requer_permissao(modulo, acao='read'):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'admin_id' not in session:
                return redirect(url_for('login'))
            
            nivel = session.get('admin_nivel')
            permissoes_nivel = PERMISSOES.get(nivel, {})
            permissoes_modulo = permissoes_nivel.get(modulo, [])
            
            if acao not in permissoes_modulo:
                flash('Acesso negado: Você não tem permissão para realizar esta ação.', 'error')
                return redirect(url_for('dashboard'))
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- ROTAS CORE ---

@app.route('/', methods=['GET', 'POST'])
def login():
    if 'admin_id' in session:
        return redirect(url_for('dashboard'))

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
        else:
            flash('Identidade ou senha incorretos, ou usuário inativo.', 'error')

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/protocolos')
@requer_permissao('protocolos', 'read')
def listar_protocolos():
    db = conectar_bd()
    cursor = db.cursor(dictionary=True)
    
    query = """
        SELECT p.id, p.numero_protocolo, p.status, p.valor_total_pix, p.data_criacao,
               c.nome_completo as cliente_nome
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
    # 1. Busca os dados gerais do protocolo (Pai) e do cliente através do motor
    dados_protocolo = admin_engine.obter_cabecalho_protocolo(protocolo_id)
    
    # Se o protocolo não existir no banco, joga de volta para a listagem com erro
    if not dados_protocolo:
        flash('Protocolo não encontrado.', 'error')
        return redirect(url_for('listar_protocolos'))
    
    # 2. Busca a lista de itens pertencentes a este protocolo (Filhos)
    itens_protocolo = admin_engine.obter_itens_protocolo(protocolo_id)
    
    # Renderiza a tela de detalhes passando os dicionários estruturados
    return render_template('detalhes_protocolo.html', 
                           protocolo=dados_protocolo, 
                           itens=itens_protocolo)

# --- ROTA DE ARQUIVOS COMPARTILHADOS ---
@app.route('/media/pericia/<nome_arquivo>')
def media_pericia(nome_arquivo):
    # Lê a pasta física configurada no .env
    pasta_uploads = os.getenv("DIRETORIO_UPLOADS_PERICIA")
    
    if not pasta_uploads:
        return "Caminho de uploads não configurado no .env", 500
        
    # O Flask busca e entrega o arquivo com segurança
    return send_from_directory(pasta_uploads, nome_arquivo)

# ==============================================================================
# ROTAS DE CONTROLE: GESTÃO DO CATÁLOGO MESTRE
# ==============================================================================

@app.route('/catalogo')
@requer_permissao('catalogo', 'read')
def listar_catalogo():
    # Busca a lista completa de produtos cadastrados através do motor de dados
    produtos_catalogo = admin_engine.obter_catalogo_completo()
    # Busca a lista estruturada de categorias para popular o <select> do modal
    categorias_lista = admin_engine.obter_categorias()
    
    return render_template('catalogo.html', produtos=produtos_catalogo, categories=categorias_lista)

@app.route('/catalogo/salvar', methods=['POST'])
@requer_permissao('catalogo', 'update')
def salvar_catalogo():
    # Coleta os inputs vindos do formulário interno do Modal
    produto_id = request.form.get('produto_id')
    nome_produto = request.form.get('nome_produto')
    categoria_id = request.form.get('categoria_id')
    plataforma = request.form.get('plataforma')
    valor_venda_ref = request.form.get('valor_venda_ref')
    valor_pix_base = request.form.get('valor_pix_base')
    valor_cred_base = request.form.get('valor_cred_base')
    ativo = request.form.get('ativo')
    
    # Garante a tipagem correta e alinhada com as colunas do banco de dados
    produto_id = int(produto_id) if produto_id and produto_id.isdigit() else None
    categoria_id = int(categoria_id) if categoria_id else None
    
    # Permite conversões seguras suportando valores vazios (NULL no banco)
    valor_venda_ref = float(valor_venda_ref) if valor_venda_ref else None
    valor_pix_base = float(valor_pix_base) if valor_pix_base else None
    valor_cred_base = float(valor_cred_base) if valor_cred_base else None
    ativo = int(ativo)

    # Invoca a persistência via motor de dados do backoffice contendo toda a nova assinatura
    sucesso = admin_engine.salvar_produto_catalogo(
        produto_id, nome_produto, categoria_id, plataforma,
        valor_venda_ref, valor_pix_base, valor_cred_base, ativo
    )
    
    if sucesso:
        flash('Alterações do catálogo salvas com sucesso!', 'success')
    else:
        flash('Ocorreu um erro ao tentar persistir os dados do produto.', 'error')
        
    return redirect(url_for('listar_catalogo'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    porta = int(os.getenv("PORTA_FLASK", 5002))
    debug_mode = os.getenv("FLASK_DEBUG") == "1"
    app.run(debug=debug_mode, port=porta)