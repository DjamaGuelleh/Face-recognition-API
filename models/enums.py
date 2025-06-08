# models/enums.py
import enum

class RegionEnum(enum.Enum):
    """Énumération des régions de Djibouti"""
    DJIBOUTI = "Djibouti"
    ARTA = "Arta"
    ALI_SABIEH = "Ali-Sabieh"
    DIKHIL = "Dikhil"
    TADJOURAH = "Tadjourah"
    OBOCK = "Obock"
    
    @classmethod
    def get_values(cls):
        """Retourne la liste des valeurs possibles"""
        return [region.value for region in cls]
    
    @classmethod
    def get_default(cls):
        """Retourne la région par défaut"""
        return cls.DJIBOUTI.value