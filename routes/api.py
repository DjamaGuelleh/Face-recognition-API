# routes/api.py
from flask import Blueprint, request, jsonify, current_app, send_file
import logging
import os
import base64

from models.person import Person

logger = logging.getLogger(__name__)

# Créer le Blueprint
api = Blueprint('api', __name__)

@api.route('/persons', methods=['POST'])
def create_person():
    """
    Endpoint pour créer une nouvelle personne avec empreintes digitales
    Formulaire attendu:
    - name: Nom de la personne
    - age: Âge de la personne
    - gender: Genre de la personne
    - nationality: Nationalité de la personne
    - photo: Image du visage de la personne
    - fingerprint_right: (Optionnel) Image des empreintes de la main droite
    - fingerprint_left: (Optionnel) Image des empreintes de la main gauche
    - fingerprint_thumbs: (Optionnel) Image des empreintes des pouces
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
        
        # Récupérer les fichiers d'empreintes (optionnels)
        fingerprint_right = request.files.get('fingerprint_right')
        fingerprint_left = request.files.get('fingerprint_left')
        fingerprint_thumbs = request.files.get('fingerprint_thumbs')
        
        # Vérifier que les empreintes ont des noms de fichiers valides
        if fingerprint_right and fingerprint_right.filename == '':
            fingerprint_right = None
            
        if fingerprint_left and fingerprint_left.filename == '':
            fingerprint_left = None
            
        if fingerprint_thumbs and fingerprint_thumbs.filename == '':
            fingerprint_thumbs = None
        
        # Créer la personne
        person_service = current_app.person_service
        person = person_service.create_person(
            name, age, gender, nationality, photo,
            fingerprint_right, fingerprint_left, fingerprint_thumbs
        )
        
        if not person:
            return jsonify({"error": "Impossible de créer la personne. Vérifiez que l'image contient un visage."}), 400
            
        # Préparer les URLs pour les empreintes
        person_dict = person.to_dict()
        
        if person.fingerprint_right_path:
            person_dict["fingerprint_right_url"] = f"/api/persons/{person.id}/fingerprint/right"
        
        if person.fingerprint_left_path:
            person_dict["fingerprint_left_url"] = f"/api/persons/{person.id}/fingerprint/left"
        
        if person.fingerprint_thumbs_path:
            person_dict["fingerprint_thumbs_url"] = f"/api/persons/{person.id}/fingerprint/thumbs"
            
        return jsonify({"success": True, "person": person_dict}), 201
        
    except Exception as e:
        logger.error(f"Erreur lors de la création de la personne: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

@api.route('/persons/<person_id>/fingerprint/<type>', methods=['GET'])
def get_fingerprint(person_id, type):
    """
    Endpoint pour récupérer une image d'empreinte digitale
    
    Args:
        person_id: ID de la personne
        type: Type d'empreinte (right, left, thumbs)
    """
    try:
        person_service = current_app.person_service
        person = Person.query.filter_by(id=person_id).first()
        
        if not person:
            return jsonify({"error": "Personne non trouvée"}), 404
        
        # Déterminer le chemin selon le type
        if type == 'right':
            path = person.fingerprint_right_path
        elif type == 'left':
            path = person.fingerprint_left_path
        elif type == 'thumbs':
            path = person.fingerprint_thumbs_path
        else:
            return jsonify({"error": "Type d'empreinte invalide"}), 400
        
        if not path or not os.path.exists(path):
            return jsonify({"error": "Empreinte non trouvée"}), 404
        
        # Déterminer le type MIME
        file_ext = os.path.splitext(path)[1].lower()
        mime_type = {
            '.bmp': 'image/bmp',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png'
        }.get(file_ext, 'application/octet-stream')
        
        # Renvoyer l'image
        return send_file(path, mimetype=mime_type)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'empreinte: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

@api.route('/identify', methods=['POST'])
def identify_person():
    """
    Endpoint pour identifier une personne à partir d'une photo
    Nécessite une image avec un visage
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

