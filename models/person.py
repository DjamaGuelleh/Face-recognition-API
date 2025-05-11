from datetime import datetime
from .database import db
import uuid

class Person(db.Model):
    """Modèle de données pour une personne"""
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(20), nullable=False)
    nationality = db.Column(db.String(50), nullable=False)
    photo_path = db.Column(db.String(255), nullable=False)
    vector_id = db.Column(db.String(36), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Person {self.name}, {self.age} ans>"
    
    def to_dict(self):
        """Convertit l'objet en dictionnaire pour l'API"""
        return {
            "id": self.id,
            "name": self.name,
            "age": self.age,
            "gender": self.gender,
            "nationality": self.nationality,
            "photo_path": self.photo_path,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }