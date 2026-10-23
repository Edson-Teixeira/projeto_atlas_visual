import io
import unittest
import pandas as pd
from app import create_app
from app.db import get_db, query_one, execute
from app.importer import normalize_column_name, read_uploaded_file, process_and_import
from werkzeug.datastructures import FileStorage

class AtlasSistemaTestCase(unittest.TestCase):
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
            'username': 'fiscalizacao',
            'password': 'fiscalizacao123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"BRK Fiscaliza", response.data)
        # Deve exibir a Base Secundária pois fiscalização possui tabela secundária
        self.assertIn(b'id="card-upload-secundaria"', response.data)

    def test_login_valid_hidrometro_no_secondary(self):
        response = self.client.post('/login', data={
            'username': 'hidrometro',
            'password': 'hidrometro123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"BRK Hidr", response.data)
        # Hidrômetro NÃO deve exibir o card de Base Secundária
        self.assertNotIn(b'id="card-upload-secundaria"', response.data)

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
        user = query_one("SELECT id FROM atlas_usuarios WHERE username = 'fiscalizacao'")

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
        # Cria um arquivo Excel em memória
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
        user = query_one("SELECT id FROM atlas_usuarios WHERE username = 'fiscalizacao'")

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
        # Testa especificamente o formato MM/DD/YY (ex: 09/14/26) reportado pelo usuário
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
        user = query_one("SELECT id FROM atlas_usuarios WHERE username = 'fiscalizacao'")

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
        # Deve ter convertido perfeitamente para 2026-09-14
        self.assertEqual(res['date_reference'], '2026-09-14')

        # Verifica se gravou no Postgres como date correto (2026-09-14)
        registro = query_one("SELECT data FROM brk_fiscalizacao WHERE ordem_servico = 'OS-DATE-01'")
        self.assertIsNotNone(registro)
        self.assertEqual(str(registro['data']), '2026-09-14')

        # Limpa dados de teste
        execute("DELETE FROM brk_fiscalizacao WHERE ordem_servico IN ('OS-DATE-01', 'OS-DATE-02');")
        execute("DELETE FROM atlas_importacoes_log WHERE nome_arquivo = 'teste_data_mm_dd_yy.csv';")

    def test_services_table_visibility_and_export(self):
        # 1. Login com fiscalizacao (deve ter tabela de servicos)
        self.client.post('/login', data={'username': 'fiscalizacao', 'password': 'fiscalizacao123'})
        resp = self.client.get('/dashboard')
        self.assertIn(b"Tipos de Servi", resp.data)
        self.assertIn(b"dashboard-split-layout", resp.data)

        # 2. Exporta CSV de servicos
        contrato = query_one("SELECT id FROM atlas_contratos WHERE codigo = 'brk_fiscalizacao'")
        resp_export = self.client.get(f"/servicos/exportar/{contrato['id']}")
        self.assertEqual(resp_export.status_code, 200)
        self.assertEqual(resp_export.mimetype, 'text/csv')
        self.assertIn(b"tipo_servico;valor_servico", resp_export.data)
        self.assertIn(b"Corte", resp_export.data)

    def test_services_import_replace(self):
        # Login como fiscalizacao
        self.client.post('/login', data={'username': 'fiscalizacao', 'password': 'fiscalizacao123'})
        contrato = query_one("SELECT id FROM atlas_contratos WHERE codigo = 'brk_fiscalizacao'")

        # Envia novo CSV para substituir
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

        # Confirma que 'Corte' (antigo) foi removido na substituicao completa
        antigo = query_one("SELECT id FROM atlas_servicos_valores WHERE contrato_id = %s AND tipo_servico = 'Corte'", (contrato['id'],))
        self.assertIsNone(antigo)

        # Restaura os servicos padrao para fiscalizacao
        from scripts.init_db import init_database
        init_database()

if __name__ == '__main__':
    unittest.main()
