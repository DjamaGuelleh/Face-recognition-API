from flask import Blueprint, request, jsonify, current_app
import logging
import os

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

@api.route('/persons/<person_id>', methods=['DELETE'])
def delete_person(person_id):
    """Endpoint pour supprimer une personne"""
    try:
        person_service = current_app.person_service
        result = person_service.delete_person(person_id)
        
        if not result:
            return jsonify({"error": "Personne non trouvée ou impossible à supprimer"}), 404
            
        return jsonify({"success": True, "message": "Personne supprimée avec succès"}), 200
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de la personne: {e}")
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