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
# ==============================================================================

from flask import Flask, render_template, request, redirect, url_for, session, flash
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

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    porta = int(os.getenv("PORTA_FLASK", 5002))
    debug_mode = os.getenv("FLASK_DEBUG") == "1"
    app.run(debug=debug_mode, port=porta)