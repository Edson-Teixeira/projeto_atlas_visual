# Atlas - Gestão & Importação Multi-Tenant

Sistema web com interface moderna (*Dark-First*) desenvolvido em **Python (Flask)**, **PostgreSQL** e **Pandas**, projetado para permitir que múltiplos operadores realizem a carga e importação diária de dados dos seus respectivos contratos operacionais.

---

## 🚀 Funcionalidades Principais

1. **Autenticação e Isolamento Multi-Tenant por Contrato:**
   * Cada usuário logado é vinculado a um contrato específico (ex: `brk_fiscalizacao`, `brk_hidrometro`).
   * Usuários só conseguem visualizar dados e enviar arquivos para o seu respectivo contrato.
   * Suporte a múltiplos usuários para um mesmo contrato.
   * Acesso de Administrador com permissão de alternar dinamicamente entre contratos.

2. **Carga Inteligente de Arquivos (CSV + Excel):**
   * **Detecção Automática de Delimitadores e Encodings:** Lê arquivos `.csv` com separadores (`;`, `,` ou `\t`) e encodings comuns (`utf-8`, `latin-1`).
   * **Suporte Completo a Planilhas:** Aceita arquivos `.xlsx` e `.xls`.
   * **Normalização Automática de Colunas:** Remove acentos e caracteres especiais para corresponder ao schema PostgreSQL.

3. **Suporte a Base Principal e Base Secundária:**
   * **Base Principal:** Tabela padrão do contrato (ex: `brk_fiscalizacao`).
   * **Base Secundária:** Exibida condicionalmente apenas para os contratos que possuem tabela secundária configurada (ex: `brk_fisca_secundaria`).

4. **Idempotência Diária (Proteção Anti-Duplicidade):**
   * Opção padrão de **substituição da mesma data**: caso um arquivo do mesmo dia seja enviado novamente, os registros anteriores daquela data são removidos antes da inserção, prevenindo linhas duplicadas no Power BI.
   * Opção alternativa de **Append** direto.

5. **Tabela de Tipos de Serviço & Valores (BRK Fiscalização e BRK Hidrômetro):**
   * **Layout Dividido em 2 Colunas:** Lado esquerdo com as áreas operacionais de carga e histórico; lado direito com a tabela de serviços e valores unitários.
   * **Exportação Rápida:** Botão para exportar a tabela atual em CSV com delimitador `;` e codificação compatível com Excel.
   * **Substituição Completa da Tabela:** Permite enviar uma planilha com as colunas `tipo_servico` e `valor_servico`, substituindo integralmente a tabela anterior no banco caso haja correções necessárias.
   * **Busca Instantânea:** Filtro em tempo real no próprio navegador.

6. **Auditoria e Histórico Completo:**
   * Todas as importações registram: Operador, Data/Hora, Arquivo, Tabela de Destino, Quantidade de Linhas e Status.

---

## 📋 Credenciais Padrão (Ambiente de Testes)

| Usuário | Senha | Perfil | Contrato Associado |
| :--- | :--- | :--- | :--- |
| **`admin`** | `admin123` | Administrador | Todos (pode alternar) |
| **`fiscalizacao`** | `fiscalizacao123` | Operador 1 | BRK Fiscalização (Base Principal + Secundária) |
| **`fiscalizacao2`** | `fiscalizacao123` | Operador 2 | BRK Fiscalização (Base Principal + Secundária) |
| **`hidrometro`** | `hidrometro123` | Operador | BRK Hidrômetro (Apenas Base Principal) |

---

## 🛠️ Instalação e Execução

### Opção A: Via Docker / Dockge (Recomendado no Umbrel)

O projeto já inclui `Dockerfile` e `docker-compose.yml` otimizados para produção com Gunicorn.

```bash
# 1. Entre na pasta do projeto clonado
cd projeto_atlas_visual

# 2. Crie ou configure seu arquivo .env (se necessário ajustar IP do Postgres)
cp .env.example .env

# 3. Suba o container com build automático
docker compose up -d --build
```

Acesse no seu navegador: **`http://<IP_DO_SEU_UMBREL>:5000`**

#### No Dockge (Interface Web):
1. O Dockge detectará automaticamente a stack `projeto_atlas_visual` ou `api_cifra`.
2. Se quiser subir pelo painel do Dockge, basta clicar em **Deploy / Start**.
3. As variáveis de conexão com o PostgreSQL podem ser editadas diretamente no editor do Dockge se o banco estiver em outro host ou porta.

---

### Opção B: Execução Local (Python venv)

```bash
# 1. Ativar o ambiente virtual
source .venv/bin/activate

# 2. Instalar dependências (se necessário)
pip install -r requirements.txt

# 3. Inicializar as tabelas no PostgreSQL (apenas primeira execução)
python scripts/init_db.py

# 4. Executar o servidor Flask
python run.py
```

Acesse no navegador: **`http://localhost:5000`**

---

## 📂 Estrutura do Projeto

```text
projeto_atlas_sistema/
├── app/
│   ├── __init__.py           # Fábrica da aplicação Flask e filtros Jinja
│   ├── auth.py               # Autenticação, sessão e controle de acesso
│   ├── config.py             # Configurações carregadas do .env
│   ├── db.py                 # Pool de conexões psycopg2
│   ├── importer.py           # Leitura e carga inteligente de CSV e XLSX
│   ├── routes.py             # Rotas do painel e endpoints de importação
│   ├── schema.sql            # Definição das tabelas de controle no Postgres
│   ├── static/
│   │   ├── css/style.css     # Design System moderno Dark-First
│   │   └── js/app.js         # Tema Dark/Light e Drag & Drop
│   └── templates/
│       ├── base.html         # Template mestre com topbar e branding
│       ├── login.html        # Página 1: Login moderno com iluminação radial
│       └── dashboard.html    # Página 2: Painel de controle e uploads
├── scripts/
│   └── init_db.py            # Script de inicialização e dados iniciais
├── .env.example              # Modelo de variáveis de ambiente
├── .gitignore                # Arquivos ignorados no Git
├── REFERENCIA_ESTETICA.md    # Especificação do design system de referência
├── requirements.txt          # Dependências do projeto
├── run.py                    # Ponto de entrada da aplicação
└── README.md                 # Documentação do sistema
```
