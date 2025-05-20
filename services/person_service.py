# services/person_service.py
import logging
import os
import uuid
import base64
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
import mimetypes

from models.database import db
from models.person import Person

logger = logging.getLogger(__name__)

class PersonService:
    """Service pour la gestion des personnes"""
    
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
        
    def create_person(self, name, age, gender, nationality, image_file, fingerprint_right=None, fingerprint_left=None, fingerprint_thumbs=None):
        """
        Crée une nouvelle personne avec son embedding facial et ses empreintes
        
        Args:
            name: Nom de la personne
            age: Âge de la personne
            gender: Genre de la personne
            nationality: Nationalité de la personne
            image_file: Fichier image contenant un visage
            fingerprint_right: Fichier image des empreintes de la main droite
            fingerprint_left: Fichier image des empreintes de la main gauche
            fingerprint_thumbs: Fichier image des empreintes des pouces
            
        Returns:
            Person ou None en cas d'erreur
        """
        try:
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
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return None
            
            # Métadonnées pour ChromaDB
            metadata = {
                "name": name,
                "age": age,
                "gender": gender,
                "nationality": nationality,
                "person_id": person_id
            }
            
            # Ajouter l'embedding à ChromaDB
            if not self.vector_store.add_embedding(person_id, embedding, metadata):
                logger.error(f"Erreur lors de l'ajout de l'embedding pour {name}")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return None
            
            # Lire les fichiers en binaire pour les stocker en base de données
            photo_data = None
            photo_mime_type = None
            if image_file:
                # Reset file pointer to beginning
                image_file.seek(0)
                photo_data = image_file.read()
                photo_mime_type = mimetypes.guess_type(image_file.filename)[0] or 'application/octet-stream'
            
            fingerprint_right_data = None
            fingerprint_right_mime_type = None
            if fingerprint_right:
                fingerprint_right.seek(0)
                fingerprint_right_data = fingerprint_right.read()
                fingerprint_right_mime_type = mimetypes.guess_type(fingerprint_right.filename)[0] or 'application/octet-stream'
            
            fingerprint_left_data = None
            fingerprint_left_mime_type = None
            if fingerprint_left:
                fingerprint_left.seek(0)
                fingerprint_left_data = fingerprint_left.read()
                fingerprint_left_mime_type = mimetypes.guess_type(fingerprint_left.filename)[0] or 'application/octet-stream'
            
            fingerprint_thumbs_data = None
            fingerprint_thumbs_mime_type = None
            if fingerprint_thumbs:
                fingerprint_thumbs.seek(0)
                fingerprint_thumbs_data = fingerprint_thumbs.read()
                fingerprint_thumbs_mime_type = mimetypes.guess_type(fingerprint_thumbs.filename)[0] or 'application/octet-stream'
            
            # Créer la personne dans la base de données
            person = Person(
                id=person_id,
                name=name,
                age=age,
                gender=gender,
                nationality=nationality,
                vector_id=person_id,
                
                # Nouvelles données binaires
                photo_data=photo_data,
                photo_mime_type=photo_mime_type,
                fingerprint_right_data=fingerprint_right_data,
                fingerprint_right_mime_type=fingerprint_right_mime_type,
                fingerprint_left_data=fingerprint_left_data,
                fingerprint_left_mime_type=fingerprint_left_mime_type,
                fingerprint_thumbs_data=fingerprint_thumbs_data,
                fingerprint_thumbs_mime_type=fingerprint_thumbs_mime_type
            )
            
            db.session.add(person)
            db.session.commit()
            
            # Supprimer l'image temporaire
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
            logger.info(f"Personne créée avec succès: {name} (ID: {person_id})")
            return person
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Erreur de base de données lors de la création de la personne: {e}")
            # Nettoyage en cas d'erreur
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
            return None
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erreur lors de la création de la personne: {e}")
            # Nettoyage en cas d'erreur
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
            return None
            
    def find_person_by_face(self, image_file, threshold=0.7):
        """
        Recherche une personne en utilisant la reconnaissance faciale
        
        Args:
            image_file: Fichier image contenant un visage
            threshold: Seuil de similarité (0-1)
            
        Returns:
            dict: Résultat de la recherche ou None
        """
        try:
            # Sauvegarder temporairement l'image
            temp_filename = f"temp_{uuid.uuid4()}_{image_file.filename}"
            temp_path = os.path.join(self.upload_folder, temp_filename)
            image_file.save(temp_path)
            
            # Extraire l'embedding
            embedding, bbox, score = self.face_service.extract_embedding(temp_path)
            
            # Nettoyer le fichier temporaire
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            if embedding is None:
                return {"found": False, "message": "Aucun visage détecté dans l'image"}
            
            # Rechercher des visages similaires
            matches = self.vector_store.search_similar(embedding, threshold)
            
            if not matches:
                return {"found": False, "message": "Aucune correspondance trouvée"}
            
            # Essayer plusieurs approches pour trouver la personne correspondante
            for match in matches:
                # Approche 1: Essayer avec l'ID direct de ChromaDB
                direct_id = match["id"]
                person = Person.query.filter_by(id=direct_id).first()
                
                if person:
                    # Inclure les données d'image directement
                    return {
                        "found": True,
                        "person": person.to_dict(include_image_data=True),
                        "similarity": match["similarity"]
                    }
                
                # Approche 2: Essayer avec le vector_id
                person = Person.query.filter_by(vector_id=direct_id).first()
                
                if person:
                    # Inclure les données d'image directement
                    return {
                        "found": True,
                        "person": person.to_dict(include_image_data=True),
                        "similarity": match["similarity"]
                    }
                
                # Approche 3: Essayer avec person_id dans les métadonnées
                if "metadata" in match and "person_id" in match["metadata"]:
                    metadata_person_id = match["metadata"]["person_id"]
                    person = Person.query.filter_by(id=metadata_person_id).first()
                    
                    if person:
                        # Inclure les données d'image directement
                        return {
                            "found": True,
                            "person": person.to_dict(include_image_data=True),
                            "similarity": match["similarity"]
                        }
            
            # Si aucune approche n'a fonctionné
            logger.warning(f"Aucune personne trouvée dans la base de données malgré {len(matches)} correspondances dans ChromaDB")
            
            return {"found": False, "message": "Personne non trouvée dans la base de données"}
            
        except SQLAlchemyError as e:
            logger.error(f"Erreur de base de données lors de la recherche de la personne: {e}")
            # Nettoyer le fichier temporaire en cas d'erreur
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
            return {"found": False, "message": f"Erreur de base de données: {str(e)}"}
        except Exception as e:
            logger.error(f"Erreur lors de la recherche de la personne: {e}")
            # Nettoyer le fichier temporaire en cas d'erreur
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
            return {"found": False, "message": f"Erreur interne: {str(e)}"}
    
    def get_all_persons(self, include_images=False, include_fingerprints=False):
        """
        Récupère toutes les personnes dans la base de données
        
        Args:
            include_images: Si True, inclut les photos de visage encodées en base64
            include_fingerprints: Si True, inclut aussi les empreintes digitales
        
        Returns:
            list: Liste des personnes
        """
        try:
            persons = Person.query.all()
            return [person.to_dict(
                include_image_data=include_images, 
                include_fingerprints=include_fingerprints
            ) for person in persons]
        except SQLAlchemyError as e:
            logger.error(f"Erreur de base de données lors de la récupération des personnes: {e}")
            return []
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des personnes: {e}")
            return []

    def get_person_by_id(self, person_id, include_images=True, include_fingerprints=True):
        """
        Récupère une personne par son ID
        
        Args:
            person_id: ID de la personne
            include_images: Si True, inclut la photo de visage encodée en base64
            include_fingerprints: Si True, inclut aussi les empreintes digitales
        
        Returns:
            dict: Informations de la personne ou None
        """
        try:
            person = Person.query.filter_by(id=person_id).first()
            
            if not person:
                return None
                
            return person.to_dict(
                include_image_data=include_images,
                include_fingerprints=include_fingerprints
            )
        except SQLAlchemyError as e:
            logger.error(f"Erreur de base de données lors de la récupération de la personne: {e}")
            return None
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la personne: {e}")
            return None
    
    # def get_persons_with_fingerprints(self, include_images=False):
    #     """Récupère toutes les personnes qui ont des empreintes digitales"""
    #     try:
    #         # Pour PostgreSQL, on utilise une syntaxe compatible
    #         persons = Person.query.filter(
    #             db.or_(
    #                 Person.fingerprint_right_data.isnot(None),
    #                 Person.fingerprint_left_data.isnot(None),
    #                 Person.fingerprint_thumbs_data.isnot(None)
    #             )
    #         ).all()
    #         
    #         return [person.to_dict(include_image_data=include_images) for person in persons]
    #     except SQLAlchemyError as e:
    #         logger.error(f"Erreur de base de données lors de la récupération des personnes avec empreintes: {e}")
    #         return []
    #     except Exception as e:
    #         logger.error(f"Erreur lors de la récupération des personnes avec empreintes: {e}")
    #         return []

    def get_persons_with_fingerprints(self, include_images=False, include_fingerprints=False):
        """
        Récupère toutes les personnes qui ont des empreintes digitales
        
        Args:
            include_images: Si True, inclut les photos encodées en base64
            include_fingerprints: Si True, inclut les empreintes digitales encodées en base64
        
        Returns:
            list: Liste des personnes avec empreintes
        """
        try:
            # Pour PostgreSQL, on utilise une syntaxe compatible
            persons = Person.query.filter(
                db.or_(
                    Person.fingerprint_right_data.isnot(None),
                    Person.fingerprint_left_data.isnot(None),
                    Person.fingerprint_thumbs_data.isnot(None)
                )
            ).all()
            
            return [person.to_dict(
                include_image_data=include_images,
                include_fingerprints=include_fingerprints  # Ajout du paramètre
            ) for person in persons]
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des personnes avec empreintes: {e}")
            return []

    
    def delete_person(self, person_id):
        """Supprime une personne et son embedding"""
        try:
            person = Person.query.filter_by(id=person_id).first()
            
            if not person:
                return False
            
            # Supprimer l'embedding
            self.vector_store.delete_embedding(person.vector_id)
            
            # Supprimer la personne
            db.session.delete(person)
            db.session.commit()
            
            logger.info(f"Personne supprimée avec succès: {person_id}")
            return True
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Erreur de base de données lors de la suppression de la personne: {e}")
            return False
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erreur lors de la suppression de la personne: {e}")
            return False