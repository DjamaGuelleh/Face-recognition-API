from flask import Blueprint

# Cette fonction sera appelée par app.py pour enregistrer les routes
def init_routes(app):
    from .api import api
    from .dashboard import dashboard
    
    # Enregistrer les blueprints
    app.register_blueprint(api, url_prefix='/api')
    app.register_blueprint(dashboard, url_prefix='/api/dashboard')
    
    return app