import os
import io
import re
import unicodedata
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, date
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
    Converte múltiplos formatos de data (ex: 09/14/26, 14/09/2026, 2026-09-14)
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
        '%m/%d/%y',    # 09/14/26 (MM/DD/YY - formato reportado)
        '%m/%d/%Y',    # 09/14/2026
        '%d/%m/%Y',    # 14/09/2026 (DD/MM/YYYY)
        '%d/%m/%y',    # 14/09/26 (DD/MM/YY)
        '%Y-%m-%d',    # 2026-09-14 (ISO)
        '%Y/%m/%d',    # 2026/09/14
    ]
    for fmt in known_formats:
        try:
            return datetime.strptime(val_str, fmt).date()
        except ValueError:
            pass

    # 2. Fallback flexível via pandas
    try:
        dt = pd.to_datetime(val_str, format='mixed', errors='coerce')
        if pd.notnull(dt):
            return dt.date()
    except Exception:
        pass

    return None

def parse_timestamp_value(val):
    """Converte valores para timestamp do Python."""
    if pd.isnull(val) or val == '' or str(val).strip().lower() in ('nan', 'none', 'null', 'nat'):
        return None
    if isinstance(val, datetime):
        return val
    try:
        dt = pd.to_datetime(str(val).strip(), format='mixed', errors='coerce')
        if pd.notnull(dt):
            return dt.to_pydatetime()
    except Exception:
        pass
    return None

def read_uploaded_file(file_storage, filename: str) -> pd.DataFrame:
    """
    Lê o arquivo enviado suportando CSV (vírgula, ponto-e-vírgula, tab, utf-8, latin1)
    e planilhas Excel (.xlsx, .xls).
    """
    ext = os.path.splitext(filename)[1].lower()
    content = file_storage.read()
    
    if ext in ('.xlsx', '.xls'):
        # Leitura de Excel
        df = pd.read_excel(io.BytesIO(content))
    elif ext == '.csv':
        # Tentativa de detecção de encoding e separador para CSV
        encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']
        df = None
        last_error = None
        
        for enc in encodings:
            for sep in [';', ',', '\t']:
                try:
                    candidate = pd.read_csv(io.BytesIO(content), sep=sep, encoding=enc, nrows=5)
                    # Se tiver mais de 1 coluna, provavelmente acertamos o delimitador
                    if len(candidate.columns) > 1:
                        df = pd.read_csv(io.BytesIO(content), sep=sep, encoding=enc)
                        break
                except Exception as e:
                    last_error = e
                    continue
            if df is not None:
                break
                
        if df is None:
            # Fallback padrão
            try:
                df = pd.read_csv(io.BytesIO(content), sep=None, engine='python', encoding='utf-8')
            except Exception:
                df = pd.read_csv(io.BytesIO(content), sep=None, engine='python', encoding='latin-1')
    else:
        raise ValueError(f"Formato de arquivo não suportado: '{ext}'. Envie arquivos .csv ou .xlsx.")

    return df

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
    de colunas, idempotência por data e log de auditoria.
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

        db_cols = list(col_types.keys())

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

        # 4. Trata e converte colunas de data e timestamp para compatibilidade com PostgreSQL
        for col in matched_cols:
            dtype = col_types.get(col, '')
            if dtype == 'date':
                df_to_insert[col] = df_to_insert[col].apply(parse_date_value)
            elif 'timestamp' in dtype:
                df_to_insert[col] = df_to_insert[col].apply(parse_timestamp_value)

        # Substitui NaN/None por None para inserção correta de NULLs no PostgreSQL
        df_to_insert = df_to_insert.astype(object).where(pd.notnull(df_to_insert), None)

        # 5. Trata data de referência para idempotência diária
        reference_date = None
        if date_col in df_to_insert.columns:
            valid_dates = [d for d in df_to_insert[date_col] if isinstance(d, date)]
            if valid_dates:
                reference_date = valid_dates[0]

        linhas_removidas = 0
        total_a_inserir = len(df_to_insert)

        with get_db() as conn:
            with conn.cursor() as cur:
                # Se a ação for 'substituir_data' e tivermos uma data de referência e a coluna existir
                if action == 'substituir_data' and reference_date and date_col in db_cols:
                    cur.execute(f"DELETE FROM {target_table} WHERE {date_col} = %s", (reference_date,))
                    linhas_removidas = cur.rowcount

                # 5. Inserção em lote de alto desempenho via execute_values
                col_names_str = ", ".join(matched_cols)
                insert_sql = f"INSERT INTO {target_table} ({col_names_str}) VALUES %s"

                records = [tuple(row) for row in df_to_insert.to_numpy()]
                execute_values(cur, insert_sql, records, page_size=1000)

                # 6. Grava log de auditoria
                msg = f"Arquivo importado com sucesso ({total_a_inserir} linhas)."
                if linhas_removidas > 0:
                    msg += f" {linhas_removidas} registros anteriores da data {reference_date} foram substituídos."

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
        error_msg = f"Erro ao processar importação: {str(e)}"
        # Registra erro no log de auditoria
        try:
            execute("""
                INSERT INTO atlas_importacoes_log 
                (contrato_id, usuario_id, tipo_base, tabela_destino, nome_arquivo, total_linhas, acao, status, mensagem)
                VALUES (%s, %s, %s, %s, %s, 0, %s, 'erro', %s)
            """, (contrato_id, usuario_id, tipo_base, target_table, filename, action, error_msg))
        except Exception:
            pass

        return {
            "success": False,
            "message": error_msg,
            "total_lines": 0
        }
