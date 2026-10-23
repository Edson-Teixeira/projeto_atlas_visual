-- ==============================================================================
-- Schema das Tabelas de Controle do Sistema Atlas
-- Banco: cifra | Schema: public
-- ==============================================================================

-- 1. Tabela de Contratos
CREATE TABLE IF NOT EXISTS atlas_contratos (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(60) UNIQUE NOT NULL,
    nome_exibicao VARCHAR(120) NOT NULL,
    tabela_principal VARCHAR(100) NOT NULL,
    tabela_secundaria VARCHAR(100),
    coluna_data VARCHAR(50) DEFAULT 'data',
    ativo BOOLEAN DEFAULT TRUE,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Tabela de Usuários vinculados a Contratos
CREATE TABLE IF NOT EXISTS atlas_usuarios (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    username VARCHAR(60) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    contrato_id INT REFERENCES atlas_contratos(id) ON DELETE SET NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    ativo BOOLEAN DEFAULT TRUE,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Tabela de Auditoria e Logs de Importação
CREATE TABLE IF NOT EXISTS atlas_importacoes_log (
    id SERIAL PRIMARY KEY,
    contrato_id INT REFERENCES atlas_contratos(id) ON DELETE CASCADE,
    usuario_id INT REFERENCES atlas_usuarios(id) ON DELETE SET NULL,
    tipo_base VARCHAR(20) NOT NULL, -- 'principal' ou 'secundaria'
    tabela_destino VARCHAR(100) NOT NULL,
    nome_arquivo VARCHAR(255) NOT NULL,
    total_linhas INT DEFAULT 0,
    data_referencia DATE,
    acao VARCHAR(40) DEFAULT 'append', -- 'append' ou 'substituir_data'
    status VARCHAR(30) DEFAULT 'sucesso', -- 'sucesso', 'erro', 'aviso'
    mensagem TEXT,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Exemplo de tabela secundária para BRK Fiscalização (se ainda não existir)
CREATE TABLE IF NOT EXISTS brk_fisca_secundaria (
    id SERIAL PRIMARY KEY,
    recurso VARCHAR(255),
    data DATE,
    cdc_matricula BIGINT,
    ordem_servico VARCHAR(255),
    status_atividade VARCHAR(255),
    observacoes TEXT,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para garantir consultas rápidas no painel
CREATE INDEX IF NOT EXISTS idx_atlas_importacoes_contrato ON atlas_importacoes_log(contrato_id, criado_em DESC);
CREATE INDEX IF NOT EXISTS idx_atlas_usuarios_username ON atlas_usuarios(username);
