import io
import csv
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, Response
from werkzeug.security import generate_password_hash
from app.auth import login_required, admin_required, get_current_user
from app.db import get_db, query_one, query_all
from app.importer import process_and_import

main_bp = Blueprint('main', __name__)

def count_table_rows(table_name):
    """Conta registros de forma segura checando a existência da tabela."""
    if not table_name:
        return 0
    try:
        exists = query_one("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = %s
            ) as exists
        """, (table_name,))
        if exists and exists['exists']:
            row = query_one(f'SELECT COUNT(*) as c FROM "{table_name}"')
            return row['c'] if row else 0
        return 0
    except Exception:
        return 0

@main_bp.route('/')
@login_required
def index():
    return redirect(url_for('main.dashboard'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.logout'))

    # Se for Administrador, abre DIRETAMENTE o Dashboard Executivo do Admin
    if user['is_admin']:
        return render_admin_dashboard(user)

    # Se for Operador de Contrato:
    contrato_id = user['contrato_id']
    if not contrato_id:
        flash("Nenhum contrato vinculado a este usuário.", "warning")
        return render_template('dashboard.html', user=user, contrato=None)

    return render_operator_dashboard(user, contrato_id)

def render_admin_dashboard(user):
    """Renderiza a tela de status de cada contrato e histórico global para o Administrador."""
    todos_contratos = query_all("""
        SELECT id, codigo, nome_exibicao, tabela_principal, tabela_secundaria, tabela_terciaria 
        FROM atlas_contratos 
        WHERE ativo = TRUE 
        ORDER BY nome_exibicao
    """)
    
    contratos_status = []
    total_enviados_hoje = 0
    total_pendentes_hoje = 0

    for c in todos_contratos:
        # Carga realizada hoje?
        info_hoje = query_one("""
            SELECT l.id, l.criado_em, l.total_linhas, u.nome as user_nome
            FROM atlas_importacoes_log l
            LEFT JOIN atlas_usuarios u ON l.usuario_id = u.id
            WHERE l.contrato_id = %s AND DATE(l.criado_em) = CURRENT_DATE AND l.status = 'sucesso'
            ORDER BY l.criado_em DESC
            LIMIT 1
        """, (c['id'],))

        # Última carga em qualquer data
        ultima_carga = query_one("""
            SELECT l.id, l.criado_em, l.total_linhas, l.status, u.nome as user_nome
            FROM atlas_importacoes_log l
            LEFT JOIN atlas_usuarios u ON l.usuario_id = u.id
            WHERE l.contrato_id = %s
            ORDER BY l.criado_em DESC
            LIMIT 1
        """, (c['id'],))

        # Total acumulado somando principal, secundária e terciária
        total_acumulado = count_table_rows(c['tabela_principal'])
        if c.get('tabela_secundaria'):
            total_acumulado += count_table_rows(c['tabela_secundaria'])
        if c.get('tabela_terciaria'):
            total_acumulado += count_table_rows(c['tabela_terciaria'])

        # Total de operadores vinculados a esse contrato
        users_count = query_one("SELECT COUNT(*) as c FROM atlas_usuarios WHERE contrato_id = %s", (c['id'],))
        total_usuarios = users_count['c'] if users_count else 0

        carga_hoje = bool(info_hoje)
        if carga_hoje:
            total_enviados_hoje += 1
        else:
            total_pendentes_hoje += 1

        contratos_status.append({
            'contrato': c,
            'carga_hoje': carga_hoje,
            'info_hoje': info_hoje,
            'ultima_carga': ultima_carga,
            'total_linhas': total_acumulado,
            'total_usuarios': total_usuarios
        })

    # Histórico recente global consolidado
    historico_global = query_all("""
        SELECT l.id, l.tipo_base, l.tabela_destino, l.nome_arquivo, l.total_linhas,
               l.data_referencia, l.acao, l.status, l.mensagem, l.criado_em,
               u.nome as usuario_nome, c.nome_exibicao as contrato_nome, c.codigo as contrato_codigo
        FROM atlas_importacoes_log l
        LEFT JOIN atlas_usuarios u ON l.usuario_id = u.id
        LEFT JOIN atlas_contratos c ON l.contrato_id = c.id
        ORDER BY l.criado_em DESC
        LIMIT 30
    """)

    return render_template(
        'admin/dashboard.html',
        user=user,
        contratos_status=contratos_status,
        total_enviados_hoje=total_enviados_hoje,
        total_pendentes_hoje=total_pendentes_hoje,
        historico_global=historico_global,
        todos_contratos_sidebar=todos_contratos
    )

def render_operator_dashboard(user, contrato_id, is_admin_preview=False):
    """Renderiza a visão de operador para um contrato específico."""
    contrato = query_one("""
        SELECT id, codigo, nome_exibicao, tabela_principal, tabela_secundaria, tabela_terciaria, coluna_data, criado_em
        FROM atlas_contratos
        WHERE id = %s
    """, (contrato_id,))

    if not contrato:
        flash("Contrato não encontrado.", "danger")
        return render_template('dashboard.html', user=user, contrato=None)

    # Informações da última importação deste contrato
    ultima_importacao = query_one("""
        SELECT l.id, l.tipo_base, l.tabela_destino, l.nome_arquivo, l.total_linhas,
               l.data_referencia, l.status, l.mensagem, l.criado_em, u.nome as usuario_nome
        FROM atlas_importacoes_log l
        LEFT JOIN atlas_usuarios u ON l.usuario_id = u.id
        WHERE l.contrato_id = %s
        ORDER BY l.criado_em DESC
        LIMIT 1
    """, (contrato['id'],))

    # Carga de hoje
    carga_hoje = query_one("""
        SELECT id FROM atlas_importacoes_log
        WHERE contrato_id = %s AND DATE(criado_em) = CURRENT_DATE AND status = 'sucesso'
        LIMIT 1
    """, (contrato['id'],))

    # Histórico recente das últimas cargas
    historico_importacoes = query_all("""
        SELECT l.id, l.tipo_base, l.tabela_destino, l.nome_arquivo, l.total_linhas,
               l.data_referencia, l.acao, l.status, l.mensagem, l.criado_em,
               u.nome as usuario_nome
        FROM atlas_importacoes_log l
        LEFT JOIN atlas_usuarios u ON l.usuario_id = u.id
        WHERE l.contrato_id = %s
        ORDER BY l.criado_em DESC
        LIMIT 10
    """, (contrato['id'],))

    # Tabela de Tipos de Serviço & Valores (habilitada para brk_fiscalizacao e brk_hidrometro)
    has_services = contrato['codigo'] in ('brk_fiscalizacao', 'brk_hidrometro')
    servicos = []
    if has_services:
        servicos = query_all("""
            SELECT id, tipo_servico, valor_servico, atualizado_em
            FROM atlas_servicos_valores
            WHERE contrato_id = %s
            ORDER BY tipo_servico ASC
        """, (contrato['id'],))

    todos_contratos = []
    if user['is_admin']:
        todos_contratos = query_all("SELECT id, codigo, nome_exibicao FROM atlas_contratos WHERE ativo = TRUE ORDER BY nome_exibicao")

    return render_template(
        'dashboard.html',
        user=user,
        contrato=contrato,
        todos_contratos=todos_contratos,
        ultima_importacao=ultima_importacao,
        carga_hoje=bool(carga_hoje),
        historico=historico_importacoes,
        has_services=has_services,
        servicos=servicos,
        is_admin_preview=is_admin_preview,
        today=date.today().isoformat()
    )

@main_bp.route('/admin/contrato/<int:contrato_id>')
@admin_required
def admin_ver_contrato(contrato_id):
    """Permite ao administrador inspecionar a visão operacional de um contrato."""
    user = get_current_user()
    return render_operator_dashboard(user, contrato_id, is_admin_preview=True)

# ----------------- ADMIN: GESTÃO DE USUÁRIOS E SENHAS -----------------

@main_bp.route('/admin/usuarios', methods=['GET'])
@admin_required
def admin_usuarios():
    user = get_current_user()
    usuarios = query_all("""
        SELECT u.id, u.nome, u.username, u.contrato_id, u.is_admin, u.ativo, u.criado_em,
               c.nome_exibicao as contrato_nome, c.codigo as contrato_codigo
        FROM atlas_usuarios u
        LEFT JOIN atlas_contratos c ON u.contrato_id = c.id
        ORDER BY u.is_admin DESC, u.nome ASC
    """)
    todos_contratos = query_all("SELECT id, codigo, nome_exibicao, tabela_principal FROM atlas_contratos WHERE ativo = TRUE ORDER BY nome_exibicao")
    
    return render_template(
        'admin/usuarios.html',
        user=user,
        usuarios=usuarios,
        todos_contratos_sidebar=todos_contratos
    )

@main_bp.route('/admin/usuarios/novo', methods=['POST'])
@admin_required
def admin_criar_usuario():
    nome = request.form.get('nome', '').strip()
    username = request.form.get('username', '').strip().lower()
    password = request.form.get('password', '')
    contrato_id = request.form.get('contrato_id', type=int) or None
    is_admin = bool(request.form.get('is_admin'))

    if not nome or not username or not password:
        flash("Todos os campos obrigatórios devem ser preenchidos.", "danger")
        return redirect(url_for('main.admin_usuarios'))

    if len(password) < 6:
        flash("A senha deve conter no mínimo 6 caracteres.", "warning")
        return redirect(url_for('main.admin_usuarios'))

    # Verifica se username já existe
    existente = query_one("SELECT id FROM atlas_usuarios WHERE username = %s", (username,))
    if existente:
        flash(f"O nome de usuário '{username}' já está em uso.", "danger")
        return redirect(url_for('main.admin_usuarios'))

    pwd_hash = generate_password_hash(password)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO atlas_usuarios (nome, username, password_hash, contrato_id, is_admin, ativo)
                VALUES (%s, %s, %s, %s, %s, TRUE)
            """, (nome, username, pwd_hash, contrato_id, is_admin))

    flash(f"✅ Usuário '{nome}' (@{username}) criado com sucesso!", "success")
    return redirect(url_for('main.admin_usuarios'))

