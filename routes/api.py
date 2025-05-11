import base64
import os
from flask import Blueprint, request, jsonify, current_app, send_file
import logging

from models.person import Person
from models.database import db

logger = logging.getLogger(__name__)

# Créer le Blueprint
api = Blueprint('api', __name__)

@api.route('/persons', methods=['POST'])
def create_person():
    """
    Endpoint pour créer une nouvelle personne
    Formulaire attendu:
    - name: Nom de la personne
    - age: Âge de la personne
    - gender: Genre de la personne
    - nationality: Nationalité de la personne
    - photo: Image du visage de la personne
    """
    try:
        # Vérifier la présence de tous les champs requis
        if 'photo' not in request.files:
            return jsonify({"error": "Aucune photo fournie"}), 400
            
        photo = request.files['photo']
        if photo.filename == '':
            return jsonify({"error": "Nom de fichier vide"}), 400
            
        # Vérifier les champs du formulaire
        name = request.form.get('name')
        age_str = request.form.get('age')
        gender = request.form.get('gender')
        nationality = request.form.get('nationality')
        
        if not all([name, age_str, gender, nationality]):
            return jsonify({"error": "Tous les champs sont obligatoires"}), 400
        
        try:
            age = int(age_str)
            if age <= 0 or age > 120:
                return jsonify({"error": "L'âge doit être compris entre 1 et 120"}), 400
        except ValueError:
            return jsonify({"error": "L'âge doit être un nombre entier"}), 400
            
        # Créer la personne
        person_service = current_app.person_service
        person = person_service.create_person(name, age, gender, nationality, photo)
        
        if not person:
            return jsonify({"error": "Impossible de créer la personne. Vérifiez que l'image contient un visage."}), 400
            
        return jsonify({"success": True, "person": person.to_dict()}), 201
        
    except Exception as e:
        logger.error(f"Erreur lors de la création de la personne: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

@api.route('/persons', methods=['GET'])
def get_all_persons():
    """Endpoint pour récupérer toutes les personnes"""
    try:
        person_service = current_app.person_service
        persons = person_service.get_all_persons()
        return jsonify({"persons": persons}), 200
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des personnes: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

@api.route('/persons/<person_id>', methods=['GET'])
def get_person(person_id):
    """Endpoint pour récupérer une personne par son ID"""
    try:
        person_service = current_app.person_service
        person = person_service.get_person_by_id(person_id)
        
        if not person:
            return jsonify({"error": "Personne non trouvée"}), 404
            
        return jsonify({"person": person}), 200
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la personne: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

@api.route('/identify', methods=['POST'])
def identify_person():
    """
    Endpoint pour identifier une personne à partir d'une photo
    Renvoie l'image et les informations de la personne si trouvée
    """
    try:
        if 'photo' not in request.files:
            return jsonify({"error": "Aucune photo fournie"}), 400
            
        photo = request.files['photo']
        if photo.filename == '':
            return jsonify({"error": "Nom de fichier vide"}), 400
            
        # Récupérer threshold optionnel
        threshold = request.form.get('threshold')
        if threshold:
            try:
                threshold = float(threshold)
                if threshold < 0 or threshold > 1:
                    return jsonify({"error": "Le seuil doit être compris entre 0 et 1"}), 400
            except ValueError:
                return jsonify({"error": "Le seuil doit être un nombre entre 0 et 1"}), 400
        else:
            threshold = current_app.config['SIMILARITY_THRESHOLD']
            
        # Rechercher la personne
        person_service = current_app.person_service
        result = person_service.find_person_by_face(photo, threshold)
        
        # Si une personne est trouvée, récupérer son image
        if result.get("found", False) and "person" in result:
            person_data = result["person"]
            photo_path = person_data.get("photo_path")
            
            if photo_path and os.path.exists(photo_path):
                # Déterminer le type MIME de l'image
                file_ext = os.path.splitext(photo_path)[1].lower()
                mime_type = {
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.png': 'image/png',
                    '.gif': 'image/gif'
                }.get(file_ext, 'application/octet-stream')
                
                # Lire l'image et l'encoder en base64
                with open(photo_path, "rb") as image_file:
                    encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
                    
                # Ajouter l'image encodée et son type MIME au résultat
                result["person"]["photo_data"] = encoded_image
                result["person"]["photo_mime_type"] = mime_type
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Erreur lors de l'identification de la personne: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

@api.route('/process', methods=['POST'])
def process_image():
    """
    Endpoint pour traiter une image et extraire les embeddings
    Compatible avec votre route existante
    """
    try:
        if 'image' not in request.files:
            return jsonify({"error": "Aucune image fournie"}), 400
            
        image_file = request.files['image']
        if image_file.filename == '':
            return jsonify({"error": "Nom de fichier vide"}), 400
            
        # Traiter l'image
        face_service = current_app.face_service
        image_bytes = image_file.read()
        results = face_service.process_image_bytes(image_bytes)
        
        if "error" in results:
            return jsonify(results), 400
            
        return jsonify(results), 200
        
    except Exception as e:
        logger.error(f"Erreur lors du traitement de l'image: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500
    
@api.route('/debug/embeddings', methods=['GET'])
def debug_embeddings():
    """Route de débogage pour vérifier les embeddings"""
    try:
        vector_store = current_app.vector_store
        # Récupérer tous les embeddings (10 premiers)
        results = vector_store.collection.query(
            query_embeddings=[[0] * 512],  # Un vecteur zéro pour récupérer tous les éléments
            n_results=10,
            include=["metadatas", "documents", "distances", "embeddings"]
        )
        
        return jsonify({"embeddings": results}), 200
    except Exception as e:
        logger.error(f"Erreur lors du débogage: {e}")
        return jsonify({"error": f"Erreur interne du serveur: {str(e)}"}), 500

@api.route('/debug/embedding/<vector_id>', methods=['GET'])
def debug_specific_embedding(vector_id):
    """Route de débogage pour vérifier un embedding spécifique"""
    try:
        vector_store = current_app.vector_store
        
        # Récupérer l'embedding spécifique
        results = vector_store.collection.get(
            ids=[vector_id],
            include=["embeddings", "metadatas"]
        )
        
        if not results['ids']:
            return jsonify({"error": "Embedding non trouvé"}), 404
            
        # Vérifier si l'embedding existe
        embedding = results.get('embeddings', [None])[0]
        embedding_info = {
            "exists": embedding is not None,
            "length": len(embedding) if embedding is not None else 0,
            "metadata": results.get('metadatas', [None])[0]
        }
        
        return jsonify({"embedding_info": embedding_info}), 200
    except Exception as e:
        logger.error(f"Erreur lors du débogage: {e}")
        return jsonify({"error": f"Erreur interne du serveur: {str(e)}"}), 500
    
@api.route('/admin/clear-all', methods=['POST'])
def clear_all_data():
    """Supprime toutes les données des bases de données"""
    try:
        # Vérifier l'authentification si nécessaire
        
        # 1. Récupérer toutes les personnes
        persons = Person.query.all()
        
        # 2. Supprimer les images
        for person in persons:
            if os.path.exists(person.photo_path):
                try:
                    os.remove(person.photo_path)
                    logger.info(f"Image supprimée: {person.photo_path}")
                except Exception as e:
                    logger.error(f"Erreur lors de la suppression de l'image {person.photo_path}: {e}")
        
        # 3. Supprimer ChromaDB de manière sécurisée
        chroma_dir = current_app.config['CHROMA_DB_DIR']
        collection_name = current_app.config['CHROMA_COLLECTION']
        
        # D'abord, essayer de supprimer la collection via l'API
        try:
            # Essayer de supprimer la collection via l'API
            current_app.vector_store.client.delete_collection(collection_name)
            logger.info(f"Collection ChromaDB '{collection_name}' supprimée via API")
        except Exception as e:
            logger.warning(f"Impossible de supprimer la collection via API: {e}")
        
        # Recréer l'instance VectorStore
        try:
            # Fermer toutes les connexions potentielles
            del current_app.vector_store
            import gc
            gc.collect()  # Forcer le garbage collector
            
            # Recréer le VectorStore
            from models.vector_store import VectorStore
            try:
                # Supprimer physiquement le répertoire
                import shutil
                if os.path.exists(chroma_dir):
                    shutil.rmtree(chroma_dir)
                    logger.info(f"Répertoire ChromaDB supprimé: {chroma_dir}")
                os.makedirs(chroma_dir, exist_ok=True)
            except Exception as e:
                logger.error(f"Erreur lors de la suppression du répertoire ChromaDB: {e}")
            
            # Réinitialiser l'instance
            current_app.vector_store = VectorStore(
                db_directory=chroma_dir,
                collection_name=collection_name
            )
            logger.info("Instance VectorStore réinitialisée")
        except Exception as e:
            logger.error(f"Erreur lors de la réinitialisation de VectorStore: {e}")
            return jsonify({"error": f"Erreur Vector Store: {str(e)}"}), 500
        
        # 4. Vider la table SQLite
        try:
            Person.query.delete()
            db.session.commit()
            logger.info("Table Person vidée avec succès")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erreur lors de la suppression des données SQLite: {e}")
            return jsonify({"error": f"Erreur SQLite: {str(e)}"}), 500
        
        return jsonify({"success": True, "message": "Toutes les données ont été supprimées"}), 200
        
    except Exception as e:
        logger.error(f"Erreur générale lors de la suppression des données: {e}")
        return jsonify({"error": f"Erreur interne du serveur: {str(e)}"}), 500