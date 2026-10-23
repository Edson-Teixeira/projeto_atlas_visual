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

    # 1. Contratos padrão
    contratos = [
        ("brk_fiscalizacao", "BRK Fiscalização", "brk_fiscalizacao", "brk_fisca_secundaria", "brk_irregularidades", "data"),
        ("brk_hidrometro", "BRK Hidrômetro", "brk_hidrometro", None, None, "data"),
        ("brk_pav_comer", "BRK Pav. Comercial", "brk_pav_comer", None, None, "data"),
        ("brk_pav_opera", "BRK Pav. Operacional", "brk_pav_opera", None, None, "data")
    ]

    for codigo, nome, tab_prin, tab_sec, tab_ter, col_data in contratos:
        existe = query_one("SELECT id FROM atlas_contratos WHERE codigo = %s", (codigo,))
        if not existe:
            execute("""
                INSERT INTO atlas_contratos (codigo, nome_exibicao, tabela_principal, tabela_secundaria, tabela_terciaria, coluna_data)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (codigo, nome, tab_prin, tab_sec, tab_ter, col_data))
            print(f"Contrato criado: {nome} ({codigo})")
        else:
            execute("""
                UPDATE atlas_contratos 
                SET tabela_principal = %s, tabela_secundaria = %s, tabela_terciaria = %s
                WHERE codigo = %s
            """, (tab_prin, tab_sec, tab_ter, codigo))
            print(f"Contrato atualizado: {nome} ({codigo})")

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

    # 3. Serviços e Valores padrão para BRK Fiscalização e BRK Hidrômetro
    c_fisc = query_one("SELECT id FROM atlas_contratos WHERE codigo = 'brk_fiscalizacao'")
    if c_fisc:
        servicos_fisc = [
            ('Corte', 112.90),
            ('Hidrômetro', 200.14),
            ('Fiscalização', 108.72),
            ('Religação', 84.29),
            ('Regularização', 100.91),
            ('Recomposição', 75.00),
            ('Troca de Padrão', 135.50),
            ('Vistoria Técnica', 65.00),
            ('Lacração', 55.00),
            ('Outros', 45.00)
        ]
        for s, v in servicos_fisc:
            execute("""
                INSERT INTO atlas_servicos_valores (contrato_id, tipo_servico, valor_servico)
                VALUES (%s, %s, %s)
                ON CONFLICT (contrato_id, tipo_servico) DO UPDATE SET valor_servico = EXCLUDED.valor_servico;
            """, (c_fisc['id'], s, v))

    c_hidro = query_one("SELECT id FROM atlas_contratos WHERE codigo = 'brk_hidrometro'")
    if c_hidro:
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
                INSERT INTO atlas_servicos_valores (contrato_id, tipo_servico, valor_servico)
                VALUES (%s, %s, %s)
                ON CONFLICT (contrato_id, tipo_servico) DO UPDATE SET valor_servico = EXCLUDED.valor_servico;
            """, (c_hidro['id'], s, v))

    print("\nInicialização concluída com sucesso!")

if __name__ == "__main__":
    init_database()
