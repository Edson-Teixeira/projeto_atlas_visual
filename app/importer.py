import os
import io
import re
import unicodedata
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, date, time
from app.db import get_db, execute, query_one, query_all

def normalize_column_name(name: str) -> str:
    """Normaliza o nome da coluna para padrão snake_case sem acentos."""
    name = str(name).strip().lower()
    # Remove acentos
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('utf-8')
    # Substitui caracteres especiais por underline
    name = re.sub(r'[^a-z0-9_]+', '_', name)
    name = re.sub(r'_+', '_', name).strip('_')
    return name

def get_table_column_types(table_name: str) -> dict[str, str]:
    """Retorna um dicionário {coluna: data_type} da tabela no PostgreSQL."""
    sql = """
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = %s;
    """
    rows = query_all(sql, (table_name,))
    return {r['column_name']: r['data_type'] for r in rows}

def parse_date_value(val):
    """
    Converte múltiplos formatos de data (ex: 22/10/26, 09/14/26, 14/09/2026, 2026-09-14)
    para um objeto date nativo do Python (YYYY-MM-DD).
    """
    if pd.isnull(val) or val == '' or str(val).strip().lower() in ('nan', 'none', 'null', 'nat'):
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()

    val_str = str(val).strip()
    
    # 1. Tenta formatos conhecidos explicitamente
    known_formats = [
        '%d/%m/%Y',    # 28/08/2026, 01/09/2026 (DD/MM/YYYY - Padrão Nacional)
        '%d/%m/%y',    # 22/10/26 (DD/MM/YY)
        '%Y-%m-%d',    # 2026-09-14 (ISO)
        '%Y/%m/%d',    # 2026/09/14
        '%m/%d/%y',    # 09/14/26 (MM/DD/YY - fallback para datas onde mês vem primeiro e dia > 12)
        '%m/%d/%Y',    # 09/14/2026
    ]
    for fmt in known_formats:
        try:
            return datetime.strptime(val_str, fmt).date()
        except ValueError:
            pass

    # 2. Fallback flexível via pandas com dayfirst=True
    try:
        dt = pd.to_datetime(val_str, format='mixed', errors='coerce', dayfirst=True)
        if pd.notnull(dt):
            return dt.date()
    except Exception:
        pass

    return None

def parse_timestamp_value(val):
    """Converte valores para timestamp (datetime) do Python com alta compatibilidade."""
    if pd.isnull(val) or val == '' or str(val).strip().lower() in ('nan', 'none', 'null', 'nat'):
        return None
    if isinstance(val, datetime):
        return val
    val_str = str(val).strip()

    known_formats = [
        '%d/%m/%Y %H:%M:%S',
        '%d/%m/%y %H:%M:%S',
        '%d/%m/%Y %H:%M',
        '%d/%m/%y %H:%M',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%m/%d/%Y %H:%M:%S',
        '%m/%d/%y %H:%M:%S',
        '%m/%d/%Y %H:%M',
        '%m/%d/%y %H:%M',
    ]
    for fmt in known_formats:
        try:
            return datetime.strptime(val_str, fmt)
        except ValueError:
            pass

    try:
        dt = pd.to_datetime(val_str, format='mixed', errors='coerce', dayfirst=True)
        if pd.notnull(dt):
            return dt.to_pydatetime()
    except Exception:
        pass
    return None

def parse_time_value(val):
    """Converte strings de hora (ex: 10:32, 10:32:00) para datetime.time."""
    if pd.isnull(val) or val == '' or str(val).strip().lower() in ('nan', 'none', 'null', 'nat'):
        return None
    if isinstance(val, time):
        return val
    if isinstance(val, datetime):
        return val.time()
    val_str = str(val).strip()
    for fmt in ('%H:%M:%S', '%H:%M'):
        try:
            return datetime.strptime(val_str, fmt).time()
        except ValueError:
            pass
    return None

