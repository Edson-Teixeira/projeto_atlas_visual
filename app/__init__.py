from flask import Flask
from datetime import datetime, date
from app.config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Registro de Blueprints
    from app.auth import auth_bp
    from app.routes import main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    # Filtros úteis para Jinja2
    @app.template_filter('datetime_br')
    def datetime_br_filter(val):
        if not val:
            return '-'
        try:
            if isinstance(val, (datetime, date)):
                dt = val
            else:
                dt = datetime.fromisoformat(str(val))
            
            # Se tiver fuso horário explícito, converte para o horário de Brasília
            if isinstance(dt, datetime) and dt.tzinfo is not None:
                import zoneinfo
                dt = dt.astimezone(zoneinfo.ZoneInfo("America/Sao_Paulo"))
                
            return dt.strftime('%d/%m/%Y às %H:%M')
        except Exception:
            return str(val)

    @app.template_filter('date_br')
    def date_br_filter(val):
        if not val:
            return '-'
        if isinstance(val, (datetime, date)):
            return val.strftime('%d/%m/%Y')
        try:
            dt = datetime.fromisoformat(str(val))
            return dt.strftime('%d/%m/%Y')
        except Exception:
            return str(val)

    @app.template_filter('int_br')
    def int_br_filter(val):
        if val is None:
            return '-'
        try:
            return f"{int(val):,}".replace(",", ".")
        except Exception:
            return str(val)

    @app.template_filter('currency')
    def currency_filter(val):
        if val is None or val == '':
            return 'R$ 0,00'
        try:
            val_f = float(val)
            formatted = f"{val_f:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return f"R$ {formatted}"
        except Exception:
            return str(val)

    return app
