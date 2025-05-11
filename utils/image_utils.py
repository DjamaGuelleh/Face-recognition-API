import os
import uuid
import logging
from werkzeug.utils import secure_filename
from PIL import Image

logger = logging.getLogger(__name__)

def allowed_file(filename, allowed_extensions):
    """Vérifie si le fichier a une extension autorisée"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def save_image(file, upload_folder, allowed_extensions):
    """
    Sauvegarde une image téléchargée avec un nom sécurisé
    
    Args:
        file: Fichier téléchargé
        upload_folder: Dossier de destination
        allowed_extensions: Extensions autorisées
        
    Returns:
        str: Chemin vers le fichier sauvegardé ou None en cas d'erreur
    """
    try:
        if file and allowed_file(file.filename, allowed_extensions):
            # Sécuriser le nom de fichier
            original_filename = secure_filename(file.filename)
            # Générer un nom unique
            unique_filename = f"{uuid.uuid4()}_{original_filename}"
            file_path = os.path.join(upload_folder, unique_filename)
            
            # Sauvegarder le fichier
            file.save(file_path)
            
            # Vérifier que c'est bien une image valide
            try:
                with Image.open(file_path) as img:
                    img.verify()  # Vérifie que l'image est valide
                return file_path
            except Exception as e:
                # Si ce n'est pas une image valide, supprimer le fichier
                if os.path.exists(file_path):
                    os.remove(file_path)
                logger.error(f"Le fichier n'est pas une image valide: {e}")
                return None
        else:
            logger.error(f"Extension de fichier non autorisée: {file.filename}")
            return None
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde de l'image: {e}")
        return None

def get_file_extension(filename):
    """Récupère l'extension d'un fichier"""
    if '.' in filename:
        return filename.rsplit('.', 1)[1].lower()
    return ""