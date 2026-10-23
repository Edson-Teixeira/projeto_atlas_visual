from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import date
from app.auth import login_required, get_current_user
from app.db import query_one, query_all
from app.importer import process_and_import

main_bp = Blueprint('main', __name__)

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

    # Se for admin e tiver parâmetro ?contrato_id=, permite alternar visualização
    contrato_id = request.args.get('contrato_id', type=int)
    todos_contratos = []

    if user['is_admin']:
        todos_contratos = query_all("SELECT id, codigo, nome_exibicao FROM atlas_contratos WHERE ativo = TRUE ORDER BY nome_exibicao")
        if not contrato_id:
            # Se não especificou, pega o do usuário ou o primeiro da lista
            contrato_id = user['contrato_id'] or (todos_contratos[0]['id'] if todos_contratos else None)
    else:
        contrato_id = user['contrato_id']

    if not contrato_id:
        flash("Nenhum contrato vinculado a este usuário.", "warning")
        return render_template('dashboard.html', user=user, contrato=None)

    contrato = query_one("""
        SELECT id, codigo, nome_exibicao, tabela_principal, tabela_secundaria, coluna_data, criado_em
        FROM atlas_contratos
        WHERE id = %s
    """, (contrato_id,))

    if not contrato:
        flash("Contrato não encontrado.", "danger")
        return render_template('dashboard.html', user=user, contrato=None)

    # 1. Total de registros na tabela principal
    total_linhas_principal = 0
    try:
        r = query_one(f"SELECT COUNT(*) as total FROM {contrato['tabela_principal']}")
        total_linhas_principal = r['total'] if r else 0
    except Exception:
        total_linhas_principal = 0

    # 2. Total de registros na tabela secundária (se configurada)
    total_linhas_secundaria = None
    if contrato['tabela_secundaria']:
        try:
            r = query_one(f"SELECT COUNT(*) as total FROM {contrato['tabela_secundaria']}")
            total_linhas_secundaria = r['total'] if r else 0
        except Exception:
            total_linhas_secundaria = 0

    # 3. Informações da última importação
    ultima_importacao = query_one("""
        SELECT l.id, l.tipo_base, l.tabela_destino, l.nome_arquivo, l.total_linhas,
               l.data_referencia, l.status, l.mensagem, l.criado_em, u.nome as usuario_nome
        FROM atlas_importacoes_log l
        LEFT JOIN atlas_usuarios u ON l.usuario_id = u.id
        WHERE l.contrato_id = %s
        ORDER BY l.criado_em DESC
        LIMIT 1
    """, (contrato['id'],))

    # 4. Verificação de status de hoje (se houve carga hoje)
    carga_hoje = query_one("""
        SELECT id FROM atlas_importacoes_log
        WHERE contrato_id = %s AND DATE(criado_em) = CURRENT_DATE AND status = 'sucesso'
        LIMIT 1
    """, (contrato['id'],))

    # 5. Histórico recente das últimas 10 importações
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

    return render_template(
        'dashboard.html',
        user=user,
        contrato=contrato,
        todos_contratos=todos_contratos,
        total_principal=total_linhas_principal,
        total_secundaria=total_linhas_secundaria,
        ultima_importacao=ultima_importacao,
        carga_hoje=bool(carga_hoje),
        historico=historico_importacoes,
        today=date.today().isoformat()
    )

@main_bp.route('/importar/<tipo_base>', methods=['POST'])
@login_required
def importar_base(tipo_base):
    if tipo_base not in ('principal', 'secundaria'):
        flash("Tipo de base inválido.", "danger")
        return redirect(url_for('main.dashboard'))

    user = get_current_user()
    contrato_id = request.form.get('contrato_id', type=int)

    # Segurança: usuário não-admin só pode importar para o seu próprio contrato
    if not user['is_admin']:
        contrato_id = user['contrato_id']

    contrato = query_one("SELECT * FROM atlas_contratos WHERE id = %s", (contrato_id,))
    if not contrato:
        flash("Contrato não encontrado.", "danger")
        return redirect(url_for('main.dashboard'))

    if tipo_base == 'principal':
        target_table = contrato['tabela_principal']
    else:
        target_table = contrato['tabela_secundaria']
        if not target_table:
            flash("Este contrato não possui base secundária configurada.", "warning")
            return redirect(url_for('main.dashboard', contrato_id=contrato_id))

    if 'file' not in request.files:
        flash("Nenhum arquivo enviado.", "danger")
        return redirect(url_for('main.dashboard', contrato_id=contrato_id))

    file = request.files['file']
    if file.filename == '':
        flash("Nenhum arquivo selecionado.", "danger")
        return redirect(url_for('main.dashboard', contrato_id=contrato_id))

    action = request.form.get('action', 'substituir_data')

    # Executa a importação
    res = process_and_import(
        file_storage=file,
        filename=file.filename,
        target_table=target_table,
        contrato_id=contrato['id'],
        usuario_id=user['id'],
        tipo_base=tipo_base,
        action=action,
        date_col=contrato['coluna_data'] or 'data'
    )

    if res['success']:
        flash(f"✅ {res['message']}", "success")
    else:
        flash(f"❌ {res['message']}", "danger")

    return redirect(url_for('main.dashboard', contrato_id=contrato_id))
