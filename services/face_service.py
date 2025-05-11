import logging
import numpy as np
from insightface.app import FaceAnalysis
import cv2
import os

logger = logging.getLogger(__name__)

class FaceService:
    """Service pour la détection et l'extraction d'embeddings de visages"""
    
    def __init__(self, model_name="buffalo_l"):
        """Initialise le modèle InsightFace"""
        try:
            self.face_app = FaceAnalysis(
                name=model_name,
                allowed_modules=["detection", "recognition"],
                providers=['CPUExecutionProvider']
            )
            self.face_app.prepare(ctx_id=-1, det_size=(640, 640))
            logger.info(f"Modèle InsightFace '{model_name}' initialisé avec succès")
        except Exception as e:
            logger.error(f"Erreur d'initialisation d'InsightFace: {e}")
            raise
    
    def extract_embedding(self, image_path):
        """
        Extrait l'embedding d'un visage à partir d'une image
        
        Args:
            image_path: Chemin vers l'image à analyser
            
        Returns:
            tuple: (embedding, bbox, score) ou (None, None, None) si aucun visage trouvé
        """
        try:
            # Charger l'image
            img = cv2.imread(image_path)
            if img is None:
                logger.error(f"Impossible de charger l'image: {image_path}")
                return None, None, None
            
            # Conversion en RGB (InsightFace attend RGB)
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            # Détecter les visages
            faces = self.face_app.get(img_rgb)
            
            if not faces:
                logger.warning(f"Aucun visage détecté dans l'image: {image_path}")
                return None, None, None
            
            # Prendre le visage avec le score de détection le plus élevé
            best_face = max(faces, key=lambda x: x.det_score)
            
            # Normaliser l'embedding pour la recherche par similarité cosinus
            embedding = best_face.embedding
            norm = np.linalg.norm(embedding)
            if norm > 0:
                normalized_embedding = embedding / norm
            else:
                normalized_embedding = embedding
            
            return normalized_embedding.tolist(), best_face.bbox.tolist(), best_face.det_score.item()
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction de l'embedding: {e}")
            return None, None, None
    
    def process_image_bytes(self, image_bytes):
        """
        Traite une image depuis des bytes (pour les requêtes HTTP)
        
        Args:
            image_bytes: Bytes de l'image
            
        Returns:
            dict: Résultats de la détection de visages
        """
        try:
            # Convertir les bytes en image OpenCV
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                return {"error": "Format d'image non supporté"}
                
            # Conversion RGB
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            # Détection des visages
            faces = self.face_app.get(img_rgb)
            
            if not faces:
                return {"message": "Aucun visage détecté"}
                
            results = []
            for i, face in enumerate(faces):
                embedding = face.embedding.tolist()
                norm = np.linalg.norm(face.embedding)
                
                if norm > 0:
                    normalized_embedding = (face.embedding / norm).tolist()
                else:
                    normalized_embedding = embedding
                    
                results.append({
                    "face_index": i+1,
                    "embedding": normalized_embedding,
                    "bbox": face.bbox.tolist(),
                    "detection_score": face.det_score.item()
                })
                
            return {"faces": results}
            
        except Exception as e:
            logger.error(f"Erreur de traitement d'image: {str(e)}")
            return {"error": str(e)}