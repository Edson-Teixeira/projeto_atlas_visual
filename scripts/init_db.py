import os
import sys
from pathlib import Path
from werkzeug.security import generate_password_hash

# Garante importação do módulo app
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.db import get_db, execute, query_one

def init_database():
    print("Iniciando verificação e criação das tabelas de controle no PostgreSQL...")
    
    schema_path = ROOT_DIR / "app" / "schema.sql"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
    print("Schema executado com sucesso!")

    # Garante flexibilidade em brk_fiscalizacao (campos opcionais sem constraints restritivas)
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE brk_fiscalizacao DROP CONSTRAINT IF EXISTS pk_brk_fiscalizacao_os_status;")
                cur.execute("ALTER TABLE brk_fiscalizacao ALTER COLUMN ordem_servico DROP NOT NULL;")
                cur.execute("ALTER TABLE brk_fiscalizacao ALTER COLUMN status_atividade DROP NOT NULL;")
                cur.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name = 'brk_fiscalizacao' AND column_name = 'id'
                        ) THEN
                            ALTER TABLE brk_fiscalizacao ADD COLUMN id BIGSERIAL PRIMARY KEY;
                        END IF;
                    END $$;
                """)
                cur.execute("CREATE INDEX IF NOT EXISTS idx_brk_fiscalizacao_os_status ON brk_fiscalizacao(ordem_servico, status_atividade);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_brk_fiscalizacao_data ON brk_fiscalizacao(data);")
    except Exception as e:
        print(f"Aviso migração brk_fiscalizacao: {e}")

    # 1. Contratos padrão
    contratos = [
        ("brk_fiscalizacao", "BRK Fiscalização", "brk_fiscalizacao", "brk_fisca_secundaria", "brk_irregularidades", "brk_fisca_valores", "data"),
        ("brk_hidrometro", "BRK Hidrômetro", "brk_hidrometro", None, None, "brk_hidro_valores", "data"),
        ("brk_pav_comer", "BRK Pav. Comercial", "brk_pav_comer", None, None, None, "data"),
        ("brk_pav_opera", "BRK Pav. Operacional", "brk_pav_opera", None, None, None, "data")
    ]

    for codigo, nome, tab_prin, tab_sec, tab_ter, tab_val, col_data in contratos:
        existe = query_one("SELECT id FROM atlas_contratos WHERE codigo = %s", (codigo,))
        if not existe:
            execute("""
                INSERT INTO atlas_contratos (codigo, nome_exibicao, tabela_principal, tabela_secundaria, tabela_terciaria, tabela_valores, coluna_data)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (codigo, nome, tab_prin, tab_sec, tab_ter, tab_val, col_data))
            print(f"Contrato criado: {nome} ({codigo})")
        else:
            print(f"Contrato já configurado: {nome} ({codigo}) - preservando configurações.")

    # 2. Usuários padrão
    usuarios = [
        # (nome, username, senha, contrato_codigo, is_admin)
        ("Administrador Atlas", "admin", "admin123", None, True),
        ("Operador Fiscalização 1", "fiscalizacao", "fiscalizacao123", "brk_fiscalizacao", False),
        ("Operador Fiscalização 2", "fiscalizacao2", "fiscalizacao123", "brk_fiscalizacao", False),
        ("Operador Hidrômetro", "hidrometro", "hidrometro123", "brk_hidrometro", False),
    ]

    for nome, username, senha, contrato_codigo, is_admin in usuarios:
        contrato_id = None
        if contrato_codigo:
            c = query_one("SELECT id FROM atlas_contratos WHERE codigo = %s", (contrato_codigo,))
            if c:
                contrato_id = c["id"]

        existe_u = query_one("SELECT id FROM atlas_usuarios WHERE username = %s", (username,))
        if not existe_u:
            p_hash = generate_password_hash(senha)
            execute("""
                INSERT INTO atlas_usuarios (nome, username, password_hash, contrato_id, is_admin)
                VALUES (%s, %s, %s, %s, %s)
            """, (nome, username, p_hash, contrato_id, is_admin))
            print(f"Usuário criado: {username} (Contrato: {contrato_codigo or 'Admin'})")
        else:
            print(f"Usuário já existe: {username}")

    # 3. Serviços e Valores padrão para tabelas dedicadas: brk_fisca_valores e brk_hidro_valores
    # REGRA DE PROTEÇÃO: Preserva 100% dos dados customizados existentes.
    # Só insere valores padrão se a tabela estiver completamente vazia (primeira inicialização do sistema).
    count_fisc = query_one("SELECT COUNT(*) as c FROM brk_fisca_valores")
    if not count_fisc or count_fisc['c'] == 0:
        servicos_fisc = [
            ('Corte', 112.90),
            ('Fiscalização', 108.72),
            ('Hidrômetro', 200.14),
            ('Lacração', 55.00),
            ('Outros', 45.00),
            ('Recomposição', 75.00),
            ('Regularização', 100.91),
            ('Religação', 84.29),
            ('Troca de Padrão', 135.50),
            ('Troca Expressa', 180.00),
            ('Vistoria Especial', 250.50),
            ('Vistoria Técnica', 65.00)
        ]
        for s, v in servicos_fisc:
            execute("""
                INSERT INTO brk_fisca_valores (tipo_servico, valor_servico)
                VALUES (%s, %s)
                ON CONFLICT (tipo_servico) DO NOTHING;
            """, (s, v))
        print("Tabela brk_fisca_valores populada com valores iniciais padrão.")
    else:
        print(f"Tabela brk_fisca_valores já possui {count_fisc['c']} registros. Preservando valores e customizações existentes.")

    count_hidro = query_one("SELECT COUNT(*) as c FROM brk_hidro_valores")
    if not count_hidro or count_hidro['c'] == 0:
        servicos_hidro = [
            ('Aferição de Hidrômetro', 95.50),
            ('Instalação de Hidrômetro', 185.00),
            ('Lacração de Hidrômetro', 70.00),
            ('Manutenção de Ramal', 120.00),
            ('Outros Serviços Hidrometria', 50.00),
            ('Padronização de Cavalete', 160.00),
            ('Remanejamento de Cavalete', 175.00),
            ('Substituição de Hidrômetro', 145.00),
            ('Supressão a Pedido', 90.00),
            ('Troca por Defeito / Parado', 140.00),
            ('Troca por Idade / Obsoleto', 130.00),
            ('Vistoria de Consumo', 80.00)
        ]
        for s, v in servicos_hidro:
            execute("""
                INSERT INTO brk_hidro_valores (tipo_servico, valor_servico)
                VALUES (%s, %s)
                ON CONFLICT (tipo_servico) DO NOTHING;
            """, (s, v))
        print("Tabela brk_hidro_valores populada com valores iniciais padrão.")
    else:
        print(f"Tabela brk_hidro_valores já possui {count_hidro['c']} registros. Preservando valores e customizações existentes.")

    print("\nInicialização concluída com sucesso!")

if __name__ == "__main__":
    init_database()
