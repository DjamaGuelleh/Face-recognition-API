import chromadb
from chromadb.config import Settings
import logging
import os

logger = logging.getLogger(__name__)

class VectorStore:
    """Interface avec ChromaDB pour stocker et rechercher des embeddings de visages"""
    
    def __init__(self, db_directory, collection_name):
        """Initialise le client ChromaDB et la collection"""
        
        # S'assurer que le répertoire existe
        if not os.path.exists(db_directory):
            os.makedirs(db_directory)
            
        # Initialiser le client ChromaDB
        try:
            self.client = chromadb.PersistentClient(
                path=db_directory,
                settings=Settings(anonymized_telemetry=False)
            )
            
            # Créer ou récupérer la collection
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}  # Utiliser la distance cosinus
            )
            
            logger.info(f"Collection ChromaDB '{collection_name}' initialisée avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de ChromaDB: {e}")
            raise
    
    def add_embedding(self, person_id, embedding, metadata):
        """Ajoute un embedding à la collection avec les métadonnées associées"""
        try:
            self.collection.add(
                ids=[person_id],
                embeddings=[embedding],
                metadatas=[metadata]
            )
            logger.info(f"Embedding ajouté pour la personne {person_id}")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout de l'embedding: {e}")
            return False
    
    def search_similar(self, embedding, threshold=0.9, limit=1):
        """
        Recherche les embeddings similaires avec un seuil minimal
        
        Args:
            embedding: Vecteur d'embedding à rechercher
            threshold: Seuil de similarité (0-1)
            limit: Nombre maximum de résultats
            
        Returns:
            Liste des correspondances trouvées
        """
        try:
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=limit
            )
            
            # Vérifier si des résultats ont été trouvés
            if not results['ids'][0]:
                return []
            
            # Filtrer par seuil de similarité
            matches = []
            for i, score in enumerate(results['distances'][0]):
                similarity = 1 - score  # Convertir distance cosinus en similarité
                
                if similarity >= threshold:
                    matches.append({
                        'id': results['ids'][0][i],
                        'similarity': similarity,
                        'metadata': results['metadatas'][0][i]
                    })
            
            return matches
        except Exception as e:
            logger.error(f"Erreur lors de la recherche d'embeddings: {e}")
            return []
    
    def delete_embedding(self, person_id):
        """Supprime un embedding de la collection"""
        try:
            self.collection.delete(ids=[person_id])
            logger.info(f"Embedding supprimé pour la personne {person_id}")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la suppression de l'embedding: {e}")
            return False
    
    def update_embedding(self, person_id, embedding, metadata):
        """Met à jour un embedding existant"""
        try:
            # Supprimer l'ancien
            self.delete_embedding(person_id)
            # Ajouter le nouveau
            return self.add_embedding(person_id, embedding, metadata)
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour de l'embedding: {e}")
            return False