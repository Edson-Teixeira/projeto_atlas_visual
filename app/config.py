import os
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env
load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "atlas_super_secret_dev_key_2026")
    
    # Configurações do PostgreSQL
    DB_HOST = os.getenv("DB_HOST", "192.168.1.102")
    DB_PORT = int(os.getenv("DB_PORT", "5432"))
    DB_USER = os.getenv("DB_USER", "admin")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "secretpassword")
    DB_NAME = os.getenv("DB_NAME", "cifra")
    DB_DEFAULT_SCHEMA = os.getenv("DB_DEFAULT_SCHEMA", "public")
    DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))

    # Servidor Flask
    PORT = int(os.getenv("PORT", "5000"))
    DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

    # Limites de upload (ex: até 100MB por arquivo)
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024
