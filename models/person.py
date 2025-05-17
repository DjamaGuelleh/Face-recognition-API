# models/person.py
from datetime import datetime
from .database import db
import uuid
import base64

class Person(db.Model):
    """Modèle de données pour une personne"""
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(20), nullable=False)
    nationality = db.Column(db.String(50), nullable=False)
    
    # Stockage des chemins de fichiers (pour compatibilité/transition)
    photo_path = db.Column(db.Text, nullable=True)
    fingerprint_right_path = db.Column(db.Text, nullable=True)
    fingerprint_left_path = db.Column(db.Text, nullable=True)
    fingerprint_thumbs_path = db.Column(db.Text, nullable=True)
    
    # Nouveaux champs pour stocker les images directement en base de données
    photo_data = db.Column(db.LargeBinary, nullable=True)  # Photo du visage en binaire
    photo_mime_type = db.Column(db.String(30), nullable=True)  # Type MIME de la photo
    
    fingerprint_right_data = db.Column(db.LargeBinary, nullable=True)  # Empreinte droite en binaire
    fingerprint_right_mime_type = db.Column(db.String(30), nullable=True)
    
    fingerprint_left_data = db.Column(db.LargeBinary, nullable=True)  # Empreinte gauche en binaire
    fingerprint_left_mime_type = db.Column(db.String(30), nullable=True)
    
    fingerprint_thumbs_data = db.Column(db.LargeBinary, nullable=True)  # Empreinte pouces en binaire
    fingerprint_thumbs_mime_type = db.Column(db.String(30), nullable=True)
    
    vector_id = db.Column(db.String(36), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Person {self.name}, {self.age} ans>"
    
    def to_dict(self, include_image_data=False, include_fingerprints=False):
        """
        Convertit l'objet en dictionnaire pour l'API
        
        Args:
            include_image_data: Si True, inclut la photo du visage encodée en base64
            include_fingerprints: Si True, inclut aussi les empreintes digitales en base64
        """
        person_dict = {
            "id": self.id,
            "name": self.name,
            "age": self.age,
            "gender": self.gender,
            "nationality": self.nationality,
            "vector_id": self.vector_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
        
        # Ajouter les propriétés pour indiquer si les empreintes sont disponibles
        has_fingerprints = any([
            self.fingerprint_right_data is not None,
            self.fingerprint_left_data is not None,
            self.fingerprint_thumbs_data is not None
        ])
        person_dict["has_fingerprints"] = has_fingerprints
        
        # Ajouter la photo du visage encodée en base64 si demandé
        if include_image_data and self.photo_data is not None:
            person_dict["photo_data"] = base64.b64encode(self.photo_data).decode('utf-8')
            person_dict["photo_mime_type"] = self.photo_mime_type
        
        # Ajouter les empreintes digitales encodées en base64 si demandé
        if include_fingerprints:
            if self.fingerprint_right_data is not None:
                person_dict["fingerprint_right_data"] = base64.b64encode(self.fingerprint_right_data).decode('utf-8')
                person_dict["fingerprint_right_mime_type"] = self.fingerprint_right_mime_type
            
            if self.fingerprint_left_data is not None:
                person_dict["fingerprint_left_data"] = base64.b64encode(self.fingerprint_left_data).decode('utf-8')
                person_dict["fingerprint_left_mime_type"] = self.fingerprint_left_mime_type
            
            if self.fingerprint_thumbs_data is not None:
                person_dict["fingerprint_thumbs_data"] = base64.b64encode(self.fingerprint_thumbs_data).decode('utf-8')
                person_dict["fingerprint_thumbs_mime_type"] = self.fingerprint_thumbs_mime_type
        
        return person_dict