# Routes existantes (get_all_persons, get_person, delete_person, process_image, etc.)# routes/api.py
from flask import Blueprint, request, jsonify, current_app, send_file
import logging
import os
import base64

logger = logging.getLogger(__name__)

# Créer le Blueprint
api = Blueprint('api', __name__)

@api.route('/persons', methods=['POST'])
def create_person():
    """
    Endpoint pour créer une nouvelle personne avec empreintes digitales
    Formulaire attendu:
    - name: Nom de la personne
    - age: Âge de la personne
    - gender: Genre de la personne
    - nationality: Nationalité de la personne
    - photo: Image du visage de la personne
    - fingerprint_right: (Optionnel) Image des empreintes de la main droite
    - fingerprint_left: (Optionnel) Image des empreintes de la main gauche
    - fingerprint_thumbs: (Optionnel) Image des empreintes des pouces
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
        
        # Récupérer les fichiers d'empreintes (optionnels)
        fingerprint_right = request.files.get('fingerprint_right')
        fingerprint_left = request.files.get('fingerprint_left')
        fingerprint_thumbs = request.files.get('fingerprint_thumbs')
        
        # Vérifier que les empreintes ont des noms de fichiers valides
        if fingerprint_right and fingerprint_right.filename == '':
            fingerprint_right = None
            
        if fingerprint_left and fingerprint_left.filename == '':
            fingerprint_left = None
            
        if fingerprint_thumbs and fingerprint_thumbs.filename == '':
            fingerprint_thumbs = None
        
        # Créer la personne
        person_service = current_app.person_service
        person = person_service.create_person(
            name, age, gender, nationality, photo,
            fingerprint_right, fingerprint_left, fingerprint_thumbs
        )
        
        if not person:
            return jsonify({"error": "Impossible de créer la personne. Vérifiez que l'image contient un visage."}), 400
            
        # Préparer les URLs pour les empreintes
        person_dict = person.to_dict()
        
        if person.fingerprint_right_path:
            person_dict["fingerprint_right_url"] = f"/api/persons/{person.id}/fingerprint/right"
        
        if person.fingerprint_left_path:
            person_dict["fingerprint_left_url"] = f"/api/persons/{person.id}/fingerprint/left"
        
        if person.fingerprint_thumbs_path:
            person_dict["fingerprint_thumbs_url"] = f"/api/persons/{person.id}/fingerprint/thumbs"
            
        return jsonify({"success": True, "person": person_dict}), 201
        
    except Exception as e:
        logger.error(f"Erreur lors de la création de la personne: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

@api.route('/persons/<person_id>/fingerprint/<type>', methods=['GET'])
def get_fingerprint(person_id, type):
    """
    Endpoint pour récupérer une image d'empreinte digitale
    
    Args:
        person_id: ID de la personne
        type: Type d'empreinte (right, left, thumbs)
    """
    try:
        person_service = current_app.person_service
        person = Person.query.filter_by(id=person_id).first()
        
        if not person:
            return jsonify({"error": "Personne non trouvée"}), 404
        
        # Déterminer le chemin selon le type
        if type == 'right':
            path = person.fingerprint_right_path
        elif type == 'left':
            path = person.fingerprint_left_path
        elif type == 'thumbs':
            path = person.fingerprint_thumbs_path
        else:
            return jsonify({"error": "Type d'empreinte invalide"}), 400
        
        if not path or not os.path.exists(path):
            return jsonify({"error": "Empreinte non trouvée"}), 404
        
        # Déterminer le type MIME
        file_ext = os.path.splitext(path)[1].lower()
        mime_type = {
            '.bmp': 'image/bmp',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png'
        }.get(file_ext, 'application/octet-stream')
        
        # Renvoyer l'image
        return send_file(path, mimetype=mime_type)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'empreinte: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

@api.route('/identify', methods=['POST'])
def identify_person():
    """
    Endpoint pour identifier une personne à partir d'une photo
    Nécessite une image avec un visage
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

# Routes existantes (get_all_persons, get_person, delete_person, process_image, etc.)