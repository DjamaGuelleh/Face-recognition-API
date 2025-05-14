import os
from dotenv import load_dotenv

# Chargement des variables d'environnement
load_dotenv()

class Config:
    # Configuration de Flask
    SECRET_KEY = os.environ.get("SECRET_KEY") or "clé-secrète-par-défaut"
    DEBUG = os.environ.get("DEBUG", "False").lower() == "true"
    
    # Configuration de la base de données PostgreSQL
    DB_USER = os.environ.get("DB_USER") or "face_user"
    DB_PASSWORD = os.environ.get("DB_PASSWORD") or "mlkiop"
    DB_HOST = os.environ.get("DB_HOST") or "localhost"
    DB_PORT = os.environ.get("DB_PORT") or "5432"
    DB_NAME = os.environ.get("DB_NAME") or "face_recognition"
    
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URI") or \
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = DEBUG
    
    # Reste de votre configuration existante...
    CHROMA_DB_DIR = os.environ.get("CHROMA_DB_DIR") or "chroma_db"
    CHROMA_COLLECTION = os.environ.get("CHROMA_COLLECTION") or "face_embeddings"
    
    # Configuration des dossiers de téléchargements
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER") or "static/uploads"
    FINGERPRINTS_FOLDER = os.environ.get("FINGERPRINTS_FOLDER") or "static/fingerprints"
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # Configuration InsightFace
    INSIGHTFACE_MODEL = os.environ.get("INSIGHTFACE_MODEL") or "buffalo_l"
    SIMILARITY_THRESHOLD = float(os.environ.get("SIMILARITY_THRESHOLD") or 0.6)
    
    # Crée les dossiers s'ils n'existent pas
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    if not os.path.exists(FINGERPRINTS_FOLDER):
        os.makedirs(FINGERPRINTS_FOLDER)