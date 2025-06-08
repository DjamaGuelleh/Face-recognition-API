"""Add region field with Djibouti regions enum

Revision ID: e5d0b9c46344
Revises: e36da302aeb4
Create Date: 2025-06-08 14:18:41.060008

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5d0b9c46344'
down_revision: Union[str, None] = 'e36da302aeb4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ÉTAPE 1: Ajouter la colonne région comme NULLABLE d'abord
    op.add_column('person', sa.Column('region', sa.String(length=100), nullable=True))
    
    # ÉTAPE 2: Définir Djibouti comme valeur par défaut pour tous les enregistrements existants
    op.execute("UPDATE person SET region = 'Djibouti' WHERE region IS NULL")
    
    # ÉTAPE 3: Rendre la colonne NOT NULL après avoir défini les valeurs par défaut
    op.alter_column('person', 'region', nullable=False, server_default='Djibouti')
    
    # ÉTAPE 4: Créer une contrainte CHECK pour valider les régions autorisées
    op.execute("""
        ALTER TABLE person 
        ADD CONSTRAINT check_valid_region 
        CHECK (region IN ('Djibouti', 'Arta', 'Ali-Sabieh', 'Dikhil', 'Tadjourah', 'Obock'))
    """)
    
    # NOTE: Les index seront recréés par le script SQL séparé
    # Ne pas supprimer les index existants dans cette migration


def downgrade() -> None:
    """Downgrade schema."""
    # Supprimer la contrainte CHECK
    op.execute("ALTER TABLE person DROP CONSTRAINT IF EXISTS check_valid_region")
    
    # Supprimer la colonne région
    op.drop_column('person', 'region')
    
    # NOTE: Les index seront restaurés automatiquement si nécessaire