def parse_interval_value(val):
    """Garante formatação correta de strings de intervalo (ex: '00:07', '02:21')."""
    if pd.isnull(val) or val == '' or str(val).strip().lower() in ('nan', 'none', 'null', 'nat'):
        return None
    s = str(val).strip()
    return s if s else None

def parse_numeric_value(val):
    """Converte valores numéricos aceitando separador decimal vírgula ou ponto."""
    if pd.isnull(val) or val == '' or str(val).strip().lower() in ('nan', 'none', 'null'):
        return None
    try:
        s = str(val).strip()
        if ',' in s and '.' in s:
            s = s.replace('.', '').replace(',', '.')
        elif ',' in s:
            s = s.replace(',', '.')
        return float(s)
    except Exception:
        return None

def parse_int_value(val):
    """Converte valores inteiros de forma segura."""
    if pd.isnull(val) or val == '' or str(val).strip().lower() in ('nan', 'none', 'null'):
        return None
    try:
        return int(float(str(val).strip().replace(',', '.')))
    except Exception:
        return None

def parse_str_value(val):
    """Normaliza texto removendo sufixo .0 de números formatados como float."""
    if pd.isnull(val) or val == '' or str(val).strip().lower() in ('nan', 'none', 'null'):
        return None
    s = str(val).strip()
    if s.endswith('.0') and s[:-2].isdigit():
        return s[:-2]
    return s

def read_uploaded_file(file_storage, filename: str) -> pd.DataFrame:
    """
    Lê o arquivo enviado suportando CSV/TSV (vírgula, ponto-e-vírgula, tab, pipe, utf-8, latin1)
    e planilhas Excel (.xlsx, .xls) com detecção inteligente de formato e delimitador,
    incluindo fallback automático para arquivos de texto delimitados salvos com extensão .xlsx/.xls.
    """
    ext = os.path.splitext(filename)[1].lower()
    content = file_storage.read()
    df = None

    # 1. Se for extensão Excel (.xlsx, .xls), tenta ler primeiro como planilha binária
    if ext in ('.xlsx', '.xls'):
        try:
            df = pd.read_excel(io.BytesIO(content))
        except Exception:
            # Fallback resiliente: muitos sistemas corporativos exportam ou usuários salvam
            # arquivos de texto delimitados (TSV/CSV) com extensão .xlsx/.xls para abrir direto no Excel.
            df = None

    # 2. Se for CSV/TSV/TXT ou se a leitura binária do Excel falhou (arquivo na verdade é delimitado)
    if df is None:
        encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']
        separators = ['\t', ';', ',', '|']
        
        max_cols = 0
        best_enc = None
        best_sep = None

        for enc in encodings:
            for sep in separators:
                try:
                    sample = pd.read_csv(io.BytesIO(content), sep=sep, encoding=enc, nrows=5)
                    cols_count = len(sample.columns)
                    if cols_count > max_cols:
                        max_cols = cols_count
                        best_enc = enc
                        best_sep = sep
                except Exception:
                    continue
            if max_cols > 1 and best_enc in ('utf-8-sig', 'utf-8'):
                break

        if best_enc and best_sep and max_cols > 1:
            try:
                df = pd.read_csv(io.BytesIO(content), sep=best_sep, encoding=best_enc)
            except Exception:
                pass

        if df is None:
            for enc in ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']:
                try:
                    df = pd.read_csv(io.BytesIO(content), sep=None, engine='python', encoding=enc)
                    break
                except Exception:
                    continue

    # 3. Fallback inverso: caso um arquivo .csv seja na verdade uma planilha Excel binária
    if df is None:
        try:
            df = pd.read_excel(io.BytesIO(content))
        except Exception:
            pass

    if df is None:
        raise ValueError("Não foi possível ler o arquivo. Verifique a codificação e formato do arquivo.")

    return df

