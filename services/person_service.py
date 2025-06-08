# services/person_service.py - Version Complètement Optimisée
import logging
import os
import uuid
import base64
import mimetypes
import io
from datetime import datetime, timedelta
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, case, and_, or_, text, desc, asc
from sqlalchemy.orm import selectinload, defer, undefer
from flask import send_file

from models.database import db
from models.person import Person
from models.enums import RegionEnum

logger = logging.getLogger(__name__)

class PersonService:
    """Service optimisé pour la gestion des personnes avec pagination et filtres avancés"""
    
    def __init__(self, vector_store, face_service, upload_folder, fingerprints_folder):
        """
        Initialise le service
        
        Args:
            vector_store: Instance de VectorStore pour la gestion des embeddings
            face_service: Instance de FaceService pour l'extraction d'embeddings
            upload_folder: Dossier pour stocker les photos de visage
            fingerprints_folder: Dossier pour stocker les images d'empreintes
        """
        self.vector_store = vector_store
        self.face_service = face_service
        self.upload_folder = upload_folder
        self.fingerprints_folder = fingerprints_folder
        
    # ========================
    # CRÉATION DE PERSONNE
    # ========================
    
    # Mise à jour de la méthode create_person
    def create_person(self, name, age, gender, nationality, region=None, image_file=None, 
                    fingerprint_right=None, fingerprint_left=None, fingerprint_thumbs=None):
        """
        Crée une nouvelle personne avec son embedding facial et ses empreintes
        Version avec énumération des régions et défaut Djibouti
        """
        temp_path = None
        try:
            # Si aucune région n'est spécifiée, utiliser Djibouti par défaut
            if not region:
                region = RegionEnum.get_default()
                
            # Validation des données d'entrée
            if not self._validate_person_data(name, age, gender, nationality, region):
                return None
                
            # Générer un identifiant unique pour la personne
            person_id = str(uuid.uuid4())
            
            # Sauvegarder temporairement l'image du visage pour extraction d'embedding
            temp_filename = f"temp_{uuid.uuid4()}_{image_file.filename}"
            temp_path = os.path.join(self.upload_folder, temp_filename)
            image_file.save(temp_path)
            
            # Extraire l'embedding du visage
            embedding, bbox, score = self.face_service.extract_embedding(temp_path)
            
            if embedding is None:
                logger.error(f"Impossible d'extraire l'embedding du visage pour {name}")
                return None
            
            # Métadonnées pour ChromaDB
            metadata = {
                "name": name,
                "age": age,
                "gender": gender,
                "nationality": nationality,
                "region": region,
                "person_id": person_id,
                "detection_score": score
            }
            
            # Transaction atomique
            with db.session.begin():
                # Ajouter l'embedding à ChromaDB
                if not self.vector_store.add_embedding(person_id, embedding, metadata):
                    logger.error(f"Erreur lors de l'ajout de l'embedding pour {name}")
                    raise Exception("Échec de l'ajout de l'embedding")
                
                # Préparer les données binaires
                binary_data = self._prepare_binary_data(
                    image_file, fingerprint_right, fingerprint_left, fingerprint_thumbs
                )
                
                # Créer la personne dans la base de données
                person = Person(
                    id=person_id,
                    name=name.strip(),
                    age=age,
                    gender=gender.strip(),
                    nationality=nationality.strip(),
                    region=region.strip(),
                    vector_id=person_id,
                    **binary_data
                )
                
                db.session.add(person)
                # Le commit est automatique grâce à begin()
                
            logger.info(f"Personne créée avec succès: {name} (ID: {person_id}, Région: {region})")
            return person
            
        except Exception as e:
            # Le rollback est automatique en cas d'exception dans begin()
            logger.error(f"Erreur lors de la création de la personne: {e}")
            # Nettoyer l'embedding en cas d'erreur
            try:
                self.vector_store.delete_embedding(person_id)
            except:
                pass
            return None
        finally:
            # Supprimer le fichier temporaire
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
    
    # Mise à jour de la validation avec énumération
    def _validate_person_data(self, name, age, gender, nationality, region):
        """Valide les données d'une personne avec énumération des régions"""
        if not name or len(name.strip()) < 2:
            logger.error("Le nom doit contenir au moins 2 caractères")
            return False
        if not isinstance(age, int) or age < 1 or age > 120:
            logger.error("L'âge doit être entre 1 et 120 ans")
            return False
        if not gender or gender.strip() not in ['Masculin', 'Féminin', 'Autre']:
            logger.error("Le genre doit être 'Masculin', 'Féminin' ou 'Autre'")
            return False
        if not nationality or len(nationality.strip()) < 2:
            logger.error("La nationalité doit être spécifiée")
            return False
        
        # Validation de la région avec énumération
        if not region:
            logger.error("La région doit être spécifiée")
            return False
        
        valid_regions = RegionEnum.get_values()
        if region.strip() not in valid_regions:
            logger.error(f"La région doit être l'une des suivantes: {', '.join(valid_regions)}")
            return False
            
        return True
    
    # Méthode utilitaire pour obtenir les régions disponibles
    def get_available_regions(self):
        """Retourne la liste des régions disponibles"""
        return {
            "regions": RegionEnum.get_values(),
            "default_region": RegionEnum.get_default(),
            "total_count": len(RegionEnum.get_values())
        }
    
    def _prepare_binary_data(self, image_file, fingerprint_right, fingerprint_left, fingerprint_thumbs):
        """Prépare les données binaires pour le stockage"""
        binary_data = {}
        
        # Photo principale
        if image_file:
            image_file.seek(0)
            binary_data['photo_data'] = image_file.read()
            binary_data['photo_mime_type'] = mimetypes.guess_type(image_file.filename)[0] or 'image/jpeg'
        
        # Empreintes
        for field_name, file_obj in [
            ('fingerprint_right', fingerprint_right),
            ('fingerprint_left', fingerprint_left),
            ('fingerprint_thumbs', fingerprint_thumbs)
        ]:
            if file_obj:
                file_obj.seek(0)
                binary_data[f'{field_name}_data'] = file_obj.read()
                binary_data[f'{field_name}_mime_type'] = mimetypes.guess_type(file_obj.filename)[0] or 'image/jpeg'
        
        return binary_data
    
    # ========================
    # RECHERCHE ET RÉCUPÉRATION OPTIMISÉES
    # ========================
    
    def get_all_persons_optimized(self, page=1, limit=20, include_images=False, 
                                 include_fingerprints=False, filters=None, sort_by='created_at', 
                                 sort_order='desc'):
        """
        Récupère les personnes avec pagination avancée et filtres optimisés
        
        Args:
            page: Numéro de page (défaut: 1)
            limit: Nombre d'éléments par page (défaut: 20, max: 100)
            include_images: Inclure les images en base64
            include_fingerprints: Inclure les empreintes
            filters: Dictionnaire de filtres optionnels
            sort_by: Champ de tri ('created_at', 'name', 'age', 'updated_at')
            sort_order: Ordre de tri ('asc', 'desc')
        """
        try:
            # Validation et limitation
            page = max(1, page)
            limit = min(max(1, limit), 100)
            offset = (page - 1) * limit
            
            # Construction de la requête de base
            query = self._build_base_query(include_images, include_fingerprints)
            
            # Application des filtres
            query = self._apply_filters(query, filters)
            
            # Comptage optimisé
            count_query = query.statement.alias()
            total_count = db.session.execute(
                text("SELECT COUNT(*) FROM ({}) AS subquery".format(str(count_query.compile(compile_kwargs={"literal_binds": True}))))
            ).scalar()
            
            # Application du tri
            query = self._apply_sorting(query, sort_by, sort_order)
            
            # Pagination
            persons = query.offset(offset).limit(limit).all()
            
            # Conversion en dictionnaires
            person_dicts = []
            for person in persons:
                person_dict = person.to_dict(
                    include_image_data=include_images,
                    include_fingerprints=include_fingerprints
                )
                person_dicts.append(person_dict)
            
            # Métadonnées de pagination
            pagination_info = self._build_pagination_info(page, limit, total_count)
            
            return {
                "persons": person_dicts,
                "pagination": pagination_info,
                "filters_applied": filters or {},
                "sort": {"by": sort_by, "order": sort_order}
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération paginée: {e}")
            return self._empty_result(page, limit)
    
    def get_persons_summary_only(self, page=1, limit=50, filters=None, sort_by='created_at', sort_order='desc'):
        """
        Version ultra-rapide et minimaliste pour récupérer seulement les infos essentielles
        SANS URLs - juste les données de base
        """
        try:
            page = max(1, page)
            limit = min(max(1, limit), 200)
            offset = (page - 1) * limit
            
            # Requête avec defer pour éviter de charger les BLOB
            query = Person.query.options(
                defer(Person.photo_data),
                defer(Person.fingerprint_right_data),
                defer(Person.fingerprint_left_data),
                defer(Person.fingerprint_thumbs_data)
            )
            
            # Application des filtres
            query = self._apply_filters(query, filters)
            
            # Comptage
            total_count = query.count()
            
            # Tri et pagination
            query = self._apply_sorting(query, sort_by, sort_order)
            results = query.offset(offset).limit(limit).all()
            
            # Conversion MINIMALISTE - seulement les données essentielles
            persons = []
            for person in results:
                # Calculer has_fingerprints et has_photo côté Python
                has_fingerprints = any([
                    person.fingerprint_right_data is not None,
                    person.fingerprint_left_data is not None,
                    person.fingerprint_thumbs_data is not None
                ])
                
                has_photo = person.photo_data is not None
                
                # RÉSUMÉ MINIMAL - pas d'URLs
                person_dict = {
                    "id": person.id,
                    "name": person.name,
                    "age": person.age,
                    "gender": person.gender,
                    "nationality": person.nationality,
                    "has_fingerprints": has_fingerprints,
                    "has_photo": has_photo,
                    "created_at": person.created_at.isoformat()
                }
                persons.append(person_dict)
            
            pagination_info = self._build_pagination_info(page, limit, total_count)
            
            return {
                "persons": persons,
                "pagination": pagination_info,
                "filters_applied": filters or {},
                "sort": {"by": sort_by, "order": sort_order},
                "mode": "summary"
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération summary: {e}")
            return self._empty_result(page, limit)

    
    def get_persons_with_fingerprints_optimized(self, page=1, limit=20, include_images=False, 
                                              include_fingerprints=True):
        """Version optimisée pour les personnes avec empreintes utilisant l'index partiel"""
        filters = {"has_fingerprints": True}
        return self.get_all_persons_optimized(
            page=page, 
            limit=limit, 
            include_images=include_images, 
            include_fingerprints=include_fingerprints,
            filters=filters
        )
    
    def search_persons(self, search_term, page=1, limit=20, search_fields=None):
        """
        Recherche textuelle optimisée dans les personnes
        
        Args:
            search_term: Terme de recherche
            page: Page de résultats
            limit: Limite par page
            search_fields: Liste des champs à rechercher ['name', 'nationality', 'gender']
        """
        try:
            if not search_term or len(search_term.strip()) < 2:
                return self._empty_result(page, limit)
            
            search_term = search_term.strip().lower()
            page = max(1, page)
            limit = min(max(1, limit), 100)
            offset = (page - 1) * limit
            
            # Champs de recherche par défaut
            if not search_fields:
                search_fields = ['name', 'nationality']
            
            # Construction des conditions de recherche
            conditions = []
            if 'name' in search_fields:
                conditions.append(func.lower(Person.name).contains(search_term))
            if 'nationality' in search_fields:
                conditions.append(func.lower(Person.nationality).contains(search_term))
            if 'gender' in search_fields:
                conditions.append(func.lower(Person.gender).contains(search_term))
            
            if not conditions:
                return self._empty_result(page, limit)
            
            # Requête de recherche
            query = Person.query.filter(or_(*conditions))
            
            # Comptage
            total_count = query.count()
            
            # Tri par pertinence (nom exact en premier)
            query = query.order_by(
                case([(func.lower(Person.name) == search_term, 0)], else_=1),
                Person.name.asc()
            )
            
            # Pagination
            persons = query.offset(offset).limit(limit).all()
            
            # Conversion
            person_dicts = [person.to_dict(include_image_data=False) for person in persons]
            
            pagination_info = self._build_pagination_info(page, limit, total_count)
            
            return {
                "persons": person_dicts,
                "pagination": pagination_info,
                "search_term": search_term,
                "search_fields": search_fields
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche de personnes: {e}")
            return self._empty_result(page, limit)
    
    # ========================
    # MÉTHODES AUXILIAIRES DE REQUÊTE
    # ========================
    
    def _build_base_query(self, include_images, include_fingerprints):
        """Construit la requête de base avec optimisations de chargement"""
        if include_images or include_fingerprints:
            # Chargement complet si nécessaire
            return Person.query
        else:
            # Chargement différé des BLOB pour optimiser
            return Person.query.options(
                defer(Person.photo_data),
                defer(Person.fingerprint_right_data),
                defer(Person.fingerprint_left_data),
                defer(Person.fingerprint_thumbs_data)
            )
    
    def _apply_filters(self, query, filters):
        """Applique les filtres à la requête en utilisant les index optimisés (CORRIGÉ avec région)"""
        if not filters:
            return query
        
        # Filtres simples utilisant les index
        if filters.get('gender'):
            query = query.filter(Person.gender == filters['gender'])
        
        if filters.get('nationality'):
            query = query.filter(Person.nationality == filters['nationality'])
        
        # 🔧 CORRECTION: Filtre par région (était manquant)
        if filters.get('region'):
            query = query.filter(Person.region == filters['region'])
        
        # Filtre d'âge optimisé
        if filters.get('age_min') is not None:
            query = query.filter(Person.age >= filters['age_min'])
        if filters.get('age_max') is not None:
            query = query.filter(Person.age <= filters['age_max'])
        
        # Filtre de date optimisé
        if filters.get('created_after'):
            if isinstance(filters['created_after'], str):
                date_filter = datetime.fromisoformat(filters['created_after'])
            else:
                date_filter = filters['created_after']
            query = query.filter(Person.created_at >= date_filter)
        
        if filters.get('created_before'):
            if isinstance(filters['created_before'], str):
                date_filter = datetime.fromisoformat(filters['created_before'])
            else:
                date_filter = filters['created_before']
            query = query.filter(Person.created_at <= date_filter)
        
        # Filtre d'empreintes utilisant l'index partiel
        if filters.get('has_fingerprints') is True:
            query = query.filter(
                or_(
                    Person.fingerprint_right_data.isnot(None),
                    Person.fingerprint_left_data.isnot(None),
                    Person.fingerprint_thumbs_data.isnot(None)
                )
            )
        elif filters.get('has_fingerprints') is False:
            query = query.filter(
                and_(
                    Person.fingerprint_right_data.is_(None),
                    Person.fingerprint_left_data.is_(None),
                    Person.fingerprint_thumbs_data.is_(None)
                )
            )
        
        # Filtres de tranche d'âge prédéfinis
        age_group = filters.get('age_group')
        if age_group:
            age_ranges = {
                'child': (0, 18),
                'young': (19, 30),
                'adult': (31, 45),
                'middle': (46, 60),
                'senior': (61, 120)
            }
            if age_group in age_ranges:
                min_age, max_age = age_ranges[age_group]
                query = query.filter(and_(Person.age >= min_age, Person.age <= max_age))
        
        return query

    def _apply_filters_to_summary(self, query, filters):
        """Version des filtres pour les requêtes summary - IDENTIQUE à _apply_filters"""
        return self._apply_filters(query, filters)
    
    def _apply_sorting(self, query, sort_by, sort_order):
        """Applique le tri en utilisant les index optimisés"""
        sort_columns = {
            'created_at': Person.created_at,
            'updated_at': Person.updated_at,
            'name': Person.name,
            'age': Person.age,
            'gender': Person.gender,
            'nationality': Person.nationality
        }
        
        if sort_by not in sort_columns:
            sort_by = 'created_at'
        
        column = sort_columns[sort_by]
        
        if sort_order.lower() == 'asc':
            return query.order_by(asc(column))
        else:
            return query.order_by(desc(column))
    
    def _apply_sorting_to_summary(self, query, sort_by, sort_order):
        """Version du tri pour les requêtes summary"""
        sort_columns = {
            'created_at': Person.created_at,
            'updated_at': Person.updated_at,
            'name': Person.name,
            'age': Person.age,
            'gender': Person.gender,
            'nationality': Person.nationality
        }
        
        if sort_by not in sort_columns:
            sort_by = 'created_at'
        
        column = sort_columns[sort_by]
        
        if sort_order.lower() == 'asc':
            return query.order_by(asc(column))
        else:
            return query.order_by(desc(column))
    
    def _build_pagination_info(self, page, limit, total_count):
        """Construit les informations de pagination"""
        total_pages = (total_count + limit - 1) // limit if total_count > 0 else 0
        
        return {
            "current_page": page,
            "total_pages": total_pages,
            "total_count": total_count,
            "limit": limit,
            "has_next": page < total_pages,
            "has_prev": page > 1,
            "start_index": (page - 1) * limit + 1 if total_count > 0 else 0,
            "end_index": min(page * limit, total_count)
        }
    
    def _build_fingerprint_urls(self, person_id):
        """Construit les URLs des empreintes pour une personne"""
        return {
            "right": f"/api/persons/{person_id}/fingerprint/right",
            "left": f"/api/persons/{person_id}/fingerprint/left",
            "thumbs": f"/api/persons/{person_id}/fingerprint/thumbs"
        }
    
    def _empty_result(self, page, limit):
        """Retourne un résultat vide avec pagination"""
        return {
            "persons": [],
            "pagination": self._build_pagination_info(page, limit, 0)
        }
    
    # ========================
    # MÉTHODES EXISTANTES OPTIMISÉES
    # ========================
    
    def get_person_by_id(self, person_id, include_images=True, include_fingerprints=True):
        """
        Récupère une personne par son ID avec chargement optimisé
        """
        try:
            query = Person.query.filter_by(id=person_id)
            
            # Optimiser le chargement selon les besoins
            if not include_images and not include_fingerprints:
                query = query.options(
                    defer(Person.photo_data),
                    defer(Person.fingerprint_right_data),
                    defer(Person.fingerprint_left_data),
                    defer(Person.fingerprint_thumbs_data)
                )
            elif not include_fingerprints:
                query = query.options(
                    defer(Person.fingerprint_right_data),
                    defer(Person.fingerprint_left_data),
                    defer(Person.fingerprint_thumbs_data)
                )
            elif not include_images:
                query = query.options(defer(Person.photo_data))
            
            person = query.first()
            
            if not person:
                return None
                
            return person.to_dict(
                include_image_data=include_images,
                include_fingerprints=include_fingerprints
            )
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la personne: {e}")
            return None
    
    def find_person_by_face(self, image_file, threshold=0.7):
        """
        Recherche une personne en utilisant la reconnaissance faciale
        Version optimisée avec chargement des images à la demande
        """
        temp_path = None
        try:
            # Sauvegarder temporairement l'image
            temp_filename = f"temp_{uuid.uuid4()}_{image_file.filename}"
            temp_path = os.path.join(self.upload_folder, temp_filename)
            image_file.save(temp_path)
            
            # Extraire l'embedding
            embedding, bbox, score = self.face_service.extract_embedding(temp_path)
            
            if embedding is None:
                return {"found": False, "message": "Aucun visage détecté dans l'image"}
            
            # Rechercher des visages similaires
            matches = self.vector_store.search_similar(embedding, threshold)
            
            if not matches:
                return {"found": False, "message": "Aucune correspondance trouvée"}
            
            # Rechercher la personne correspondante avec chargement optimisé
            for match in matches:
                person = self._find_person_from_match(match)
                
                if person:
                    return {
                        "found": True,
                        "person": person.to_dict(include_image_data=True),
                        "similarity": match["similarity"],
                        "detection_score": score
                    }
            
            logger.warning(f"Aucune personne trouvée malgré {len(matches)} correspondances")
            return {"found": False, "message": "Personne non trouvée dans la base de données"}
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche de la personne: {e}")
            return {"found": False, "message": f"Erreur interne: {str(e)}"}
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
    
    def _find_person_from_match(self, match):
        """Trouve une personne à partir d'un match ChromaDB"""
        # Approche 1: ID direct
        person = Person.query.filter_by(id=match["id"]).first()
        if person:
            return person
        
        # Approche 2: vector_id
        person = Person.query.filter_by(vector_id=match["id"]).first()
        if person:
            return person
        
        # Approche 3: métadonnées
        if "metadata" in match and "person_id" in match["metadata"]:
            person = Person.query.filter_by(id=match["metadata"]["person_id"]).first()
            if person:
                return person
        
        return None
    
    def delete_person(self, person_id):
        """Supprime une personne et son embedding avec transaction"""
        try:
            with db.session.begin():
                person = Person.query.filter_by(id=person_id).first()
                
                if not person:
                    return False
                
                # Supprimer l'embedding
                self.vector_store.delete_embedding(person.vector_id)
                
                # Supprimer la personne
                db.session.delete(person)
                # Le commit est automatique
                
            logger.info(f"Personne supprimée avec succès: {person_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la suppression de la personne: {e}")
            return False
    
    # ========================
    # MÉTHODES DE GESTION DES IMAGES
    # ========================
    
    def get_person_photo(self, person_id):
        """Récupère la photo d'une personne pour envoi HTTP optimisé"""
        try:
            # Requête optimisée pour ne charger que les données photo
            person = db.session.query(Person.photo_data, Person.photo_mime_type).filter_by(id=person_id).first()
            
            if not person or not person.photo_data:
                return None, None
                
            return person.photo_data, person.photo_mime_type or 'image/jpeg'
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la photo: {e}")
            return None, None
    
    def get_person_fingerprint(self, person_id, fingerprint_type):
        """Récupère une empreinte digitale spécifique"""
        try:
            if fingerprint_type not in ['right', 'left', 'thumbs']:
                return None, None
                
            # Colonnes à charger selon le type
            data_column = getattr(Person, f'fingerprint_{fingerprint_type}_data')
            mime_column = getattr(Person, f'fingerprint_{fingerprint_type}_mime_type')
            
            # Requête optimisée
            result = db.session.query(data_column, mime_column).filter_by(id=person_id).first()
            
            if not result or not result[0]:
                return None, None
                
            return result[0], result[1] or 'image/jpeg'
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de l'empreinte: {e}")
            return None, None
    
    # ========================
    # MÉTHODES DE STATISTIQUES OPTIMISÉES
    # ========================
    
    def get_statistics_optimized(self):
        """Récupère des statistiques optimisées en utilisant les index"""
        try:
            stats = {}
            
            # Statistiques de base (utilise l'index principal)
            stats['total_persons'] = Person.query.count()
            
            # Distribution par genre (utilise l'index sur gender)
            gender_stats = db.session.query(
                Person.gender, 
                func.count(Person.id)
            ).group_by(Person.gender).all()
            stats['gender_distribution'] = dict(gender_stats)
            
            # Top nationalités (utilise l'index sur nationality)
            nationality_stats = db.session.query(
                Person.nationality,
                func.count(Person.id)
            ).group_by(Person.nationality).order_by(
                func.count(Person.id).desc()
            ).limit(10).all()
            stats['top_nationalities'] = [
                {"nationality": nat, "count": count} 
                for nat, count in nationality_stats
            ]
            
            # Statistiques d'âge (utilise l'index sur age)
            age_groups = {
                "0-18": db.session.query(Person.id).filter(Person.age <= 18).count(),
                "19-30": db.session.query(Person.id).filter(
                    and_(Person.age > 18, Person.age <= 30)
                ).count(),
                "31-45": db.session.query(Person.id).filter(
                    and_(Person.age > 30, Person.age <= 45)
                ).count(),
                "46-60": db.session.query(Person.id).filter(
                    and_(Person.age > 45, Person.age <= 60)
                ).count(),
                "60+": db.session.query(Person.id).filter(Person.age > 60).count()
            }
            stats['age_groups'] = age_groups
            
            # Personnes avec empreintes (utilise l'index partiel)
            persons_with_fingerprints = db.session.query(Person.id).filter(
                or_(
                    Person.fingerprint_right_data.isnot(None),
                    Person.fingerprint_left_data.isnot(None),
                    Person.fingerprint_thumbs_data.isnot(None)
                )
            ).count()
            stats['persons_with_fingerprints'] = persons_with_fingerprints
            stats['persons_without_fingerprints'] = stats['total_persons'] - persons_with_fingerprints
            
            # Statistiques temporelles (utilise les index sur created_at)
            now = datetime.utcnow()
            
            # Dernières 24h
            yesterday = now - timedelta(days=1)
            stats['registrations_last_24h'] = db.session.query(Person.id).filter(
                Person.created_at >= yesterday
            ).count()
            
            # Dernière semaine
            last_week = now - timedelta(days=7)
            stats['registrations_last_week'] = db.session.query(Person.id).filter(
                Person.created_at >= last_week
            ).count()
            
            # Dernier mois
            last_month = now - timedelta(days=30)
            stats['registrations_last_month'] = db.session.query(Person.id).filter(
                Person.created_at >= last_month
            ).count()
            
            # Taille des données (estimation rapide)
            size_query = db.session.query(
                func.coalesce(func.sum(func.length(Person.photo_data)), 0).label('photo_size'),
                func.coalesce(func.sum(func.length(Person.fingerprint_right_data)), 0).label('right_size'),
                func.coalesce(func.sum(func.length(Person.fingerprint_left_data)), 0).label('left_size'),
                func.coalesce(func.sum(func.length(Person.fingerprint_thumbs_data)), 0).label('thumbs_size')
            ).first()
            
            total_size_bytes = (size_query.photo_size or 0) + (size_query.right_size or 0) + \
                              (size_query.left_size or 0) + (size_query.thumbs_size or 0)
            stats['total_data_size_mb'] = round(total_size_bytes / (1024 * 1024), 2)
            
            return stats
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des statistiques: {e}")
            return {
                'total_persons': 0,
                'error': 'Impossible de récupérer les statistiques'
            }
    
    def get_registration_trends(self, period='daily', days=30):
        """
        Récupère les tendances d'inscription optimisées
        
        Args:
            period: 'daily', 'weekly', 'monthly'
            days: Nombre de jours à considérer pour 'daily'
        """
        try:
            now = datetime.utcnow()
            trends = []
            
            if period == 'daily':
                # Utilise l'index sur created_at
                for i in range(days, -1, -1):
                    date = now - timedelta(days=i)
                    day_start = datetime(date.year, date.month, date.day, 0, 0, 0)
                    day_end = datetime(date.year, date.month, date.day, 23, 59, 59)
                    
                    count = db.session.query(Person.id).filter(
                        and_(Person.created_at >= day_start, Person.created_at <= day_end)
                    ).count()
                    
                    trends.append({
                        "date": date.strftime('%Y-%m-%d'),
                        "count": count
                    })
            
            elif period == 'weekly':
                # 12 dernières semaines
                for i in range(11, -1, -1):
                    week_end = now - timedelta(weeks=i)
                    week_start = week_end - timedelta(days=7)
                    
                    count = db.session.query(Person.id).filter(
                        and_(Person.created_at >= week_start, Person.created_at < week_end)
                    ).count()
                    
                    week_num = week_end.isocalendar()[1]
                    year = week_end.isocalendar()[0]
                    
                    trends.append({
                        "period": f"W{week_num} {year}",
                        "count": count
                    })
            
            elif period == 'monthly':
                # 12 derniers mois
                for i in range(11, -1, -1):
                    target_month = now.month - i
                    target_year = now.year
                    
                    while target_month <= 0:
                        target_month += 12
                        target_year -= 1
                    
                    first_day = datetime(target_year, target_month, 1)
                    
                    if target_month == 12:
                        next_month_first = datetime(target_year + 1, 1, 1)
                    else:
                        next_month_first = datetime(target_year, target_month + 1, 1)
                    
                    count = db.session.query(Person.id).filter(
                        and_(Person.created_at >= first_day, Person.created_at < next_month_first)
                    ).count()
                    
                    trends.append({
                        "period": first_day.strftime('%B %Y'),
                        "count": count
                    })
            
            return trends
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des tendances: {e}")
            return []
    
    # ========================
    # MÉTHODES DE MAINTENANCE ET OPTIMISATION
    # ========================
    
    def cleanup_orphaned_embeddings(self):
        """
        Nettoie les embeddings orphelins dans ChromaDB
        (embeddings sans personne correspondante en base)
        """
        try:
            # Récupérer tous les IDs de personnes en base
            person_ids = set(
                id_tuple[0] for id_tuple in db.session.query(Person.id).all()
            )
            
            # Récupérer tous les IDs dans ChromaDB
            all_embeddings = self.vector_store.collection.get()
            chroma_ids = set(all_embeddings['ids'])
            
            # Trouver les orphelins
            orphaned_ids = chroma_ids - person_ids
            
            if orphaned_ids:
                logger.info(f"Suppression de {len(orphaned_ids)} embeddings orphelins")
                for orphan_id in orphaned_ids:
                    self.vector_store.delete_embedding(orphan_id)
                
                return {"cleaned": len(orphaned_ids), "orphaned_ids": list(orphaned_ids)}
            else:
                return {"cleaned": 0, "message": "Aucun embedding orphelin trouvé"}
                
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage des embeddings: {e}")
            return {"error": str(e)}
    
    def rebuild_embeddings_for_person(self, person_id):
        """
        Reconstruit l'embedding pour une personne spécifique
        Utile en cas de corruption ou de mise à jour du modèle
        """
        temp_path = None
        try:
            person = Person.query.filter_by(id=person_id).first()
            if not person or not person.photo_data:
                return False
            
            # Sauvegarder temporairement l'image
            temp_filename = f"rebuild_{uuid.uuid4()}.jpg"
            temp_path = os.path.join(self.upload_folder, temp_filename)
            
            with open(temp_path, 'wb') as f:
                f.write(person.photo_data)
            
            # Extraire le nouvel embedding
            embedding, bbox, score = self.face_service.extract_embedding(temp_path)
            
            if embedding is None:
                logger.error(f"Impossible de reconstruire l'embedding pour {person_id}")
                return False
            
            # Métadonnées mises à jour
            metadata = {
                "name": person.name,
                "age": person.age,
                "gender": person.gender,
                "nationality": person.nationality,
                "person_id": person_id,
                "detection_score": score,
                "rebuilt_at": datetime.utcnow().isoformat()
            }
            
            # Mettre à jour dans ChromaDB
            success = self.vector_store.update_embedding(person.vector_id, embedding, metadata)
            
            if success:
                logger.info(f"Embedding reconstruit avec succès pour {person_id}")
                return True
            else:
                logger.error(f"Échec de la reconstruction de l'embedding pour {person_id}")
                return False
                
        except Exception as e:
            logger.error(f"Erreur lors de la reconstruction de l'embedding: {e}")
            return False
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
    
    def analyze_duplicate_faces(self, similarity_threshold=0.95):
        """
        Analyse pour détecter les visages potentiellement dupliqués
        Utile pour la maintenance de la base de données
        """
        try:
            all_persons = Person.query.with_entities(Person.id, Person.name, Person.vector_id).all()
            duplicates = []
            
            for person in all_persons:
                # Rechercher des visages très similaires
                # Note: Ceci est coûteux, à utiliser avec parcimonie
                try:
                    # Récupérer l'embedding depuis ChromaDB
                    embedding_result = self.vector_store.collection.get(
                        ids=[person.vector_id], 
                        include=["embeddings"]
                    )
                    
                    if embedding_result['embeddings'] and embedding_result['embeddings'][0]:
                        embedding = embedding_result['embeddings'][0]
                        
                        # Rechercher des similaires
                        matches = self.vector_store.search_similar(
                            embedding, 
                            threshold=similarity_threshold, 
                            limit=10
                        )
                        
                        # Filtrer pour exclure la personne elle-même
                        potential_duplicates = [
                            match for match in matches 
                            if match['id'] != person.vector_id and match['similarity'] >= similarity_threshold
                        ]
                        
                        if potential_duplicates:
                            duplicates.append({
                                "person_id": person.id,
                                "person_name": person.name,
                                "potential_duplicates": potential_duplicates
                            })
                            
                except Exception as e:
                    logger.warning(f"Erreur lors de l'analyse de {person.id}: {e}")
                    continue
            
            return duplicates
            
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse des doublons: {e}")
            return []
    
    def get_database_health_report(self):
        """
        Génère un rapport de santé de la base de données
        """
        try:
            report = {
                "timestamp": datetime.utcnow().isoformat(),
                "status": "healthy"
            }
            
            # Statistiques de base
            total_persons = Person.query.count()
            report["total_persons"] = total_persons
            
            # Vérifier les données manquantes
            persons_without_photo = db.session.query(Person.id).filter(
                Person.photo_data.is_(None)
            ).count()
            report["persons_without_photo"] = persons_without_photo
            
            # Vérifier la cohérence avec ChromaDB
            try:
                chroma_count = self.vector_store.collection.count()
                report["chroma_embeddings_count"] = chroma_count
                report["embedding_sync_status"] = "synced" if chroma_count == total_persons else "out_of_sync"
                report["embedding_diff"] = abs(chroma_count - total_persons)
            except Exception as e:
                report["chroma_status"] = f"error: {str(e)}"
                report["status"] = "warning"
            
            # Vérifier les index (requête d'exemple)
            try:
                import time
                start_time = time.time()
                
                # Test de performance des index
                db.session.query(Person.id).filter(Person.gender == 'Masculin').limit(1).all()
                gender_query_time = time.time() - start_time
                
                start_time = time.time()
                db.session.query(Person.id).filter(Person.created_at >= datetime.utcnow() - timedelta(days=1)).limit(1).all()
                date_query_time = time.time() - start_time
                
                report["index_performance"] = {
                    "gender_query_ms": round(gender_query_time * 1000, 2),
                    "date_query_ms": round(date_query_time * 1000, 2),
                    "status": "good" if gender_query_time < 0.1 and date_query_time < 0.1 else "slow"
                }
                
            except Exception as e:
                report["index_performance"] = {"error": str(e)}
                report["status"] = "warning"
            
            # Recommandations
            recommendations = []
            
            if persons_without_photo > 0:
                recommendations.append(f"Nettoyer {persons_without_photo} personnes sans photo")
            
            if report.get("embedding_sync_status") == "out_of_sync":
                recommendations.append("Resynchroniser les embeddings avec ChromaDB")
            
            index_perf = report.get("index_performance", {})
            if index_perf.get("status") == "slow":
                recommendations.append("Vérifier et optimiser les index de base de données")
            
            report["recommendations"] = recommendations
            
            if len(recommendations) > 2:
                report["status"] = "needs_attention"
            
            return report
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération du rapport de santé: {e}")
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "status": "error",
                "error": str(e)
            }
    
    # ========================
    # MÉTHODES DE COMPATIBILITÉ (ANCIENNES SIGNATURES)
    # ========================
    
    def get_all_persons(self, include_images=False, include_fingerprints=False):
        """
        Méthode de compatibilité - redirige vers la version optimisée
        """
        result = self.get_all_persons_optimized(
            page=1, 
            limit=100,  # Limite raisonnable par défaut
            include_images=include_images,
            include_fingerprints=include_fingerprints
        )
        return result.get("persons", [])
    
    def get_persons_with_fingerprints(self, include_images=False, include_fingerprints=False):
        """
        Méthode de compatibilité - redirige vers la version optimisée
        """
        result = self.get_persons_with_fingerprints_optimized(
            page=1,
            limit=100,
            include_images=include_images,
            include_fingerprints=include_fingerprints
        )
        return result.get("persons", [])
    
    def _apply_sorting(self, query, sort_by, sort_order):
        """Applique le tri en utilisant les index optimisés (mise à jour avec région)"""
        sort_columns = {
            'created_at': Person.created_at,
            'updated_at': Person.updated_at,
            'name': Person.name,
            'age': Person.age,
            'gender': Person.gender,
            'nationality': Person.nationality,
            'region': Person.region  # Nouveau champ de tri
        }
        
        if sort_by not in sort_columns:
            sort_by = 'created_at'
        
        column = sort_columns[sort_by]
        
        if sort_order.lower() == 'asc':
            return query.order_by(asc(column))
        else:
            return query.order_by(desc(column))