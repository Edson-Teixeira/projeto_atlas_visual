import os
from app import create_app
from app.config import Config

app = create_app()

if __name__ == '__main__':
    print(f"🚀 Iniciando Atlas em http://0.0.0.0:{Config.PORT}")
    app.run(host='0.0.0.0', port=Config.PORT, debug=Config.DEBUG)
