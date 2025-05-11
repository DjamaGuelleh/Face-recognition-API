import logging
import os
import uuid
from datetime import datetime

from models.database import db
from models.person import Person

logger = logging.getLogger(__name__)

class PersonService:
    """Service pour la gestion des personnes"""
    
    def __init__(self, vector_store, face_service, upload_folder):
        """
        Initialise le service
        
        Args:
            vector_store: Instance de VectorStore pour la gestion des embeddings
            face_service: Instance de FaceService pour l'extraction d'embeddings
            upload_folder: Dossier pour stocker les images
        """
        self.vector_store = vector_store
        self.face_service = face_service
        self.upload_folder = upload_folder
        
    def create_person(self, name, age, gender, nationality, image_file):
        """
        Crée une nouvelle personne avec son embedding facial
        
        Args:
            name: Nom de la personne
            age: Âge de la personne
            gender: Genre de la personne
            nationality: Nationalité de la personne
            image_file: Fichier image contenant un visage
            
        Returns:
            Person ou None en cas d'erreur
        """
        try:
            # Générer un identifiant unique pour la personne
            person_id = str(uuid.uuid4())
            
            # Sauvegarder l'image
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
            
            # Métadonnées pour ChromaDB - on utilise l'ID de la personne directement
            metadata = {
                "name": name,
                "age": age,
                "gender": gender,
                "nationality": nationality,
                "person_id": person_id  # Pour compatibilité avec l'existant
            }
            
            # Ajouter l'embedding à ChromaDB en utilisant l'ID de la personne
            if not self.vector_store.add_embedding(person_id, embedding, metadata):
                logger.error(f"Erreur lors de l'ajout de l'embedding pour {name}")
                if os.path.exists(image_path):
                    os.remove(image_path)
                return None
            
            # Créer la personne dans la base de données
            # On utilise le même ID pour vector_id
            person = Person(
                id=person_id,
                name=name,
                age=age,
                gender=gender,
                nationality=nationality,
                photo_path=image_path,
                vector_id=person_id  # Même valeur que person_id
            )
            
            db.session.add(person)
            db.session.commit()
            
            logger.info(f"Personne créée avec succès: {name} (ID: {person_id})")
            return person
            
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
            
            # Récupérer les informations de la personne (maintenant l'ID est directement l'ID de la personne)
            best_match = matches[0]
            person_id = best_match["id"]  # ID direct de ChromaDB, pas depuis metadata
            
            person = Person.query.filter_by(id=person_id).first()
            
            if not person:
                logger.warning(f"Personne {person_id} non trouvée dans la base de données malgré correspondance dans ChromaDB")
                return {"found": False, "message": "Personne non trouvée dans la base de données"}
            
            return {
                "found": True,
                "person": person.to_dict(),
                "similarity": best_match["similarity"]
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche de la personne: {e}")
            # Nettoyer le fichier temporaire en cas d'erreur
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
            return {"found": False, "message": f"Erreur interne: {str(e)}"}
        
    def get_all_persons(self):
        """Récupère toutes les personnes dans la base de données"""
        try:
            persons = Person.query.all()
            return [person.to_dict() for person in persons]
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des personnes: {e}")
            return []
    
    def get_person_by_id(self, person_id):
        """Récupère une personne par son ID"""
        try:
            person = Person.query.filter_by(id=person_id).first()
            return person.to_dict() if person else None
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
            
            # Supprimer l'image
            if os.path.exists(person.photo_path):
                os.remove(person.photo_path)
            
            # Supprimer la personne
            db.session.delete(person)
            db.session.commit()
            
            logger.info(f"Personne supprimée avec succès: {person_id}")
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erreur lors de la suppression de la personne: {e}")
            return False