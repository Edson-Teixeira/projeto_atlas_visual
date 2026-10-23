from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import check_password_hash
from app.db import query_one

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Por favor, faça login para acessar esta página.", "warning")
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Por favor, faça login para acessar esta página.", "warning")
            return redirect(url_for('auth.login', next=request.url))
        user = get_current_user()
        if not user or not user['is_admin']:
            flash("Acesso restrito a administradores do sistema.", "danger")
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    if 'user_id' not in session:
        return None
    user = query_one("""
        SELECT u.id, u.nome, u.username, u.is_admin, u.contrato_id,
               c.codigo as contrato_codigo, c.nome_exibicao as contrato_nome,
               c.tabela_principal, c.tabela_secundaria, c.coluna_data
        FROM atlas_usuarios u
        LEFT JOIN atlas_contratos c ON u.contrato_id = c.id
        WHERE u.id = %s AND u.ativo = TRUE
    """, (session['user_id'],))
    return user

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash("Informe o usuário e a senha.", "danger")
            return render_template('login.html', username=username)

        user = query_one("""
            SELECT id, nome, username, password_hash, contrato_id, is_admin, ativo
            FROM atlas_usuarios
            WHERE username = %s
        """, (username,))

        if not user or not user['ativo']:
            flash("Usuário ou senha incorretos.", "danger")
            return render_template('login.html', username=username)

        if not check_password_hash(user['password_hash'], password):
            flash("Usuário ou senha incorretos.", "danger")
            return render_template('login.html', username=username)

        # Login com sucesso: define dados na sessão
        session.clear()
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['nome'] = user['nome']
        session['is_admin'] = user['is_admin']
        session['contrato_id'] = user['contrato_id']

        flash(f"Bem-vindo(a), {user['nome']}!", "success")
        next_url = request.args.get('next')
        return redirect(next_url or url_for('main.dashboard'))

    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("Sessão encerrada com sucesso.", "info")
    return redirect(url_for('auth.login'))
