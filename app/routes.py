import io
import csv
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, Response
from datetime import date
from app.auth import login_required, get_current_user
from app.db import get_db, query_one, query_all
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

    # Informações da última importação
    ultima_importacao = query_one("""
        SELECT l.id, l.tipo_base, l.tabela_destino, l.nome_arquivo, l.total_linhas,
               l.data_referencia, l.status, l.mensagem, l.criado_em, u.nome as usuario_nome
        FROM atlas_importacoes_log l
        LEFT JOIN atlas_usuarios u ON l.usuario_id = u.id
        WHERE l.contrato_id = %s
        ORDER BY l.criado_em DESC
        LIMIT 1
    """, (contrato['id'],))

    # Verificação de status de hoje (se houve carga hoje)
    carga_hoje = query_one("""
        SELECT id FROM atlas_importacoes_log
        WHERE contrato_id = %s AND DATE(criado_em) = CURRENT_DATE AND status = 'sucesso'
        LIMIT 1
    """, (contrato['id'],))

    # Histórico recente das últimas 10 importações
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

    # Gera CSV com delimitador ';' e UTF-8 com BOM para abrir perfeitamente no Excel
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

    if 'file' not in request.files:
        flash("Nenhum arquivo enviado.", "danger")
        return redirect(url_for('main.dashboard', contrato_id=contrato_id))

    file = request.files['file']
    if file.filename == '':
        flash("Nenhum arquivo selecionado.", "danger")
        return redirect(url_for('main.dashboard', contrato_id=contrato_id))

    try:
        from app.importer import read_uploaded_file, normalize_column_name
        df = read_uploaded_file(file, file.filename)
        if df.empty:
            flash("O arquivo de serviços enviado está vazio.", "warning")
            return redirect(url_for('main.dashboard', contrato_id=contrato_id))

        # Normaliza colunas
        df.columns = [normalize_column_name(c) for c in df.columns]

        # Encontra coluna de tipo/serviço e valor
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
            return redirect(url_for('main.dashboard', contrato_id=contrato_id))

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
            return redirect(url_for('main.dashboard', contrato_id=contrato_id))

        # Substitui a tabela do contrato atomicamente
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

    return redirect(url_for('main.dashboard', contrato_id=contrato_id))

