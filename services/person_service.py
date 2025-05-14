# services/person_service.py
import logging
import os
import uuid
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

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
            
            # Sauvegarder l'image du visage
            filename = f"{person_id}_{image_file.filename}"
            image_path = os.path.join(self.upload_folder, filename)
            image_file.save(image_path)
            
            # Extraire l'embedding du visage
            embedding, bbox, score = self.face_service.extract_embedding(image_path)
            
            if embedding is None:
                logger.error(f"Impossible d'extraire l'embedding du visage pour {name}")
                if os.path.exists(image_path):
                    os.remove(image_path)
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
                if os.path.exists(image_path):
                    os.remove(image_path)
                return None
            
            # Initialiser les chemins des empreintes à None
            fingerprint_right_path = None
            fingerprint_left_path = None
            fingerprint_thumbs_path = None
            
            # Traiter les empreintes si fournies
            if fingerprint_right:
                fp_right_filename = f"{person_id}_right_{fingerprint_right.filename}"
                fingerprint_right_path = os.path.join(self.fingerprints_folder, fp_right_filename)
                fingerprint_right.save(fingerprint_right_path)
                logger.info(f"Empreinte main droite sauvegardée pour {name}: {fingerprint_right_path}")
            
            if fingerprint_left:
                fp_left_filename = f"{person_id}_left_{fingerprint_left.filename}"
                fingerprint_left_path = os.path.join(self.fingerprints_folder, fp_left_filename)
                fingerprint_left.save(fingerprint_left_path)
                logger.info(f"Empreinte main gauche sauvegardée pour {name}: {fingerprint_left_path}")
            
            if fingerprint_thumbs:
                fp_thumbs_filename = f"{person_id}_thumbs_{fingerprint_thumbs.filename}"
                fingerprint_thumbs_path = os.path.join(self.fingerprints_folder, fp_thumbs_filename)
                fingerprint_thumbs.save(fingerprint_thumbs_path)
                logger.info(f"Empreinte des pouces sauvegardée pour {name}: {fingerprint_thumbs_path}")
            
            # Créer la personne dans la base de données
            person = Person(
                id=person_id,
                name=name,
                age=age,
                gender=gender,
                nationality=nationality,
                photo_path=image_path,
                vector_id=person_id,
                fingerprint_right_path=fingerprint_right_path,
                fingerprint_left_path=fingerprint_left_path,
                fingerprint_thumbs_path=fingerprint_thumbs_path
            )
            
            db.session.add(person)
            db.session.commit()
            
            logger.info(f"Personne créée avec succès: {name} (ID: {person_id})")
            return person
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Erreur de base de données lors de la création de la personne: {e}")
            # Nettoyage en cas d'erreur
            if 'image_path' in locals() and os.path.exists(image_path):
                os.remove(image_path)
            return None
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erreur lors de la création de la personne: {e}")
            # Nettoyage en cas d'erreur
            if 'image_path' in locals() and os.path.exists(image_path):
                os.remove(image_path)
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
                    # Ajouter les URLs pour accéder aux empreintes
                    person_dict = person.to_dict()
                    
                    if person.fingerprint_right_path:
                        person_dict["fingerprint_right_url"] = f"/api/persons/{person.id}/fingerprint/right"
                    
                    if person.fingerprint_left_path:
                        person_dict["fingerprint_left_url"] = f"/api/persons/{person.id}/fingerprint/left"
                    
                    if person.fingerprint_thumbs_path:
                        person_dict["fingerprint_thumbs_url"] = f"/api/persons/{person.id}/fingerprint/thumbs"
                    
                    return {
                        "found": True,
                        "person": person_dict,
                        "similarity": match["similarity"]
                    }
                
                # Approche 2: Essayer avec le vector_id
                person = Person.query.filter_by(vector_id=direct_id).first()
                
                if person:
                    # Ajouter les URLs pour accéder aux empreintes
                    person_dict = person.to_dict()
                    
                    if person.fingerprint_right_path:
                        person_dict["fingerprint_right_url"] = f"/api/persons/{person.id}/fingerprint/right"
                    
                    if person.fingerprint_left_path:
                        person_dict["fingerprint_left_url"] = f"/api/persons/{person.id}/fingerprint/left"
                    
                    if person.fingerprint_thumbs_path:
                        person_dict["fingerprint_thumbs_url"] = f"/api/persons/{person.id}/fingerprint/thumbs"
                    
                    return {
                        "found": True,
                        "person": person_dict,
                        "similarity": match["similarity"]
                    }
                
                # Approche 3: Essayer avec person_id dans les métadonnées
                if "metadata" in match and "person_id" in match["metadata"]:
                    metadata_person_id = match["metadata"]["person_id"]
                    person = Person.query.filter_by(id=metadata_person_id).first()
                    
                    if person:
                        # Ajouter les URLs pour accéder aux empreintes
                        person_dict = person.to_dict()
                        
                        if person.fingerprint_right_path:
                            person_dict["fingerprint_right_url"] = f"/api/persons/{person.id}/fingerprint/right"
                        
                        if person.fingerprint_left_path:
                            person_dict["fingerprint_left_url"] = f"/api/persons/{person.id}/fingerprint/left"
                        
                        if person.fingerprint_thumbs_path:
                            person_dict["fingerprint_thumbs_url"] = f"/api/persons/{person.id}/fingerprint/thumbs"
                        
                        return {
                            "found": True,
                            "person": person_dict,
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
    
    def get_all_persons(self):
        """Récupère toutes les personnes dans la base de données"""
        try:
            # Pour PostgreSQL, on peut utiliser la même requête
            persons = Person.query.all()
            result = []
            
            for person in persons:
                person_dict = person.to_dict()
                
                # Ajouter les URLs pour accéder aux empreintes
                if person.fingerprint_right_path:
                    person_dict["fingerprint_right_url"] = f"/api/persons/{person.id}/fingerprint/right"
                
                if person.fingerprint_left_path:
                    person_dict["fingerprint_left_url"] = f"/api/persons/{person.id}/fingerprint/left"
                
                if person.fingerprint_thumbs_path:
                    person_dict["fingerprint_thumbs_url"] = f"/api/persons/{person.id}/fingerprint/thumbs"
                
                result.append(person_dict)
                
            return result
        except SQLAlchemyError as e:
            logger.error(f"Erreur de base de données lors de la récupération des personnes: {e}")
            return []
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des personnes: {e}")
            return []
    
    def get_persons_with_fingerprints(self):
        """Récupère toutes les personnes qui ont des empreintes digitales"""
        try:
            # Pour PostgreSQL, on utilise une syntaxe compatible
            persons = Person.query.filter(
                db.or_(
                    Person.fingerprint_right_path.isnot(None),
                    Person.fingerprint_left_path.isnot(None),
                    Person.fingerprint_thumbs_path.isnot(None)
                )
            ).all()
            
            result = []
            
            for person in persons:
                person_dict = person.to_dict()
                
                # Ajouter les URLs pour accéder aux empreintes
                if person.fingerprint_right_path:
                    person_dict["fingerprint_right_url"] = f"/api/persons/{person.id}/fingerprint/right"
                
                if person.fingerprint_left_path:
                    person_dict["fingerprint_left_url"] = f"/api/persons/{person.id}/fingerprint/left"
                
                if person.fingerprint_thumbs_path:
                    person_dict["fingerprint_thumbs_url"] = f"/api/persons/{person.id}/fingerprint/thumbs"
                
                result.append(person_dict)
                
            return result
        except SQLAlchemyError as e:
            logger.error(f"Erreur de base de données lors de la récupération des personnes avec empreintes: {e}")
            return []
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des personnes avec empreintes: {e}")
            return []
    
    def get_person_by_id(self, person_id):
        """Récupère une personne par son ID"""
        try:
            person = Person.query.filter_by(id=person_id).first()
            
            if not person:
                return None
                
            person_dict = person.to_dict()
            
            # Ajouter les URLs pour accéder aux empreintes
            if person.fingerprint_right_path:
                person_dict["fingerprint_right_url"] = f"/api/persons/{person.id}/fingerprint/right"
            
            if person.fingerprint_left_path:
                person_dict["fingerprint_left_url"] = f"/api/persons/{person.id}/fingerprint/left"
            
            if person.fingerprint_thumbs_path:
                person_dict["fingerprint_thumbs_url"] = f"/api/persons/{person.id}/fingerprint/thumbs"
                
            return person_dict
        except SQLAlchemyError as e:
            logger.error(f"Erreur de base de données lors de la récupération de la personne: {e}")
            return None
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la personne: {e}")
            return None
    
    def delete_person(self, person_id):
        """Supprime une personne et son embedding"""
        try:
            person = Person.query.filter_by(id=person_id).first()
            
            if not person:
                return False
            
            # Supprimer l'embedding
            self.vector_store.delete_embedding(person.vector_id)
            
            # Supprimer l'image du visage
            if os.path.exists(person.photo_path):
                os.remove(person.photo_path)
            
            # Supprimer les images d'empreintes
            if person.fingerprint_right_path and os.path.exists(person.fingerprint_right_path):
                os.remove(person.fingerprint_right_path)
            
            if person.fingerprint_left_path and os.path.exists(person.fingerprint_left_path):
                os.remove(person.fingerprint_left_path)
            
            if person.fingerprint_thumbs_path and os.path.exists(person.fingerprint_thumbs_path):
                os.remove(person.fingerprint_thumbs_path)
            
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