@main_bp.route('/admin/usuarios/<int:user_id>/senha', methods=['POST'])
@admin_required
def admin_alterar_senha(user_id):
    nova_senha = request.form.get('nova_senha', '').strip()
    if not nova_senha or len(nova_senha) < 6:
        flash("A nova senha deve ter no mínimo 6 caracteres.", "warning")
        return redirect(url_for('main.admin_usuarios'))

    alvo = query_one("SELECT id, nome, username FROM atlas_usuarios WHERE id = %s", (user_id,))
    if not alvo:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for('main.admin_usuarios'))

    pwd_hash = generate_password_hash(nova_senha)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE atlas_usuarios SET password_hash = %s WHERE id = %s", (pwd_hash, user_id))

    flash(f"✅ Senha do usuário '{alvo['nome']}' alterada com sucesso!", "success")
    return redirect(url_for('main.admin_usuarios'))

@main_bp.route('/admin/usuarios/<int:user_id>/toggle', methods=['POST'])
@admin_required
def admin_toggle_usuario(user_id):
    user = get_current_user()
    if user['id'] == user_id:
        flash("Você não pode desativar seu próprio usuário.", "warning")
        return redirect(url_for('main.admin_usuarios'))

    alvo = query_one("SELECT id, nome, ativo FROM atlas_usuarios WHERE id = %s", (user_id,))
    if not alvo:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for('main.admin_usuarios'))

    novo_status = not alvo['ativo']
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE atlas_usuarios SET ativo = %s WHERE id = %s", (novo_status, user_id))

    status_str = "ativado" if novo_status else "desativado"
    flash(f"Usuário '{alvo['nome']}' foi {status_str}.", "info")
    return redirect(url_for('main.admin_usuarios'))

