# routes/api.py - Version Complètement Optimisée
from flask import Blueprint, request, jsonify, current_app, send_file
import logging
import os
import base64
import io
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_

from models.person import Person
from routes.dashboard import log_identification
from models.enums import RegionEnum
from models.database import db

logger = logging.getLogger(__name__)

# Créer le Blueprint
api = Blueprint('api', __name__)

# ========================
# ENDPOINTS CRUD OPTIMISÉS
# ========================

@api.route('/persons', methods=['POST'])
def create_person():
    """
    Endpoint pour créer une nouvelle personne avec empreintes digitales
    Version avec énumération des régions et défaut Djibouti
    """
    try:
        # Vérifier la présence de tous les champs requis
        if 'photo' not in request.files:
            return jsonify({"error": "Aucune photo fournie"}), 400
            
        photo = request.files['photo']
        if photo.filename == '':
            return jsonify({"error": "Nom de fichier vide"}), 400
            
        # Vérifier les champs du formulaire
        name = request.form.get('name', '').strip()
        age_str = request.form.get('age')
        gender = request.form.get('gender', '').strip()
        nationality = request.form.get('nationality', '').strip()
        region = request.form.get('region', '').strip()  # Optionnel maintenant
        
        # La région est optionnelle, Djibouti par défaut
        if not region:
            region = RegionEnum.get_default()
        
        if not all([name, age_str, gender, nationality]):
            return jsonify({"error": "Les champs nom, âge, genre et nationalité sont obligatoires"}), 400
        
        try:
            age = int(age_str)
            if age <= 0 or age > 120:
                return jsonify({"error": "L'âge doit être compris entre 1 et 120"}), 400
        except ValueError:
            return jsonify({"error": "L'âge doit être un nombre entier"}), 400
        
        # Validation du genre
        if gender not in ['Masculin', 'Féminin', 'Autre']:
            return jsonify({"error": "Le genre doit être 'Masculin', 'Féminin' ou 'Autre'"}), 400
        
        # Validation de la région avec énumération
        valid_regions = RegionEnum.get_values()
        if region not in valid_regions:
            return jsonify({
                "error": f"La région doit être l'une des suivantes: {', '.join(valid_regions)}",
                "valid_regions": valid_regions,
                "default_region": RegionEnum.get_default()
            }), 400
        
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
            name, age, gender, nationality, region, photo,
            fingerprint_right, fingerprint_left, fingerprint_thumbs
        )
        
        if not person:
            return jsonify({"error": "Impossible de créer la personne. Vérifiez que l'image contient un visage."}), 400
            
        # Retourner les informations de la personne créée
        person_dict = person.to_dict(include_image_data=False)
        
        # Ajouter les URLs des ressources
        person_dict["photo_url"] = f"/api/persons/{person.id}/photo"
        if person.fingerprint_right_data:
            person_dict["fingerprint_right_url"] = f"/api/persons/{person.id}/fingerprint/right"
        if person.fingerprint_left_data:
            person_dict["fingerprint_left_url"] = f"/api/persons/{person.id}/fingerprint/left"
        if person.fingerprint_thumbs_data:
            person_dict["fingerprint_thumbs_url"] = f"/api/persons/{person.id}/fingerprint/thumbs"
            
        return jsonify({"success": True, "person": person_dict}), 201
        
    except Exception as e:
        logger.error(f"Erreur lors de la création de la personne: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

# Mise à jour de routes/api.py - Endpoint GET /api/persons unifié

@api.route('/persons', methods=['GET'])
def get_all_persons():
    """
    Endpoint unifié pour récupérer ET rechercher les personnes
    
    Query parameters:
    === MODE RECHERCHE (avec paramètre 'q') ===
    - q: Terme de recherche (active le mode recherche)
    - search_fields: Champs à rechercher (name,nationality,region,gender) - défaut: name,nationality,region
    
    === MODE FILTRAGE (sans paramètre 'q') ===
    - region, gender, nationality: Filtres par valeurs exactes
    - age_min, age_max: Filtres d'âge
    - has_fingerprints: true/false
    - created_after, created_before: Filtres de date
    
    === PAGINATION ===
    - all: true/false - Récupérer TOUTES les données sans pagination (défaut: false)
    - page: Numéro de page (défaut: 1) - ignoré si all=true
    - limit: Éléments par page (défaut: 20, max: 100) - ignoré si all=true
    
    === COMMUN AUX DEUX MODES ===
    - sort_by: Champ de tri (défaut: created_at)
    - sort_order: Ordre de tri (défaut: desc)
    - include_images, include_fingerprints: Inclure les données binaires
    - summary_only: Mode ultra-rapide sans URLs
    """
    try:
        # NOUVEAU: Détection du mode recherche
        search_term = request.args.get('q', '').strip()
        
        # NOUVEAU: Mode sans pagination
        get_all = request.args.get('all', 'false').lower() in ('true', '1', 'yes')
        
        # Paramètres de pagination
        if get_all:
            page = 1
            limit = None  # Pas de limite
        else:
            page = request.args.get('page', 1, type=int)
            limit = request.args.get('limit', 20, type=int)
            limit = min(max(1, limit), 100)  # Limiter entre 1 et 100 uniquement si pas all=true
        
        # Paramètres communs
        include_images = request.args.get('include_images', 'false').lower() in ('true', '1', 'yes')
        include_fingerprints = request.args.get('include_fingerprints', 'false').lower() in ('true', '1', 'yes')
        summary_only = request.args.get('summary_only', 'false').lower() in ('true', '1', 'yes')
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        person_service = current_app.person_service
        
        # ===================================
        # MODE RECHERCHE (avec paramètre 'q')
        # ===================================
        if search_term:
            # Validation du terme de recherche
            if len(search_term) < 2:
                return jsonify({
                    "error": "Le terme de recherche doit contenir au moins 2 caractères",
                    "mode": "search"
                }), 400
            
            # Champs de recherche
            search_fields_param = request.args.get('search_fields', 'name,nationality,region')
            search_fields = [field.strip() for field in search_fields_param.split(',') if field.strip()]
            
            # Validation des champs de recherche
            valid_search_fields = ['name', 'nationality', 'gender', 'region']
            search_fields = [field for field in search_fields if field in valid_search_fields]
            
            if not search_fields:
                search_fields = ['name', 'nationality', 'region']
            
            # Appeler le service de recherche avec ou sans pagination
            if get_all:
                result = person_service.search_persons_all(
                    search_term=search_term,
                    search_fields=search_fields,
                    sort_by=sort_by,
                    sort_order=sort_order
                )
            else:
                result = person_service.search_persons(
                    search_term=search_term,
                    page=page,
                    limit=limit,
                    search_fields=search_fields
                )
            
            # Enrichir la réponse avec des métadonnées de recherche
            result.update({
                'mode': 'search',
                'search_query': search_term,
                'search_fields_used': search_fields,
                'available_search_fields': valid_search_fields,
                'pagination_disabled': get_all,
                'sort': {'by': 'relevance' if not get_all else sort_by, 'order': 'desc' if not get_all else sort_order}
            })
            
            # Ajouter les URLs pour les ressources si en mode non-summary
            if not summary_only:
                for person in result.get('persons', []):
                    person["photo_url"] = f"/api/persons/{person['id']}/photo"
                    if person.get("has_fingerprints"):
                        person["fingerprint_urls"] = {
                            "right": f"/api/persons/{person['id']}/fingerprint/right",
                            "left": f"/api/persons/{person['id']}/fingerprint/left", 
                            "thumbs": f"/api/persons/{person['id']}/fingerprint/thumbs"
                        }
            
            return jsonify(result), 200
        
        # ===================================
        # MODE FILTRAGE NORMAL (sans 'q')
        # ===================================
        
        # Construction des filtres (code existant)
        filters = {}
        if request.args.get('gender'):
            filters['gender'] = request.args.get('gender')
        if request.args.get('nationality'):
            filters['nationality'] = request.args.get('nationality')
        if request.args.get('region'):
            filters['region'] = request.args.get('region')
        if request.args.get('has_fingerprints'):
            filters['has_fingerprints'] = request.args.get('has_fingerprints').lower() in ('true', '1', 'yes')
        if request.args.get('age_min'):
            filters['age_min'] = int(request.args.get('age_min'))
        if request.args.get('age_max'):
            filters['age_max'] = int(request.args.get('age_max'))
        if request.args.get('age_group'):
            filters['age_group'] = request.args.get('age_group')
        if request.args.get('created_after'):
            filters['created_after'] = request.args.get('created_after')
        if request.args.get('created_before'):
            filters['created_before'] = request.args.get('created_before')
        
        # Choisir le mode approprié
        if get_all:
            # NOUVEAU: Mode sans pagination
            if summary_only:
                result = person_service.get_persons_summary_all(
                    filters=filters,
                    sort_by=sort_by,
                    sort_order=sort_order
                )
            else:
                result = person_service.get_all_persons_no_pagination(
                    include_images=include_images,
                    include_fingerprints=include_fingerprints,
                    filters=filters,
                    sort_by=sort_by,
                    sort_order=sort_order
                )
        else:
            # Mode paginé existant
            if summary_only:
                result = person_service.get_persons_summary_only(
                    page=page, 
                    limit=limit, 
                    filters=filters,
                    sort_by=sort_by,
                    sort_order=sort_order
                )
            else:
                result = person_service.get_all_persons_optimized(
                    page=page,
                    limit=limit,
                    include_images=include_images,
                    include_fingerprints=include_fingerprints,
                    filters=filters,
                    sort_by=sort_by,
                    sort_order=sort_order
                )
        
        # Ajouter les URLs pour les ressources si mode normal (non summary)
        if not summary_only and not get_all:
            for person in result.get('persons', []):
                if not include_images:
                    person["photo_url"] = f"/api/persons/{person['id']}/photo"
                if person.get("has_fingerprints") and not include_fingerprints:
                    person["fingerprint_urls"] = {
                        "right": f"/api/persons/{person['id']}/fingerprint/right",
                        "left": f"/api/persons/{person['id']}/fingerprint/left",
                        "thumbs": f"/api/persons/{person['id']}/fingerprint/thumbs"
                    }
        
        # Ajouter les métadonnées à la réponse
        result['mode'] = 'filter'
        result['pagination_disabled'] = get_all
        
        # Avertissement si trop de données demandées
        if get_all and result.get('total_count', 0) > 1000:
            result['warning'] = f"Récupération de {result['total_count']} enregistrements sans pagination. Considérez l'utilisation de la pagination pour de meilleures performances."
        
        return jsonify(result), 200
        
    except ValueError as e:
        return jsonify({"error": f"Paramètre invalide: {str(e)}"}), 400
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des personnes: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500


# ===================================
# OPTIONNEL: Garder l'ancien endpoint pour rétrocompatibilité
# ===================================

@api.route('/search', methods=['GET'])
def search_persons_legacy():
    """
    Endpoint de recherche dédié (gardé pour rétrocompatibilité)
    RECOMMANDATION: Utilisez plutôt GET /api/persons?q=... 
    """
    try:
        search_term = request.args.get('q', '').strip()
        if not search_term:
            return jsonify({
                "error": "Paramètre de recherche 'q' obligatoire",
                "recommendation": "Utilisez GET /api/persons?q=... pour la nouvelle API unifiée"
            }), 400
        
        # Rediriger vers l'endpoint unifié
        from flask import redirect, url_for
        
        # Construire les paramètres de redirection
        redirect_params = request.args.to_dict()
        
        # Note: Pour une vraie redirection, vous pourriez faire :
        # return redirect(url_for('api.get_all_persons', **redirect_params))
        
        # Ou appeler directement le service (plus simple)
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        search_fields_param = request.args.get('fields', 'name,nationality,region')
        search_fields = [field.strip() for field in search_fields_param.split(',') if field.strip()]
        
        person_service = current_app.person_service
        result = person_service.search_persons(
            search_term=search_term,
            page=page,
            limit=limit,
            search_fields=search_fields
        )
        
        # Ajouter une note de dépréciation
        result['deprecated'] = True
        result['message'] = "Cet endpoint est deprecated. Utilisez GET /api/persons?q=... à la place"
        result['new_endpoint'] = f"/api/persons?q={search_term}"
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Erreur lors de la recherche (legacy): {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

@api.route('/persons/with-fingerprints', methods=['GET'])
def get_persons_with_fingerprints():
    """Endpoint optimisé pour les personnes avec empreintes"""
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        include_images = request.args.get('include_images', 'false').lower() in ('true', '1', 'yes')
        include_fingerprints = request.args.get('include_fingerprints', 'true').lower() in ('true', '1', 'yes')
        summary_only = request.args.get('summary_only', 'false').lower() in ('true', '1', 'yes')
        
        person_service = current_app.person_service
        
        if summary_only:
            filters = {"has_fingerprints": True}
            result = person_service.get_persons_summary_only(
                page=page,
                limit=limit,
                filters=filters
            )
        else:
            result = person_service.get_persons_with_fingerprints_optimized(
                page=page,
                limit=limit,
                include_images=include_images,
                include_fingerprints=include_fingerprints
            )
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des personnes avec empreintes: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

@api.route('/persons/<person_id>', methods=['GET'])
def get_person(person_id):
    """
    Endpoint pour récupérer une personne par son ID
    
    Query parameters:
    - include_images: Si "true", inclut la photo de visage encodée en base64 (défaut: "true")
    - include_fingerprints: Si "true", inclut aussi les empreintes digitales (défaut: "false")
    """
    try:
        # Validation de l'UUID
        if not person_id or len(person_id) != 36:
            return jsonify({"error": "ID de personne invalide"}), 400
        
        # Paramètres pour inclure ou non les images et empreintes
        include_images = request.args.get('include_images', 'true').lower() in ('true', '1', 'yes')
        include_fingerprints = request.args.get('include_fingerprints', 'false').lower() in ('true', '1', 'yes')
        
        person_service = current_app.person_service
        person = person_service.get_person_by_id(
            person_id,
            include_images=include_images,
            include_fingerprints=include_fingerprints
        )
        
        if not person:
            return jsonify({"error": "Personne non trouvée"}), 404
            
        # Ajouter les URLs des ressources
        if not include_images:
            person["photo_url"] = f"/api/persons/{person_id}/photo"
        
        if person.get("has_fingerprints") and not include_fingerprints:
            person["fingerprint_urls"] = {
                "right": f"/api/persons/{person_id}/fingerprint/right",
                "left": f"/api/persons/{person_id}/fingerprint/left",
                "thumbs": f"/api/persons/{person_id}/fingerprint/thumbs"
            }
            
        return jsonify({"person": person}), 200
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la personne: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

@api.route('/persons/<person_id>', methods=['DELETE'])
def delete_person(person_id):
    """Endpoint pour supprimer une personne"""
    try:
        if not person_id or len(person_id) != 36:
            return jsonify({"error": "ID de personne invalide"}), 400
        
        person_service = current_app.person_service
        result = person_service.delete_person(person_id)
        
        if not result:
            return jsonify({"error": "Personne non trouvée ou impossible à supprimer"}), 404
            
        return jsonify({"success": True, "message": "Personne supprimée avec succès"}), 200
        
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de la personne: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

# ========================
# ENDPOINTS DE RESSOURCES MÉDIAS
# ========================

@api.route('/persons/<person_id>/photo', methods=['GET'])
def get_person_photo(person_id):
    """Endpoint optimisé pour récupérer la photo d'une personne"""
    try:
        if not person_id or len(person_id) != 36:
            return jsonify({"error": "ID de personne invalide"}), 400
        
        person_service = current_app.person_service
        photo_data, mime_type = person_service.get_person_photo(person_id)
        
        if not photo_data:
            return jsonify({"error": "Photo non trouvée"}), 404
        
        return send_file(
            io.BytesIO(photo_data),
            mimetype=mime_type,
            as_attachment=False,
            download_name=f"person_{person_id}_photo.jpg"
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la photo: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

@api.route('/persons/<person_id>/fingerprint/<fingerprint_type>', methods=['GET'])
def get_person_fingerprint(person_id, fingerprint_type):
    """
    Endpoint optimisé pour récupérer une empreinte digitale
    
    Args:
        person_id: ID de la personne
        fingerprint_type: Type d'empreinte (right, left, thumbs)
    """
    try:
        if not person_id or len(person_id) != 36:
            return jsonify({"error": "ID de personne invalide"}), 400
        
        if fingerprint_type not in ['right', 'left', 'thumbs']:
            return jsonify({"error": "Type d'empreinte invalide. Utilisez: right, left, thumbs"}), 400
        
        person_service = current_app.person_service
        fingerprint_data, mime_type = person_service.get_person_fingerprint(person_id, fingerprint_type)
        
        if not fingerprint_data:
            return jsonify({"error": "Empreinte non trouvée"}), 404
        
        return send_file(
            io.BytesIO(fingerprint_data),
            mimetype=mime_type,
            as_attachment=False,
            download_name=f"person_{person_id}_fingerprint_{fingerprint_type}.jpg"
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'empreinte: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

# ========================
# ENDPOINTS DE RECONNAISSANCE FACIALE
# ========================

@api.route('/identify', methods=['POST'])
def identify_person():
    """
    Endpoint optimisé pour identifier une personne à partir d'une photo
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
        
        # Enregistrer l'activité d'identification
        if result.get("found", False) and "person" in result:
            log_identification(
                person_id=result["person"]["id"],
                success=True,
                details={
                    "similarity": result.get("similarity", 0),
                    "detection_score": result.get("detection_score", 0),
                    "threshold_used": threshold
                }
            )
        else:
            log_identification(
                success=False,
                details={
                    "message": result.get("message", "Aucune correspondance trouvée"),
                    "threshold_used": threshold
                }
            )
       
        # Ajouter des URLs pour les ressources si trouvé
        if result.get("found", False) and "person" in result:
            person_data = result["person"]
            
            # Ajouter l'URL de la photo si pas déjà incluse en base64
            if not person_data.get("photo_data"):
                person_data["photo_url"] = f"/api/persons/{person_data['id']}/photo"
            
            # Ajouter les URLs des empreintes si disponibles
            if person_data.get("has_fingerprints"):
                person_data["fingerprint_urls"] = {
                    "right": f"/api/persons/{person_data['id']}/fingerprint/right",
                    "left": f"/api/persons/{person_data['id']}/fingerprint/left",
                    "thumbs": f"/api/persons/{person_data['id']}/fingerprint/thumbs"
                }
       
        return jsonify(result), 200
       
    except Exception as e:
        logger.error(f"Erreur lors de l'identification de la personne: {e}")
        
        log_identification(
            success=False,
            details={"error": str(e)}
        )
        
        return jsonify({"error": "Erreur interne du serveur"}), 500

@api.route('/process', methods=['POST'])
def process_image():
    """
    Endpoint pour traiter une image et extraire les embeddings de visages
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


# Mise à jour du filtrage avancé pour inclure la région
@api.route('/filter', methods=['POST'])
def filter_persons():
    """
    Endpoint de filtrage avancé avec critères multiples
    Version mise à jour avec support de la région
    Body JSON attendu:
    {
        "filters": {
            "gender": "Masculin",
            "nationality": "France",
            "region": "Île-de-France",
            "age_range": [25, 45],
            "has_fingerprints": true,
            "created_date_range": ["2024-01-01", "2024-12-31"]
        },
        "sort": {
            "by": "created_at",
            "order": "desc"
        },
        "pagination": {
            "page": 1,
            "limit": 50
        },
        "include": {
            "images": false,
            "fingerprints": false
        }
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Corps JSON requis"}), 400
        
        # Extraction des paramètres
        filters_data = data.get('filters', {})
        sort_data = data.get('sort', {})
        pagination_data = data.get('pagination', {})
        include_data = data.get('include', {})
        
        # Construction des filtres (mise à jour)
        filters = {}
        
        if filters_data.get('gender'):
            filters['gender'] = filters_data['gender']
        
        if filters_data.get('nationality'):
            filters['nationality'] = filters_data['nationality']
        
        if filters_data.get('region'):  # Nouveau filtre région
            filters['region'] = filters_data['region']
        
        if filters_data.get('age_range'):
            age_range = filters_data['age_range']
            if isinstance(age_range, list) and len(age_range) == 2:
                filters['age_min'] = age_range[0]
                filters['age_max'] = age_range[1]
        
        if 'has_fingerprints' in filters_data:
            filters['has_fingerprints'] = bool(filters_data['has_fingerprints'])
        
        if filters_data.get('created_date_range'):
            date_range = filters_data['created_date_range']
            if isinstance(date_range, list) and len(date_range) == 2:
                filters['created_after'] = date_range[0]
                filters['created_before'] = date_range[1]
        
        if filters_data.get('age_group'):
            filters['age_group'] = filters_data['age_group']
        
        # Paramètres de tri
        sort_by = sort_data.get('by', 'created_at')
        sort_order = sort_data.get('order', 'desc')
        
        # Paramètres de pagination
        page = pagination_data.get('page', 1)
        limit = pagination_data.get('limit', 20)
        
        # Paramètres d'inclusion
        include_images = include_data.get('images', False)
        include_fingerprints = include_data.get('fingerprints', False)
        summary_only = include_data.get('summary_only', False)
        
        person_service = current_app.person_service
        
        if summary_only:
            result = person_service.get_persons_summary_only(
                page=page,
                limit=limit,
                filters=filters,
                sort_by=sort_by,
                sort_order=sort_order
            )
        else:
            result = person_service.get_all_persons_optimized(
                page=page,
                limit=limit,
                include_images=include_images,
                include_fingerprints=include_fingerprints,
                filters=filters,
                sort_by=sort_by,
                sort_order=sort_order
            )
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Erreur lors du filtrage: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

# ========================
# ENDPOINTS DE STATISTIQUES ET ANALYTICS
# ========================

@api.route('/stats', methods=['GET'])
def get_statistics():
    """
    Endpoint pour récupérer les statistiques optimisées
    
    Query parameters:
    - include_trends: true/false (défaut: false)
    - trends_period: daily/weekly/monthly (défaut: daily)
    - trends_days: nombre de jours pour daily (défaut: 30)
    """
    try:
        include_trends = request.args.get('include_trends', 'false').lower() in ('true', '1', 'yes')
        trends_period = request.args.get('trends_period', 'daily')
        trends_days = request.args.get('trends_days', 30, type=int)
        
        person_service = current_app.person_service
        
        # Statistiques de base
        stats = person_service.get_statistics_optimized()
        
        # Ajouter les tendances si demandées
        if include_trends:
            trends = person_service.get_registration_trends(
                period=trends_period,
                days=trends_days
            )
            stats['trends'] = {
                'period': trends_period,
                'data': trends
            }
        
        return jsonify(stats), 200
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statistiques: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

@api.route('/analytics/duplicates', methods=['GET'])
def analyze_duplicates():
    """
    Endpoint pour analyser les doublons potentiels
    
    Query parameters:
    - threshold: Seuil de similarité (défaut: 0.95)
    """
    try:
        threshold = request.args.get('threshold', 0.95, type=float)
        
        if threshold < 0.8 or threshold > 1.0:
            return jsonify({"error": "Le seuil doit être entre 0.8 et 1.0"}), 400
        
        person_service = current_app.person_service
        duplicates = person_service.analyze_duplicate_faces(threshold)
        
        return jsonify({
            "threshold_used": threshold,
            "potential_duplicates_count": len(duplicates),
            "duplicates": duplicates
        }), 200
        
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse des doublons: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

# ========================
# ENDPOINTS D'ADMINISTRATION
# ========================

@api.route('/admin/health', methods=['GET'])
def get_health_report():
    """Endpoint pour récupérer le rapport de santé de la base de données"""
    try:
        person_service = current_app.person_service
        report = person_service.get_database_health_report()
        
        return jsonify(report), 200
        
    except Exception as e:
        logger.error(f"Erreur lors de la génération du rapport de santé: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

@api.route('/admin/cleanup-embeddings', methods=['POST'])
def cleanup_embeddings():
    """Endpoint pour nettoyer les embeddings orphelins"""
    try:
        person_service = current_app.person_service
        result = person_service.cleanup_orphaned_embeddings()
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage des embeddings: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

@api.route('/admin/rebuild-embedding/<person_id>', methods=['POST'])
def rebuild_person_embedding(person_id):
    """Endpoint pour reconstruire l'embedding d'une personne"""
    try:
        if not person_id or len(person_id) != 36:
            return jsonify({"error": "ID de personne invalide"}), 400
        
        person_service = current_app.person_service
        success = person_service.rebuild_embeddings_for_person(person_id)
        
        if success:
            return jsonify({
                "success": True,
                "message": f"Embedding reconstruit avec succès pour {person_id}"
            }), 200
        else:
            return jsonify({
                "success": False,
                "message": "Échec de la reconstruction de l'embedding"
            }), 400
        
    except Exception as e:
        logger.error(f"Erreur lors de la reconstruction de l'embedding: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

@api.route('/admin/clear-all', methods=['POST'])
def clear_all_data():
    """
    Supprime toutes les données des bases de données
    ATTENTION: Cette opération est irréversible
    """
    try:
        # Vérification de sécurité
        confirmation = request.get_json()
        if not confirmation or confirmation.get('confirm') != 'DELETE_ALL_DATA':
            return jsonify({
                "error": "Confirmation requise. Envoyez {'confirm': 'DELETE_ALL_DATA'}"
            }), 400
        
        # Récupérer toutes les personnes
        persons = Person.query.all()
        person_ids = [person.id for person in persons]
        
        # Supprimer les personnes une par une pour gérer également les embeddings
        person_service = current_app.person_service
        deleted_count = 0
        
        for person_id in person_ids:
            if person_service.delete_person(person_id):
                deleted_count += 1
        
        return jsonify({
            "success": True, 
            "message": f"Toutes les données ont été supprimées ({deleted_count} personnes)",
            "deleted_count": deleted_count
        }), 200
        
    except Exception as e:
        logger.error(f"Erreur générale lors de la suppression des données: {e}")
        return jsonify({"error": f"Erreur interne du serveur: {str(e)}"}), 500

# ========================
# ENDPOINTS DE MÉTADONNÉES
# ========================

# Ajouts dans routes/api.py pour la gestion des régions

@api.route('/regions', methods=['GET'])
def get_available_regions():
    """
    Endpoint pour récupérer la liste des régions disponibles
    """
    try:
        return jsonify({
            "regions": RegionEnum.get_values(),
            "default_region": RegionEnum.get_default(),
            "total_count": len(RegionEnum.get_values()),
            "description": "Régions administratives de Djibouti"
        }), 200
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des régions: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

@api.route('/regions/stats', methods=['GET'])
def get_regions_statistics():
    """
    Endpoint pour récupérer les statistiques par région
    """
    try:
        from sqlalchemy import func
        from models.person import Person
        
        # Statistiques par région
        region_stats = db.session.query(
            Person.region,
            func.count(Person.id).label('count')
        ).group_by(Person.region).all()
        
        # Transformer en dictionnaire
        stats_dict = {stat.region: stat.count for stat in region_stats}
        
        # Ajouter les régions avec 0 personnes
        all_regions = RegionEnum.get_values()
        for region in all_regions:
            if region not in stats_dict:
                stats_dict[region] = 0
        
        # Calculer le total
        total_persons = sum(stats_dict.values())
        
        # Calculer les pourcentages
        percentages = {}
        if total_persons > 0:
            percentages = {
                region: round((count / total_persons * 100), 2) 
                for region, count in stats_dict.items()
            }
        
        return jsonify({
            "region_distribution": stats_dict,
            "region_percentages": percentages,
            "total_persons": total_persons,
            "regions_with_data": len([count for count in stats_dict.values() if count > 0]),
            "available_regions": all_regions,
            "default_region": RegionEnum.get_default()
        }), 200
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statistiques régionales: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

# Mise à jour des métadonnées pour inclure l'énumération des régions
@api.route('/metadata/fields', methods=['GET'])
def get_available_fields():
    """Retourne les champs disponibles pour les filtres et le tri (avec énumération des régions)"""
    return jsonify({
        "sortable_fields": [
            "created_at", "updated_at", "name", "age", "gender", "nationality", "region"
        ],
        "filterable_fields": {
            "gender": {
                "type": "enum",
                "values": ["Masculin", "Féminin", "Autre"]
            },
            "nationality": {
                "type": "string",
                "description": "Nationalité de la personne"
            },
            "region": {
                "type": "enum",
                "values": RegionEnum.get_values(),
                "default": RegionEnum.get_default(),
                "description": "Région administrative de Djibouti"
            },
            "age_min": {
                "type": "integer",
                "description": "Âge minimum (1-120)"
            },
            "age_max": {
                "type": "integer", 
                "description": "Âge maximum (1-120)"
            },
            "age_group": {
                "type": "enum",
                "values": ["child", "young", "adult", "middle", "senior"],
                "description": "Groupes d'âge prédéfinis"
            },
            "has_fingerprints": {
                "type": "boolean",
                "description": "Présence d'empreintes digitales"
            },
            "created_after": {
                "type": "datetime",
                "format": "ISO 8601",
                "description": "Date de création minimum"
            },
            "created_before": {
                "type": "datetime",
                "format": "ISO 8601", 
                "description": "Date de création maximum"
            }
        },
        "searchable_fields": ["name", "nationality", "gender", "region"],
        "enums": {
            "regions": {
                "values": RegionEnum.get_values(),
                "default": RegionEnum.get_default()
            },
            "genders": ["Masculin", "Féminin", "Autre"]
        }
    }), 200

@api.route('/metadata/stats-summary', methods=['GET'])
def get_stats_summary():
    """Retourne un résumé rapide des statistiques pour les dashboards"""
    try:
        person_service = current_app.person_service
        
        # Requêtes optimisées pour un résumé rapide
        total_persons = Person.query.count()
        
        # Personnes avec empreintes (utilise l'index partiel)
        persons_with_fingerprints = db.session.query(Person.id).filter(
            or_(
                Person.fingerprint_right_data.isnot(None),
                Person.fingerprint_left_data.isnot(None),
                Person.fingerprint_thumbs_data.isnot(None)
            )
        ).count()
        
        # Nouvelles inscriptions (utilise l'index sur created_at)
        today = datetime.now(timezone.utc).date()
        today_start = datetime.combine(today, datetime.min.time())
        new_today = db.session.query(Person.id).filter(
            Person.created_at >= today_start
        ).count()
        
        week_start = today_start - timedelta(days=7)
        new_this_week = db.session.query(Person.id).filter(
            Person.created_at >= week_start
        ).count()
        
        jsonify({
                    "total_persons": total_persons,
                    "persons_with_fingerprints": persons_with_fingerprints,
                    "fingerprint_percentage": round((persons_with_fingerprints / total_persons * 100), 1) if total_persons > 0 else 0,
                    "new_today": new_today, 
                    "new_this_week": new_this_week,
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }), 200
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du résumé des stats: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500