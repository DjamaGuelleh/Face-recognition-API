import os
import logging
from flask import Flask, jsonify
from flask_cors import CORS

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app(config_class='config.Config'):
    """Création et configuration de l'application Flask"""
    
    # Initialiser l'application Flask
    app = Flask(__name__)
    
    # Charger la configuration
    app.config.from_object(config_class)
    
    # Activer CORS pour permettre les requêtes cross-origin
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Initialiser la base de données
    from models.database import init_db
    init_db(app)
    
    # Initialiser le stockage vectoriel
    from models.vector_store import VectorStore
    vector_store = VectorStore(
        app.config['CHROMA_DB_DIR'],
        app.config['CHROMA_COLLECTION']
    )
    
    # Initialiser le service de reconnaissance faciale
    from services.face_service import FaceService
    face_service = FaceService(
        model_name=app.config['INSIGHTFACE_MODEL']
    )
    
    # Initialiser le service de gestion des personnes
    from services.person_service import PersonService
    person_service = PersonService(
        vector_store=vector_store,
        face_service=face_service,
        upload_folder=app.config['UPLOAD_FOLDER']
    )
    
    # Rendre les services accessibles dans l'application
    app.vector_store = vector_store
    app.face_service = face_service
    app.person_service = person_service
    
    # Enregistrer les routes
    from routes import init_routes
    init_routes(app)
    
    # Route par défaut
    @app.route('/')
    def index():
        return jsonify({
            "message": "API de reconnaissance faciale",
            "version": "1.0.0"
        })
    
    # Gestionnaire d'erreur pour les routes non trouvées
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Route non trouvée"}), 404
    
    # Gestionnaire d'erreur général
    @app.errorhandler(Exception)
    def handle_exception(error):
        logger.error(f"Erreur non gérée: {error}")
        return jsonify({"error": "Erreur interne du serveur"}), 500
    
    return app

if __name__ == '__main__':
    app = create_app()
    # Récupérer le port depuis les variables d'environnement ou utiliser 5000 par défaut
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=app.config['DEBUG'])