# Mapeamento expandido de sinônimos/aliases para máxima robustez
SYNONYMS = {
    'ordem_servico': ['ordem_de_servico', 'os', 'ordem', 'ordem_servico'],
    'status_atividade': ['status_da_atividade', 'status', 'status_atividade'],
    'email': ['e_mail', 'correio_eletronico', 'email'],
    'intervalo_tempo': ['intervalo_de_tempo', 'intervalo', 'intervalo_tempo'],
    'janela_servico': ['janela_de_servico', 'janela', 'janela_servico'],
    'inicio_sla': ['inicio_do_sla', 'sla_inicio', 'inicio_sla'],
    'fim_sla': ['fim_do_sla', 'sla_fim', 'fim_sla'],
    'tempo_deslocamento': ['tempo_de_deslocamento', 'deslocamento', 'tempo_deslocamento'],
    'tipo_atividade': ['tipo_de_atividade', 'atividade', 'tipo_atividade'],
    'habilidade_trabalho': ['habilidade_de_trabalho', 'habilidade', 'habilidade_trabalho'],
    'area_trabalho': ['area_de_trabalho', 'area', 'area_trabalho'],
    'nome_equipe': ['nome_da_equipe', 'equipe', 'nome_equipe'],
    'cdc_matricula': ['cdc', 'matricula', 'conta', 'cdc_matricula', 'cdc_ou_matricula'],
    'cdc': ['cdc_matricula', 'matricula', 'conta', 'cdc'],
    'os': ['ordem_servico', 'ordem_de_servico', 'os', 'ordem'],
    'prazo_cliente': ['prazo_do_cliente', 'prazo', 'prazo_cliente'],
    'cep_codigo_postal': ['cep', 'codigo_postal', 'cep_codigo_postal'],
    'telefone_celular': ['celular', 'tel_celular', 'telefone_celular'],
    'no_toi': ['n_toi', 'num_toi', 'numero_toi', 'toi'],
    'num_toi': ['no_toi', 'n_toi', 'numero_toi', 'toi'],
    'observacoes': ['observacao', 'obs'],
    'equipe': ['nome_da_equipe', 'nome_equipe', 'equipe'],
    'irregularidade': ['irregularidade', 'descricao_irregularidade', 'tipo_irregularidade', 'motivo_irregularidade'],
}

# Colunas obrigatórias exigidas no padrão de cada base para impedir upload de bases incompatíveis
REQUIRED_COLUMNS_BY_TABLE = {
    'brk_fiscalizacao': ['ordem_servico', 'status_atividade', 'data', 'recurso', 'cdc_matricula'],
    'brk_hidrometro': ['ordem_servico', 'status_atividade', 'data', 'recurso', 'cdc_matricula'],
    'brk_fisca_secundaria': ['ordem_servico', 'status_atividade', 'data'],
    'brk_irregularidades': ['os', 'data', 'irregularidade'],
    'brk_pav_comer': ['ordem_servico', 'data'],
    'brk_pav_opera': ['ordem_servico', 'data'],
}

COLUMN_DISPLAY_NAMES = {
    'ordem_servico': 'Ordem de Serviço (OS)',
    'status_atividade': 'Status da Atividade',
    'data': 'Data',
    'recurso': 'Recurso',
    'cdc_matricula': 'CDC/Matrícula',
    'os': 'OS / Ordem de Serviço',
    'cdc': 'CDC / Matrícula',
    'irregularidade': 'Irregularidade',
    'no_toi': 'Nº TOI',
    'equipe': 'Equipe',
    'nome_equipe': 'Nome da Equipe',
    'habilidade_trabalho': 'Habilidade de Trabalho',
    'area_trabalho': 'Área de Trabalho',
    'prazo_cliente': 'Prazo do Cliente',
    'tipo_servico': 'Tipo de Serviço',
    'valor_servico': 'Valor do Serviço',
}

TABLE_BASE_NAMES = {
    'brk_fiscalizacao': 'Base Principal (Fiscalização)',
    'brk_hidrometro': 'Base Principal (Hidrômetro)',
    'brk_fisca_secundaria': 'Base Secundária (Diagnóstico)',
    'brk_irregularidades': 'Base de Irregularidades',
    'brk_pav_comer': 'Base Pav. Comercial',
    'brk_pav_opera': 'Base Pav. Operacional',
}

