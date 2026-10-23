import io
import unittest
import pandas as pd
from werkzeug.security import generate_password_hash
from app import create_app
from app.db import get_db, query_one, execute
from app.importer import normalize_column_name, read_uploaded_file, process_and_import
from werkzeug.datastructures import FileStorage

class AtlasSistemaTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Garante usuários isolados para testes automatizados
        execute("""
            INSERT INTO atlas_usuarios (nome, username, password_hash, contrato_id, is_admin, ativo)
            VALUES 
                ('Test Admin', 'test_admin', %s, NULL, TRUE, TRUE),
                ('Test Fisc', 'test_fiscalizacao', %s, 1, FALSE, TRUE),
                ('Test Hidro', 'test_hidrometro', %s, 2, FALSE, TRUE)
            ON CONFLICT (username) DO UPDATE 
            SET password_hash = EXCLUDED.password_hash, contrato_id = EXCLUDED.contrato_id, is_admin = EXCLUDED.is_admin, ativo = TRUE;
        """, (
            generate_password_hash('test_admin123'),
            generate_password_hash('test_fisc123'),
            generate_password_hash('test_hidro123')
        ))

    @classmethod
    def tearDownClass(cls):
        execute("DELETE FROM atlas_usuarios WHERE username IN ('test_admin', 'test_fiscalizacao', 'test_hidrometro');")

    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

    def test_normalize_column_name(self):
        self.assertEqual(normalize_column_name("Data"), "data")
        self.assertEqual(normalize_column_name("CDC / Matrícula"), "cdc_matricula")
        self.assertEqual(normalize_column_name("Ordem de Serviço"), "ordem_de_servico")
        self.assertEqual(normalize_column_name("Área de Trabalho"), "area_de_trabalho")
        self.assertEqual(normalize_column_name("Nº TOI"), "no_toi")
        self.assertEqual(normalize_column_name("OBSERVAÇÕES"), "observacoes")

    def test_login_page_renders(self):
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Atlas Sistema", response.data)
        self.assertIn(b"Entrar no Sistema", response.data)

    def test_login_invalid_credentials(self):
        response = self.client.post('/login', data={
            'username': 'invalido',
            'password': 'errada'
        }, follow_redirects=True)
        self.assertIn(b"Usu\xc3\xa1rio ou senha incorretos", response.data)

    def test_login_valid_fiscalizacao(self):
        response = self.client.post('/login', data={
            'username': 'test_fiscalizacao',
            'password': 'test_fisc123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"BRK Fiscaliza", response.data)
        self.assertIn(b'id="card-upload-secundaria"', response.data)
        self.assertIn(b'id="card-upload-terciaria"', response.data)

    def test_login_valid_hidrometro_no_secondary(self):
        response = self.client.post('/login', data={
            'username': 'test_hidrometro',
            'password': 'test_hidro123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"BRK Hidr", response.data)
        # Hidrômetro NÃO deve exibir o card de Base Secundária nem Terciária
        self.assertNotIn(b'id="card-upload-secundaria"', response.data)
        self.assertNotIn(b'id="card-upload-terciaria"', response.data)

    def test_csv_import_simulation(self):
        csv_data = (
            "recurso;data;cdc_matricula;ordem_servico;status_atividade\n"
            "EQP_01;2026-10-22;123456;OS-9901;Concluida\n"
            "EQP_02;2026-10-22;654321;OS-9902;Pendente\n"
        )
        file_storage = FileStorage(
            stream=io.BytesIO(csv_data.encode('utf-8')),
            filename="teste_importacao.csv",
            content_type="text/csv"
        )

        contrato = query_one("SELECT id FROM atlas_contratos WHERE codigo = 'brk_fiscalizacao'")
        user = query_one("SELECT id FROM atlas_usuarios WHERE username = 'test_fiscalizacao'")

        res = process_and_import(
            file_storage=file_storage,
            filename="teste_importacao.csv",
            target_table="brk_fiscalizacao",
            contrato_id=contrato['id'],
            usuario_id=user['id'],
            tipo_base='principal',
            action='substituir_data',
            date_col='data'
        )

        self.assertTrue(res['success'])
        self.assertEqual(res['total_lines'], 2)
        self.assertEqual(res['date_reference'], '2026-10-22')

        # Limpa dados de teste
        execute("DELETE FROM brk_fiscalizacao WHERE ordem_servico IN ('OS-9901', 'OS-9902');")
        execute("DELETE FROM atlas_importacoes_log WHERE nome_arquivo = 'teste_importacao.csv';")

    def test_xlsx_import_simulation(self):
        df = pd.DataFrame([
            {"recurso": "EQP_XLS", "data": "2026-10-22", "cdc_matricula": 789101, "ordem_servico": "OS-XLS-01", "status_atividade": "Concluida"}
        ])
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False, engine='openpyxl')
        excel_buffer.seek(0)

        file_storage = FileStorage(
            stream=excel_buffer,
            filename="teste_planilha.xlsx",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        contrato = query_one("SELECT id FROM atlas_contratos WHERE codigo = 'brk_fiscalizacao'")
        user = query_one("SELECT id FROM atlas_usuarios WHERE username = 'test_fiscalizacao'")

        res = process_and_import(
            file_storage=file_storage,
            filename="teste_planilha.xlsx",
            target_table="brk_fiscalizacao",
            contrato_id=contrato['id'],
            usuario_id=user['id'],
            tipo_base='principal',
            action='substituir_data',
            date_col='data'
        )

        self.assertTrue(res['success'])
        self.assertEqual(res['total_lines'], 1)

        # Limpa dados de teste
        execute("DELETE FROM brk_fiscalizacao WHERE ordem_servico = 'OS-XLS-01';")
        execute("DELETE FROM atlas_importacoes_log WHERE nome_arquivo = 'teste_planilha.xlsx';")

    def test_date_format_mm_dd_yy(self):
        csv_data = (
            "recurso;Data;cdc_matricula;ordem_servico;status_atividade\n"
            "EQP_DATE;09/14/26;445566;OS-DATE-01;Concluida\n"
            "EQP_DATE;09/14/26;445567;OS-DATE-02;Concluida\n"
        )
        file_storage = FileStorage(
            stream=io.BytesIO(csv_data.encode('utf-8')),
            filename="teste_data_mm_dd_yy.csv",
            content_type="text/csv"
        )

        contrato = query_one("SELECT id FROM atlas_contratos WHERE codigo = 'brk_fiscalizacao'")
        user = query_one("SELECT id FROM atlas_usuarios WHERE username = 'test_fiscalizacao'")

        res = process_and_import(
            file_storage=file_storage,
            filename="teste_data_mm_dd_yy.csv",
            target_table="brk_fiscalizacao",
            contrato_id=contrato['id'],
            usuario_id=user['id'],
            tipo_base='principal',
            action='substituir_data',
            date_col='data'
        )

        self.assertTrue(res['success'])
        self.assertEqual(res['total_lines'], 2)
        self.assertEqual(res['date_reference'], '2026-09-14')

        registro = query_one("SELECT data FROM brk_fiscalizacao WHERE ordem_servico = 'OS-DATE-01'")
        self.assertIsNotNone(registro)
        self.assertEqual(str(registro['data']), '2026-09-14')

        execute("DELETE FROM brk_fiscalizacao WHERE ordem_servico IN ('OS-DATE-01', 'OS-DATE-02');")
        execute("DELETE FROM atlas_importacoes_log WHERE nome_arquivo = 'teste_data_mm_dd_yy.csv';")

    def test_services_table_visibility_and_export(self):
        # 1. Fiscalização -> brk_fisca_valores
        self.client.post('/login', data={'username': 'test_fiscalizacao', 'password': 'test_fisc123'})
        resp = self.client.get('/dashboard')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Tipos de Servi", resp.data)
        self.assertIn(b"brk_fisca_valores", resp.data)

        contrato = query_one("SELECT id FROM atlas_contratos WHERE codigo = 'brk_fiscalizacao'")
        resp_export = self.client.get(f"/servicos/exportar/{contrato['id']}")
        self.assertEqual(resp_export.status_code, 200)
        self.assertEqual(resp_export.mimetype, 'text/csv')
        self.assertIn(b"tipo_servico;valor_servico", resp_export.data)

        # 2. Hidrômetro -> brk_hidro_valores
        self.client.get('/logout')
        self.client.post('/login', data={'username': 'test_hidrometro', 'password': 'test_hidro123'})
        resp_h = self.client.get('/dashboard')
        self.assertEqual(resp_h.status_code, 200)
        self.assertIn(b"Tipos de Servi", resp_h.data)
        self.assertIn(b"brk_hidro_valores", resp_h.data)

        contrato_h = query_one("SELECT id FROM atlas_contratos WHERE codigo = 'brk_hidrometro'")
        resp_export_h = self.client.get(f"/servicos/exportar/{contrato_h['id']}")
        self.assertEqual(resp_export_h.status_code, 200)
        self.assertEqual(resp_export_h.mimetype, 'text/csv')
        self.assertIn(b"tipo_servico;valor_servico", resp_export_h.data)

    def test_services_import_replace(self):
        self.client.post('/login', data={'username': 'test_fiscalizacao', 'password': 'test_fisc123'})
        contrato = query_one("SELECT id FROM atlas_contratos WHERE codigo = 'brk_fiscalizacao'")

        novo_csv = (
            "tipo_servico;valor_servico\n"
            "Vistoria Especial;250,50\n"
            "Troca Expressa;180.00\n"
        )
        data = {
            'file': (io.BytesIO(novo_csv.encode('utf-8')), 'novos_servicos.csv')
        }
        resp = self.client.post(
            f"/servicos/importar/{contrato['id']}",
            data=data,
            content_type='multipart/form-data',
            follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Vistoria Especial", resp.data)
        self.assertIn(b"Troca Expressa", resp.data)

        # Confirma que foi gravado na tabela física brk_fisca_valores
        row = query_one("SELECT valor_servico FROM brk_fisca_valores WHERE tipo_servico = 'Vistoria Especial'")
        self.assertIsNotNone(row)
        self.assertEqual(float(row['valor_servico']), 250.50)

        # Restaura os servicos padrao para fiscalizacao
        from scripts.init_db import init_database
        init_database()

    def test_admin_dashboard_renders_contracts_status_and_no_upload_box(self):
        self.client.post('/login', data={'username': 'test_admin', 'password': 'test_admin123'})
        resp = self.client.get('/dashboard')
        self.assertEqual(resp.status_code, 200)

        self.assertIn(b"Status Operacional dos Contratos", resp.data)
        self.assertIn(b"contracts-status-grid", resp.data)
        self.assertIn(b"BRK Fiscaliza", resp.data)
        self.assertIn(b"admin-sidebar", resp.data)
        self.assertIn(b"Usu\xc3\xa1rios & Senhas", resp.data)
        self.assertIn(b"Hist\xc3\xb3rico de Envios", resp.data)

        # NÃO deve conter campos de upload nem tabela de valores na tela principal do admin
        self.assertNotIn(b'id="card-upload-principal"', resp.data)
        self.assertNotIn(b'id="card-upload-secundaria"', resp.data)
        self.assertNotIn(b'id="card-upload-terciaria"', resp.data)

    def test_admin_usuarios_management(self):
        self.client.post('/login', data={'username': 'test_admin', 'password': 'test_admin123'})
        resp = self.client.get('/admin/usuarios')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Gest\xc3\xa3o de Usu\xc3\xa1rios & Senhas", resp.data)

        contrato = query_one("SELECT id FROM atlas_contratos WHERE codigo = 'brk_fiscalizacao'")
        resp_create = self.client.post('/admin/usuarios/novo', data={
            'nome': 'Operador Teste Automatizado',
            'username': 'op_teste_aut',
            'password': 'senha_antiga_123',
            'contrato_id': str(contrato['id']),
            'is_admin': ''
        }, follow_redirects=True)
        self.assertEqual(resp_create.status_code, 200)
        self.assertIn(b"op_teste_aut", resp_create.data)

        novo_user = query_one("SELECT id FROM atlas_usuarios WHERE username = 'op_teste_aut'")
        self.assertIsNotNone(novo_user)

        self.client.get('/logout')
        resp_login_ok = self.client.post('/login', data={'username': 'op_teste_aut', 'password': 'senha_antiga_123'}, follow_redirects=True)
        self.assertEqual(resp_login_ok.status_code, 200)
        self.assertIn(b"BRK Fiscaliza", resp_login_ok.data)

        self.client.get('/logout')
        self.client.post('/login', data={'username': 'test_admin', 'password': 'test_admin123'})
        resp_pwd = self.client.post(f"/admin/usuarios/{novo_user['id']}/senha", data={
            'nova_senha': 'senha_super_nova_999'
        }, follow_redirects=True)
        self.assertEqual(resp_pwd.status_code, 200)
        self.assertIn(b"alterada com sucesso", resp_pwd.data)

        self.client.get('/logout')
        resp_new_login = self.client.post('/login', data={'username': 'op_teste_aut', 'password': 'senha_super_nova_999'}, follow_redirects=True)
        self.assertEqual(resp_new_login.status_code, 200)
        self.assertIn(b"BRK Fiscaliza", resp_new_login.data)

        execute("DELETE FROM atlas_usuarios WHERE username = 'op_teste_aut';")

    def test_admin_historico_page(self):
        self.client.post('/login', data={'username': 'test_admin', 'password': 'test_admin123'})
        resp = self.client.get('/admin/historico')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Hist\xc3\xb3rico Consolidado de Envios", resp.data)
        self.assertIn(b"Registro de Importa\xc3\xa7\xc3\xb5es", resp.data)

    def test_admin_ver_contrato_preview(self):
        self.client.post('/login', data={'username': 'test_admin', 'password': 'test_admin123'})
        contrato = query_one("SELECT id FROM atlas_contratos WHERE codigo = 'brk_fiscalizacao'")
        resp = self.client.get(f"/admin/contrato/{contrato['id']}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Vis\xc3\xa3o do Administrador", resp.data)
        self.assertIn(b"Voltar ao Painel Admin", resp.data)
        self.assertIn(b'id="card-upload-principal"', resp.data)
        self.assertIn(b'id="card-upload-terciaria"', resp.data)

    def test_irregularidades_cards_visibility(self):
        # Fiscalização deve exibir os 3 cards: Principal, Diagnóstico e Irregularidades
        self.client.post('/login', data={'username': 'test_fiscalizacao', 'password': 'test_fisc123'})
        resp_fisc = self.client.get('/dashboard')
        self.assertEqual(resp_fisc.status_code, 200)
        self.assertIn(b'id="card-upload-principal"', resp_fisc.data)
        self.assertIn(b'id="card-upload-secundaria"', resp_fisc.data)
        self.assertIn(b'id="card-upload-terciaria"', resp_fisc.data)
        self.assertIn(b"Importar Irregularidades", resp_fisc.data)
        self.assertIn(b"brk_irregularidades", resp_fisc.data)

        # Hidrômetro NÃO deve exibir irregularidades nem secundária
        self.client.get('/logout')
        self.client.post('/login', data={'username': 'test_hidrometro', 'password': 'test_hidro123'})
        resp_hidro = self.client.get('/dashboard')
        self.assertEqual(resp_hidro.status_code, 200)
        self.assertIn(b'id="card-upload-principal"', resp_hidro.data)
        self.assertNotIn(b'id="card-upload-secundaria"', resp_hidro.data)
        self.assertNotIn(b'id="card-upload-terciaria"', resp_hidro.data)

    def test_irregularidades_import_process(self):
        self.client.post('/login', data={'username': 'test_fiscalizacao', 'password': 'test_fisc123'})
        contrato = query_one("SELECT id FROM atlas_contratos WHERE codigo = 'brk_fiscalizacao'")

        tsv_data = (
            "CDC\tOS\tEQUIPE\tDATA\tIRREGULARIDADE\tNº TOI\tOBSERVAÇÕES\n"
            "9594\t23-7301989\tRMM02PSF094T\t16/04/2026\tLigação direta\t64892\tFiscalizado no local\n"
            "44887\t23-7324933\tRMM02PSF098T\t17/04/2026\tLigação direta\t\tSem TOI emitido\n"
        )
        data = {
            'contrato_id': str(contrato['id']),
            'action': 'substituir_data',
            'file': (io.BytesIO(tsv_data.encode('utf-8')), 'irregularidades_abril.csv')
        }
        resp = self.client.post(
            '/importar/terciaria',
            data=data,
            content_type='multipart/form-data',
            follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"importado com sucesso", resp.data)

        row1 = query_one("SELECT * FROM brk_irregularidades WHERE os = '23-7301989'")
        self.assertIsNotNone(row1)
        self.assertEqual(row1['cdc'], 9594)
        self.assertEqual(row1['equipe'], 'RMM02PSF094T')
        self.assertEqual(str(row1['data']), '2026-04-16')
        self.assertEqual(row1['irregularidade'], 'Ligação direta')
        self.assertEqual(row1['no_toi'], '64892')

        row2 = query_one("SELECT * FROM brk_irregularidades WHERE os = '23-7324933'")
        self.assertIsNotNone(row2)
        self.assertEqual(row2['cdc'], 44887)
        self.assertEqual(str(row2['data']), '2026-04-17')
        self.assertIsNone(row2['no_toi'])

        execute("DELETE FROM brk_irregularidades WHERE os IN ('23-7301989', '23-7324933');")
        execute("DELETE FROM atlas_importacoes_log WHERE nome_arquivo = 'irregularidades_abril.csv';")

if __name__ == '__main__':
    unittest.main()
