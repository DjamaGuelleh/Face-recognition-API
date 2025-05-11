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
            # Assurez-vous que l'embedding est une liste et non un numpy array
            if hasattr(embedding, 'tolist'):
                embedding = embedding.tolist()
                
            # Vérifiez que l'embedding est bien formaté
            logger.info(f"Ajout d'un embedding de taille {len(embedding)} pour {person_id}")
            
            self.collection.add(
                ids=[person_id],
                embeddings=[embedding],
                metadatas=[metadata]
            )
            
            # Vérifiez que l'embedding a bien été ajouté
            check = self.collection.get(
                ids=[person_id],
                include=["embeddings"]
            )
            
            if check['embeddings'][0] is None:
                logger.error(f"L'embedding pour {person_id} a été ajouté mais est NULL")
                return False
                
            logger.info(f"Embedding ajouté avec succès pour la personne {person_id}")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout de l'embedding: {e}")
            return False
    
    def search_similar(self, embedding, threshold=0.7, limit=5):
        """
        Recherche les embeddings similaires avec un seuil minimal
        """
        try:
            # Assurez-vous que l'embedding est une liste et non un numpy array
            if hasattr(embedding, 'tolist'):
                embedding = embedding.tolist()
                
            logger.info(f"Recherche avec embedding de taille {len(embedding)}")
            
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=limit,
                include=["metadatas", "distances", "embeddings"]
            )
            
            # Vérifier si des résultats ont été trouvés
            if not results['ids'][0]:
                logger.warning("Aucun résultat trouvé")
                return []
            
            # Vérifier si les embeddings existent
            if results.get('embeddings') is None or all(e is None for e in results.get('embeddings', [[]])[0]):
                logger.warning("Les embeddings sont NULL dans les résultats")
                
            # Filtrer par seuil de similarité
            matches = []
            for i, score in enumerate(results['distances'][0]):
                similarity = 1 - score  # Convertir distance cosinus en similarité
                logger.info(f"ID: {results['ids'][0][i]}, Similarité: {similarity}")
                
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