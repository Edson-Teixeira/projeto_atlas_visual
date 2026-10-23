import os
from flask import Flask, send_from_directory, render_template, make_response
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

    # Headers de Segurança HTTP (Blindagem contra inspeção e ataques)
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        # Oculta detalhes do servidor web
        response.headers['Server'] = 'Atlas'
        return response

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

    @app.template_filter('safe_err')
    def safe_err_filter(val):
        if not val:
            return 'Erro no processamento'
        s = str(val)
        # Sanitização defensiva contra vazamento de IPs, portas e detalhes técnicos
        if any(w in s.lower() for w in ('detail:', 'relation', 'connection to server', 'violates', 'traceback', 'psycopg2', 'select ', 'insert ', 'password')):
            return 'Erro no processamento dos dados do arquivo enviado'
        return s[:120]

    # Rota dedicada para favicon.ico
    @app.route('/favicon.ico')
    def favicon():
        return send_from_directory(
            os.path.join(app.root_path, 'static'),
            'favicon.ico',
            mimetype='image/vnd.microsoft.icon'
        )

    # Handlers para erros HTTP sem vazamento de stacktrace ou dados internos
    @app.errorhandler(404)
    def not_found(e):
        return render_template('base.html', user=None, contrato=None), 404

    @app.errorhandler(500)
    def internal_error(e):
        return render_template('base.html', user=None, contrato=None), 500

    return app
