# app.py - Version Optimisée
import os
import logging
from flask import Flask, jsonify
from flask_cors import CORS
from sqlalchemy import text

# Configuration du logging optimisé
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/app.log') if os.path.exists('logs') else logging.NullHandler()
    ]
)
logger = logging.getLogger(__name__)

def create_app(config_class='config.Config'):
    """Création et configuration optimisée de l'application Flask"""
    
    # Initialiser l'application Flask
    app = Flask(__name__)
    
    # Charger la configuration
    app.config.from_object(config_class)
    
    # Activer CORS avec configuration optimisée
    CORS(app, resources={
        r"/api/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "max_age": 3600  # Cache preflight requests for 1 hour
        }
    })
    
    # Initialiser la base de données
    from models.database import init_db
    init_db(app)
    
    # Vérifier la santé de la base de données au démarrage
    try:
        with app.app_context():
            from models.person import Person
            # Test simple de connectivité
            Person.query.limit(1).all()
            logger.info("Connexion à la base de données PostgreSQL établie")
    except Exception as e:
        logger.error(f"Erreur de connexion à la base de données: {e}")
        raise
    
    # Initialiser le stockage vectoriel avec vérification
    try:
        from models.vector_store import VectorStore
        vector_store = VectorStore(
            app.config['CHROMA_DB_DIR'],
            app.config['CHROMA_COLLECTION']
        )
        
        # Test de connectivité ChromaDB
        collection_count = vector_store.collection.count()
        logger.info(f"ChromaDB connecté - {collection_count} embeddings trouvés")
        
    except Exception as e:
        logger.error(f"Erreur d'initialisation de ChromaDB: {e}")
        raise
    
    # Initialiser le service de reconnaissance faciale
    try:
        from services.face_service import FaceService
        face_service = FaceService(
            model_name=app.config['INSIGHTFACE_MODEL']
        )
        logger.info(f"Service de reconnaissance faciale initialisé: {app.config['INSIGHTFACE_MODEL']}")
        
    except Exception as e:
        logger.error(f"Erreur d'initialisation du service de reconnaissance faciale: {e}")
        raise
    
    # Initialiser le service de gestion des personnes OPTIMISÉ
    try:
        from services.person_service import PersonService
        person_service = PersonService(
            vector_store=vector_store,
            face_service=face_service,
            upload_folder=app.config['UPLOAD_FOLDER'],
            fingerprints_folder=app.config['FINGERPRINTS_FOLDER']
        )
        logger.info("Service de gestion des personnes optimisé initialisé")
        
    except Exception as e:
        logger.error(f"Erreur d'initialisation du service des personnes: {e}")
        raise
    
    # Rendre les services accessibles dans l'application
    app.vector_store = vector_store
    app.face_service = face_service
    app.person_service = person_service
    
    # Configuration des dossiers
    _ensure_directories_exist(app)
    
    # Enregistrer les routes optimisées
    from routes import init_routes
    init_routes(app)
    
    # Routes de base optimisées
    @app.route('/')
    def index():
        return jsonify({
            "message": "API de reconnaissance faciale et de stockage d'empreintes digitales",
            "version": "2.0.0-optimized",
            "features": [
                "Reconnaissance faciale avancée",
                "Stockage d'empreintes digitales", 
                "Pagination optimisée",
                "Filtres avancés",
                "Recherche textuelle",
                "Analytics et statistiques",
                "Index de base de données optimisés"
            ],
            "endpoints": {
                "health": "/api/admin/health",
                "stats": "/api/stats",
                "search": "/api/search",
                "persons": "/api/persons",
                "identify": "/api/identify"
            }
        })
    
    @app.route('/health')
    def health_check():
        """Endpoint de vérification de santé optimisé"""
        try:
            # Test rapide de la base de données
            from models.person import Person
            db_count = Person.query.count()
            
            # Test rapide de ChromaDB
            chroma_count = vector_store.collection.count()
            
            # Vérifier la cohérence
            sync_status = "synced" if db_count == chroma_count else "out_of_sync"
            
            return jsonify({
                "status": "healthy",
                "timestamp": app.config.get('start_time', 'unknown'),
                "database": {
                    "status": "connected",
                    "persons_count": db_count
                },
                "chromadb": {
                    "status": "connected", 
                    "embeddings_count": chroma_count
                },
                "sync_status": sync_status,
                "version": "2.0.0-optimized"
            }), 200
            
        except Exception as e:
            logger.error(f"Erreur lors du health check: {e}")
            return jsonify({
                "status": "unhealthy",
                "error": str(e),
                "timestamp": app.config.get('start_time', 'unknown')
            }), 503
    
    @app.route('/api/info')
    def api_info():
        """Informations détaillées sur l'API"""
        return jsonify({
            "api_version": "2.0.0-optimized",
            "database_optimization": {
                "indexes_created": True,
                "pagination_support": True,
                "advanced_filtering": True,
                "search_capabilities": True
            },
            "performance_features": [
                "Index partiels pour empreintes",
                "Requêtes avec projection SQL", 
                "Chargement différé des BLOB",
                "Pagination intelligente",
                "Cache des métadonnées"
            ],
            "endpoints": {
                "persons": {
                    "GET /api/persons": "Liste paginée avec filtres",
                    "POST /api/persons": "Création de personne",
                    "GET /api/persons/{id}": "Détails d'une personne",
                    "DELETE /api/persons/{id}": "Suppression"
                },
                "search": {
                    "GET /api/search": "Recherche textuelle avancée",
                    "POST /api/filter": "Filtrage avec critères multiples"
                },
                "media": {
                    "GET /api/persons/{id}/photo": "Photo de la personne",
                    "GET /api/persons/{id}/fingerprint/{type}": "Empreintes digitales"
                },
                "recognition": {
                    "POST /api/identify": "Identification faciale",
                    "POST /api/process": "Traitement d'image"
                },
                "analytics": {
                    "GET /api/stats": "Statistiques optimisées",
                    "GET /api/analytics/duplicates": "Analyse des doublons"
                },
                "admin": {
                    "GET /api/admin/health": "Rapport de santé détaillé",
                    "POST /api/admin/cleanup-embeddings": "Nettoyage des embeddings",
                    "POST /api/admin/rebuild-embedding/{id}": "Reconstruction d'embedding"
                }
            },
            "query_parameters": {
                "pagination": ["page", "limit"],
                "sorting": ["sort_by", "sort_order"],
                "filtering": ["gender", "nationality", "age_min", "age_max", "has_fingerprints", "created_after", "created_before"],
                "inclusion": ["include_images", "include_fingerprints", "summary_only"],
                "search": ["q", "fields"]
            }
        })
    
    # Gestionnaires d'erreur optimisés
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            "error": "Route non trouvée",
            "available_endpoints": [
                "/api/persons",
                "/api/search", 
                "/api/identify",
                "/api/stats",
                "/health",
                "/api/info"
            ]
        }), 404
    
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            "error": "Requête invalide",
            "message": "Vérifiez les paramètres de votre requête",
            "documentation": "/api/info"
        }), 400
    
    @app.errorhandler(413)
    def request_entity_too_large(error):
        return jsonify({
            "error": "Fichier trop volumineux",
            "max_size": f"{app.config['MAX_CONTENT_LENGTH'] // (1024*1024)}MB"
        }), 413
    
    @app.errorhandler(429)
    def too_many_requests(error):
        return jsonify({
            "error": "Trop de requêtes",
            "message": "Veuillez ralentir vos requêtes"
        }), 429
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Erreur interne: {error}")
        return jsonify({
            "error": "Erreur interne du serveur",
            "support": "Consultez les logs pour plus de détails"
        }), 500
    
    @app.errorhandler(503)
    def service_unavailable(error):
        return jsonify({
            "error": "Service temporairement indisponible",
            "retry_after": "60"
        }), 503
    
    # Middleware de performance
    @app.before_request
    def before_request():
        """Middleware exécuté avant chaque requête"""
        import time
        from flask import g, request
        
        g.start_time = time.time()
        
        # Log des requêtes importantes
        if request.method in ['POST', 'DELETE'] or 'admin' in request.path:
            logger.info(f"{request.method} {request.path} - Start")
    
    @app.after_request
    def after_request(response):
        """Middleware exécuté après chaque requête"""
        import time
        from flask import g, request
        
        # Calcul du temps de réponse
        if hasattr(g, 'start_time'):
            duration = time.time() - g.start_time
            
            # Headers de performance
            response.headers['X-Response-Time'] = f"{duration:.3f}s"
            response.headers['X-API-Version'] = "2.0.0-optimized"
            
            # Log des requêtes lentes
            if duration > 1.0:  # Plus d'1 seconde
                logger.warning(f"Requête lente: {request.method} {request.path} - {duration:.3f}s")
            
            # Log des requêtes importantes
            if request.method in ['POST', 'DELETE'] or 'admin' in request.path:
                logger.info(f"{request.method} {request.path} - {response.status_code} - {duration:.3f}s")
        
        # Headers de sécurité
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        return response
    
    # Enregistrer l'heure de démarrage
    import time
    app.config['start_time'] = time.time()
    
    # Rapport de démarrage
    logger.info("="*50)
    logger.info("API de Reconnaissance Faciale - Version Optimisée")
    logger.info("="*50)
    logger.info(f"Configuration: {config_class}")
    logger.info(f"Debug mode: {app.config['DEBUG']}")
    logger.info(f"Base de données: PostgreSQL")
    logger.info(f"ChromaDB: {app.config['CHROMA_DB_DIR']}")
    logger.info(f"Modèle InsightFace: {app.config['INSIGHTFACE_MODEL']}")
    logger.info(f"Seuil de similarité: {app.config['SIMILARITY_THRESHOLD']}")
    logger.info("Features optimisées activées:")
    logger.info("  ✓ Index de base de données")
    logger.info("  ✓ Pagination intelligente") 
    logger.info("  ✓ Filtres avancés")
    logger.info("  ✓ Recherche textuelle")
    logger.info("  ✓ Chargement différé des BLOB")
    logger.info("  ✓ Requêtes avec projection")
    logger.info("  ✓ Analytics et maintenance")
    logger.info("="*50)
    
    return app

