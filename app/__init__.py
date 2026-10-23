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
        if isinstance(val, (datetime, date)):
            return val.strftime('%d/%m/%Y às %H:%M')
        try:
            dt = datetime.fromisoformat(str(val))
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

    return app