def validate_file_columns(target_table: str, present_cols: set[str], db_cols: set[str]) -> tuple[bool, str]:
    """
    Valida rigorosamente se o arquivo enviado possui a estrutura e o padrão de colunas
    esperado para a tabela de destino, impedindo a importação de bases incompatíveis ou arquivos aleatórios.
    """
    base_name = TABLE_BASE_NAMES.get(target_table, f"tabela '{target_table}'")

    # 1. Validação por regras específicas da tabela de destino
    if target_table in REQUIRED_COLUMNS_BY_TABLE:
        req_cols = REQUIRED_COLUMNS_BY_TABLE[target_table]
        missing = [c for c in req_cols if c not in present_cols]
        if missing:
            missing_labels = [COLUMN_DISPLAY_NAMES.get(c, c) for c in missing]
            return False, (
                f"O arquivo enviado não possui o padrão de colunas esperado para a {base_name}. "
                f"Colunas obrigatórias ausentes no arquivo: {', '.join(missing_labels)}. "
                f"Verifique se selecionou o arquivo correto."
            )

    # 2. Validação geral / heurística para tabelas customizadas
    matched = [c for c in present_cols if c in db_cols and c != 'id']
    if not matched:
        return False, f"Nenhuma coluna do arquivo coincide com a estrutura da {base_name}."

    if len(matched) < 2 and len(db_cols) > 3:
        return False, (
            f"O arquivo enviado não possui o padrão de colunas esperado para a {base_name}. "
            f"Apenas a coluna '{matched[0]}' foi reconhecida. Verifique se selecionou o arquivo correto."
        )

    return True, ""