def _ensure_directories_exist(app):
    """Crée les dossiers nécessaires s'ils n'existent pas"""
    directories = [
        app.config['UPLOAD_FOLDER'],
        app.config['FINGERPRINTS_FOLDER'],
        app.config['CHROMA_DB_DIR'],
        app.config.get('LOG_DIR', 'logs')
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            logger.info(f"Dossier créé: {directory}")

def run_optimizations():
    """
    Fonction pour exécuter les optimisations de base de données au démarrage
    À appeler une seule fois après le déploiement
    """
    try:
        from models.database import db
        from models.person import Person
        
        logger.info("Exécution des optimisations de base de données...")
        
        # Analyser les tables pour mettre à jour les statistiques
        db.session.execute(text("ANALYZE person;"))
        db.session.commit()
        
        logger.info("Statistiques de base de données mises à jour")
        
        # Vérifier l'existence des index
        index_check = db.session.execute(text("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'person' 
            AND indexname LIKE 'idx_%'
        """)).fetchall()
        
        logger.info(f"Index détectés: {len(index_check)}")
        for idx in index_check:
            logger.info(f"  - {idx[0]}")
            
    except Exception as e:
        logger.warning(f"Impossible d'exécuter les optimisations: {e}")

if __name__ == '__main__':
    # Créer l'application
    app = create_app()
    
    # Exécuter les optimisations si demandé
    if os.environ.get('RUN_OPTIMIZATIONS', 'false').lower() == 'true':
        with app.app_context():
            run_optimizations()
    
    # Configuration du serveur
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))
    debug = app.config['DEBUG']
    
    logger.info(f"Démarrage du serveur sur {host}:{port}")
    logger.info(f"Mode debug: {debug}")
    
    if debug:
        logger.warning("Mode debug activé - Ne pas utiliser en production")
    
    # Démarrer le serveur
    app.run(
        host=host, 
        port=port, 
        debug=debug,
        threaded=True,  # Support multi-thread pour de meilleures performances
        use_reloader=debug  # Rechargement automatique seulement en debug
    )