# ----------------- ADMIN: HISTÓRICO CONSOLIDADO -----------------

@main_bp.route('/admin/historico', methods=['GET'])
@admin_required
def admin_historico():
    user = get_current_user()
    todos_contratos = query_all("SELECT id, codigo, nome_exibicao FROM atlas_contratos WHERE ativo = TRUE ORDER BY nome_exibicao")
    
    historico = query_all("""
        SELECT l.id, l.tipo_base, l.tabela_destino, l.nome_arquivo, l.total_linhas,
               l.data_referencia, l.acao, l.status, l.mensagem, l.criado_em,
               u.nome as usuario_nome, c.nome_exibicao as contrato_nome, c.codigo as contrato_codigo
        FROM atlas_importacoes_log l
        LEFT JOIN atlas_usuarios u ON l.usuario_id = u.id
        LEFT JOIN atlas_contratos c ON l.contrato_id = c.id
        ORDER BY l.criado_em DESC
        LIMIT 200
    """)

    return render_template(
        'admin/historico.html',
        user=user,
        historico=historico,
        todos_contratos_sidebar=todos_contratos
    )

# ----------------- OPERAÇÕES DE IMPORTAÇÃO & SERVIÇOS -----------------

@main_bp.route('/importar/<tipo_base>', methods=['POST'])
@login_required
def importar_base(tipo_base):
    if tipo_base not in ('principal', 'secundaria', 'terciaria', 'irregularidades'):
        flash("Tipo de base inválido.", "danger")
        return redirect(url_for('main.dashboard'))

    user = get_current_user()
    contrato_id = request.form.get('contrato_id', type=int)

    # Segurança: operador comum só pode importar para o seu próprio contrato
    if not user['is_admin']:
        contrato_id = user['contrato_id']

    contrato = query_one("SELECT * FROM atlas_contratos WHERE id = %s", (contrato_id,))
    if not contrato:
        flash("Contrato não encontrado.", "danger")
        return redirect(url_for('main.dashboard'))

    dest_redirect = url_for('main.admin_ver_contrato', contrato_id=contrato_id) if user['is_admin'] else url_for('main.dashboard')

    if tipo_base == 'principal':
        target_table = contrato['tabela_principal']
        log_tipo = 'principal'
    elif tipo_base == 'secundaria':
        target_table = contrato['tabela_secundaria']
        log_tipo = 'secundaria'
        if not target_table:
            flash("Este contrato não possui base secundária (Diagnóstico) configurada.", "warning")
            return redirect(dest_redirect)
    elif tipo_base in ('terciaria', 'irregularidades'):
        target_table = contrato.get('tabela_terciaria')
        log_tipo = 'irregularidades'
        if not target_table:
            flash("Este contrato não possui base de Irregularidades configurada.", "warning")
            return redirect(dest_redirect)

    if 'file' not in request.files:
        flash("Nenhum arquivo enviado.", "danger")
        return redirect(dest_redirect)

    file = request.files['file']
    if file.filename == '':
        flash("Nenhum arquivo selecionado.", "danger")
        return redirect(dest_redirect)

    action = request.form.get('action', 'substituir_data')

    res = process_and_import(
        file_storage=file,
        filename=file.filename,
        target_table=target_table,
        contrato_id=contrato['id'],
        usuario_id=user['id'],
        tipo_base=log_tipo,
        action=action,
        date_col=contrato['coluna_data'] or 'data'
    )

    if res['success']:
        flash(f"✅ {res['message']}", "success")
    else:
        flash(f"❌ {res['message']}", "danger")

    return redirect(dest_redirect)