def process_and_import(
    file_storage,
    filename: str,
    target_table: str,
    contrato_id: int,
    usuario_id: int,
    tipo_base: str,
    action: str = 'substituir_data', # 'substituir_data' ou 'append'
    date_col: str = 'data'
) -> dict:
    """
    Processa a importação do arquivo para o PostgreSQL com tratamento inteligente
    de colunas, sinônimos, idempotência por data e log de auditoria.
    """
    try:
        # 1. Carrega DataFrame
        df = read_uploaded_file(file_storage, filename)
        if df.empty:
            return {"success": False, "message": "O arquivo enviado está vazio.", "total_lines": 0}

        # 2. Normaliza os nomes das colunas do arquivo
        df.columns = [normalize_column_name(c) for c in df.columns]

        # 3. Consulta colunas existentes e tipos na tabela de destino
        col_types = get_table_column_types(target_table)
        if not col_types:
            return {"success": False, "message": f"Tabela de destino '{target_table}' não encontrada no banco.", "total_lines": 0}

        db_cols = set(col_types.keys())

        # Renomeia colunas do arquivo se houver sinônimo ou correspondência inteligente
        renames = {}
        for col in df.columns:
            if col not in db_cols:
                found = False
                # 1. Procura na tabela de sinônimos explícitos
                for target_db_col, aliases in SYNONYMS.items():
                    if target_db_col in db_cols and col in aliases:
                        renames[col] = target_db_col
                        found = True
                        break
                if found:
                    continue

                # 2. Remoção de preposições comuns em português (_de_, _da_, _do_, _dos_, _das_)
                stripped = re.sub(r'_(de|da|do|dos|das)_', '_', col)
                if stripped in db_cols:
                    renames[col] = stripped
                    continue

                # 3. Comparação canônica sem underlines (ex: e_mail -> email)
                col_clean = col.replace('_', '')
                for target_db_col in db_cols:
                    if col_clean == target_db_col.replace('_', ''):
                        renames[col] = target_db_col
                        break

        if renames:
            df.rename(columns=renames, inplace=True)

        # 4. Validação estrita do padrão de colunas para a tabela de destino
        is_valid, validation_msg = validate_file_columns(target_table, set(df.columns), db_cols)
        if not is_valid:
            try:
                execute("""
                    INSERT INTO atlas_importacoes_log 
                    (contrato_id, usuario_id, tipo_base, tabela_destino, nome_arquivo, total_linhas, acao, status, mensagem)
                    VALUES (%s, %s, %s, %s, %s, 0, %s, 'erro', %s)
                """, (contrato_id, usuario_id, tipo_base, target_table, filename, action, validation_msg))
            except Exception:
                pass

            return {
                "success": False,
                "message": validation_msg,
                "total_lines": 0
            }

        # Mapeia colunas coincidentes (desconsidera colunas como 'id' autoincrement se o arquivo não tiver)
        matched_cols = [c for c in df.columns if c in db_cols and c != 'id']
        if not matched_cols:
            return {
                "success": False,
                "message": f"Nenhuma coluna do arquivo coincide com as colunas da tabela '{target_table}'.",
                "total_lines": 0
            }

        # Filtra DataFrame somente para as colunas válidas
        df_to_insert = df[matched_cols].copy()

        # 4. Trata e converte colunas para compatibilidade exata com PostgreSQL
        for col in matched_cols:
            dtype = col_types.get(col, '').lower()
            if dtype == 'date':
                df_to_insert[col] = df_to_insert[col].apply(parse_date_value)
            elif 'timestamp' in dtype:
                df_to_insert[col] = df_to_insert[col].apply(parse_timestamp_value)
            elif 'time' in dtype and 'timestamp' not in dtype:
                df_to_insert[col] = df_to_insert[col].apply(parse_time_value)
            elif 'interval' in dtype:
                df_to_insert[col] = df_to_insert[col].apply(parse_interval_value)
            elif any(t in dtype for t in ('numeric', 'decimal', 'double', 'real', 'float')):
                df_to_insert[col] = df_to_insert[col].apply(parse_numeric_value)
            elif 'int' in dtype:
                df_to_insert[col] = df_to_insert[col].apply(parse_int_value)
            elif 'char' in dtype or 'text' in dtype:
                df_to_insert[col] = df_to_insert[col].apply(parse_str_value)

        # Substitui NaN/None por None para inserção correta de NULLs no PostgreSQL
        df_to_insert = df_to_insert.astype(object).where(pd.notnull(df_to_insert), None)

        # Todas as linhas do lote sao mantidas (sem descartar linhas sem OS ou Status)

        # 5. Trata datas de referência para idempotência diária
        reference_date = None
        unique_dates = []
        if date_col in df_to_insert.columns:
            unique_dates = list(set(d for d in df_to_insert[date_col] if isinstance(d, date)))
            if unique_dates:
                reference_date = unique_dates[0]

        linhas_removidas = 0
        total_a_inserir = len(df_to_insert)

        with get_db() as conn:
            with conn.cursor() as cur:
                # Se a ação for 'substituir_data' e tivermos datas identificadas
                if action == 'substituir_data' and unique_dates and date_col in db_cols:
                    if len(unique_dates) == 1:
                        cur.execute(f"DELETE FROM {target_table} WHERE {date_col} = %s", (unique_dates[0],))
                    else:
                        cur.execute(f"DELETE FROM {target_table} WHERE {date_col} = ANY(%s)", (unique_dates,))
                    linhas_removidas = cur.rowcount

                # 5. Inserção em lote de alto desempenho
                col_names_str = ", ".join(matched_cols)
                insert_sql = f"INSERT INTO {target_table} ({col_names_str}) VALUES %s"

                records = [tuple(row) for row in df_to_insert.to_numpy()]
                execute_values(cur, insert_sql, records, page_size=1000)

                # 6. Auto-enriquecimento de tipo_servico e valor_servico para brk_fiscalizacao
                if target_table == 'brk_fiscalizacao':
                    try:
                        cur.execute("""
                            UPDATE brk_fiscalizacao f
                            SET tipo_servico = CASE
                                WHEN habilidade_trabalho ILIKE '%FISCALIZA%' OR habilidade_trabalho ILIKE '%VISTORIA%' THEN 'Fiscalização'
                                WHEN habilidade_trabalho ILIKE '%CORTE%' OR habilidade_trabalho ILIKE '%SUSPENS%' THEN 'Corte'
                                WHEN habilidade_trabalho ILIKE '%REGULARIZA%' THEN 'Regularização'
                                WHEN habilidade_trabalho ILIKE '%RELIGA%' THEN 'Religação'
                                WHEN habilidade_trabalho ILIKE '%HIDR%' THEN 'Hidrômetro'
                                WHEN habilidade_trabalho ILIKE '%RECOMPOSI%' THEN 'Recomposição'
                                ELSE COALESCE(f.tipo_servico, 'Outros')
                            END
                            WHERE (f.tipo_servico IS NULL OR f.tipo_servico = '') AND f.habilidade_trabalho IS NOT NULL;
                        """)
                        cur.execute("""
                            UPDATE brk_fiscalizacao f
                            SET valor_servico = v.valor_servico
                            FROM brk_fisca_valores v
                            WHERE f.valor_servico IS NULL 
                              AND (f.habilidade_trabalho = v.tipo_servico OR f.tipo_servico = v.tipo_servico);
                        """)
                    except Exception:
                        pass

                # 7. Grava log de auditoria
                msg = f"Arquivo importado com sucesso ({total_a_inserir} linhas)."
                if linhas_removidas > 0:
                    datas_str = ", ".join(str(d) for d in unique_dates)
                    msg += f" {linhas_removidas} registros anteriores da(s) data(s) {datas_str} foram substituídos."

                cur.execute("""
                    INSERT INTO atlas_importacoes_log 
                    (contrato_id, usuario_id, tipo_base, tabela_destino, nome_arquivo, total_linhas, data_referencia, acao, status, mensagem)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    contrato_id,
                    usuario_id,
                    tipo_base,
                    target_table,
                    filename,
                    total_a_inserir,
                    reference_date,
                    action,
                    'sucesso',
                    msg
                ))

        return {
            "success": True,
            "message": msg,
            "total_lines": total_a_inserir,
            "date_reference": str(reference_date) if reference_date else None,
            "rows_replaced": linhas_removidas
        }

    except Exception as e:
        import logging
        logging.exception(f"Erro detalhado na importação de '{filename}':")

        raw_msg = str(e)
        # Mensagens limpas e seguras para a interface e auditoria pública
        if "violates not-null constraint" in raw_msg:
            col_match = re.search(r'column "([^"]+)"', raw_msg)
            col_info = f" (coluna obrigatória: '{col_match.group(1)}')" if col_match else ""
            user_msg = f"O arquivo contém registros sem preenchimento de campos obrigatórios{col_info}."
        elif "duplicate key value" in raw_msg or "UniqueViolation" in raw_msg:
            user_msg = "O arquivo contém registros duplicados que conflitam com a base existente."
        elif "connection" in raw_msg.lower() or "timeout" in raw_msg.lower():
            user_msg = "Falha de comunicação temporária com o banco de dados. Tente novamente."
        elif "syntax for type" in raw_msg:
            user_msg = "O arquivo possui formatos incompatíveis de data, hora ou número em algumas linhas."
        else:
            user_msg = "Erro ao processar o arquivo. Verifique se as colunas e formatos correspondem ao padrão esperado."

        # Registra erro no log de auditoria com mensagem tratada (sem vazar IPs, portas ou dados internos)
        try:
            execute("""
                INSERT INTO atlas_importacoes_log 
                (contrato_id, usuario_id, tipo_base, tabela_destino, nome_arquivo, total_linhas, acao, status, mensagem)
                VALUES (%s, %s, %s, %s, %s, 0, %s, 'erro', %s)
            """, (contrato_id, usuario_id, tipo_base, target_table, filename, action, user_msg))
        except Exception:
            pass

        return {
            "success": False,
            "message": user_msg,
            "total_lines": 0
        }
