from flask_sqlalchemy import SQLAlchemy

# Instance de la base de données
db = SQLAlchemy()

def init_db(app):
    """Initialise la base de données avec l'application Flask"""
    with app.app_context():
        db.init_app(app)
        db.create_all()
        return db