@main_bp.route('/servicos/exportar/<int:contrato_id>')
@login_required
def exportar_servicos(contrato_id):
    user = get_current_user()
    if not user['is_admin'] and user['contrato_id'] != contrato_id:
        flash("Acesso não autorizado a este contrato.", "danger")
        return redirect(url_for('main.dashboard'))

    contrato = query_one("SELECT codigo, nome_exibicao FROM atlas_contratos WHERE id = %s", (contrato_id,))
    if not contrato:
        flash("Contrato não encontrado.", "danger")
        return redirect(url_for('main.dashboard'))

    servicos = query_all("""
        SELECT tipo_servico, valor_servico 
        FROM atlas_servicos_valores 
        WHERE contrato_id = %s 
        ORDER BY tipo_servico ASC
    """, (contrato_id,))

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['tipo_servico', 'valor_servico'])
    for s in servicos:
        v = f"{s['valor_servico']:.2f}".replace('.', ',') if s['valor_servico'] is not None else '0,00'
        writer.writerow([s['tipo_servico'], v])

    csv_bytes = output.getvalue().encode('utf-8-sig')
    filename = f"tabela_servicos_{contrato['codigo']}.csv"

    return Response(
        csv_bytes,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@main_bp.route('/servicos/importar/<int:contrato_id>', methods=['POST'])
@login_required
def importar_servicos(contrato_id):
    user = get_current_user()
    if not user['is_admin'] and user['contrato_id'] != contrato_id:
        flash("Acesso não autorizado a este contrato.", "danger")
        return redirect(url_for('main.dashboard'))

    contrato = query_one("SELECT * FROM atlas_contratos WHERE id = %s", (contrato_id,))
    if not contrato:
        flash("Contrato não encontrado.", "danger")
        return redirect(url_for('main.dashboard'))

    dest_redirect = url_for('main.admin_ver_contrato', contrato_id=contrato_id) if user['is_admin'] else url_for('main.dashboard')

    if 'file' not in request.files:
        flash("Nenhum arquivo enviado.", "danger")
        return redirect(dest_redirect)

    file = request.files['file']
    if file.filename == '':
        flash("Nenhum arquivo selecionado.", "danger")
        return redirect(dest_redirect)

    try:
        from app.importer import read_uploaded_file, normalize_column_name
        df = read_uploaded_file(file, file.filename)
        if df.empty:
            flash("O arquivo de serviços enviado está vazio.", "warning")
            return redirect(dest_redirect)

        df.columns = [normalize_column_name(c) for c in df.columns]

        col_tipo = None
        for c in df.columns:
            if c in ('tipo_servico', 'tipo_de_servico', 'servico', 'descricao', 'nome'):
                col_tipo = c
                break

        col_valor = None
        for c in df.columns:
            if c in ('valor_servico', 'valor_do_servico', 'valor', 'preco', 'tarifa'):
                col_valor = c
                break

        if not col_tipo or not col_valor:
            flash("O arquivo precisa conter colunas identificáveis como 'tipo_servico' e 'valor_servico'.", "danger")
            return redirect(dest_redirect)

        novos_servicos = []
        for _, row in df.iterrows():
            tipo = str(row[col_tipo]).strip()
            if not tipo or tipo.lower() in ('nan', 'none', 'null'):
                continue

            val_raw = str(row[col_valor]).replace('R$', '').strip()
            try:
                if ',' in val_raw and '.' in val_raw:
                    val_clean = val_raw.replace('.', '').replace(',', '.')
                elif ',' in val_raw:
                    val_clean = val_raw.replace(',', '.')
                else:
                    val_clean = val_raw
                valor_f = float(val_clean)
            except Exception:
                valor_f = 0.00

            novos_servicos.append((contrato_id, tipo, valor_f))

        if not novos_servicos:
            flash("Nenhum serviço válido identificado no arquivo.", "warning")
            return redirect(dest_redirect)

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM atlas_servicos_valores WHERE contrato_id = %s", (contrato_id,))
                
                from psycopg2.extras import execute_values
                execute_values(
                    cur,
                    "INSERT INTO atlas_servicos_valores (contrato_id, tipo_servico, valor_servico) VALUES %s",
                    novos_servicos,
                    page_size=500
                )

                cur.execute("""
                    INSERT INTO atlas_importacoes_log 
                    (contrato_id, usuario_id, tipo_base, tabela_destino, nome_arquivo, total_linhas, acao, status, mensagem)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    contrato_id,
                    user['id'],
                    'servicos',
                    'atlas_servicos_valores',
                    file.filename,
                    len(novos_servicos),
                    'substituicao_completa',
                    'sucesso',
                    f"Tabela de serviços e valores substituída com sucesso ({len(novos_servicos)} registros)."
                ))

        flash(f"✅ Tabela de serviços e valores atualizada com sucesso ({len(novos_servicos)} tipos de serviços cadastrados)!", "success")

    except Exception as e:
        flash(f"❌ Erro ao atualizar tabela de serviços: {str(e)}", "danger")

    return redirect(dest_redirect)
