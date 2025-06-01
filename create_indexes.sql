-- optimize_database_complete.sql
-- Script complet d'optimisation pour l'API Face Recognition
-- Version définitive - Tous les cas gérés

\echo '========================================='
\echo '   OPTIMISATION COMPLETE BASE DE DONNEES'
\echo '========================================='
\echo ''

-- 1. SUPPRESSION DES INDEX EXISTANTS (si besoin de refaire)
\echo '1. Nettoyage des anciens index...'
DROP INDEX IF EXISTS idx_person_created_at;
DROP INDEX IF EXISTS idx_person_updated_at;
DROP INDEX IF EXISTS idx_person_gender;
DROP INDEX IF EXISTS idx_person_nationality;
DROP INDEX IF EXISTS idx_person_age;
DROP INDEX IF EXISTS idx_person_gender_nationality;
DROP INDEX IF EXISTS idx_person_age_gender;
DROP INDEX IF EXISTS idx_person_created_gender;
DROP INDEX IF EXISTS idx_person_created_nationality;
DROP INDEX IF EXISTS idx_person_fingerprint_right;
DROP INDEX IF EXISTS idx_person_fingerprint_left;
DROP INDEX IF EXISTS idx_person_fingerprint_thumbs;
DROP INDEX IF EXISTS idx_person_has_any_fingerprint;
DROP INDEX IF EXISTS idx_person_created_date;
DROP INDEX IF EXISTS idx_person_created_month;
DROP INDEX IF EXISTS idx_person_created_week;
DROP INDEX IF EXISTS idx_person_recent_first;
DROP INDEX IF EXISTS idx_person_name_lower;
DROP INDEX IF EXISTS idx_person_has_right_fingerprint;
DROP INDEX IF EXISTS idx_person_has_left_fingerprint;
DROP INDEX IF EXISTS idx_person_has_thumbs_fingerprint;
DROP INDEX IF EXISTS idx_person_fingerprints_composite;

\echo '   Anciens index supprimés'
\echo ''

-- 2. CREATION DES INDEX PRINCIPAUX
\echo '2. Création des index principaux...'

-- Index sur les colonnes de tri/filtrage (API standard)
CREATE INDEX idx_person_created_at ON person(created_at);
CREATE INDEX idx_person_updated_at ON person(updated_at);
CREATE INDEX idx_person_gender ON person(gender);
CREATE INDEX idx_person_nationality ON person(nationality);
CREATE INDEX idx_person_age ON person(age);

\echo '   ✓ Index principaux créés'

-- 3. INDEX COMPOSITES POUR DASHBOARD
\echo '3. Création des index composites pour dashboard...'

CREATE INDEX idx_person_gender_nationality ON person(gender, nationality);
CREATE INDEX idx_person_age_gender ON person(age, gender);
CREATE INDEX idx_person_created_gender ON person(created_at, gender);
CREATE INDEX idx_person_created_nationality ON person(created_at, nationality);

\echo '   ✓ Index composites créés'

-- 4. INDEX POUR EMPREINTES DIGITALES (version corrigée)
\echo '4. Création des index pour empreintes digitales...'

-- Index booléens (pas sur les BLOB volumineux)
CREATE INDEX idx_person_has_right_fingerprint ON person((fingerprint_right_data IS NOT NULL));
CREATE INDEX idx_person_has_left_fingerprint ON person((fingerprint_left_data IS NOT NULL));
CREATE INDEX idx_person_has_thumbs_fingerprint ON person((fingerprint_thumbs_data IS NOT NULL));

-- Index composite pour with-fingerprints + tri
CREATE INDEX idx_person_fingerprints_composite ON person(
    (fingerprint_right_data IS NOT NULL OR 
     fingerprint_left_data IS NOT NULL OR 
     fingerprint_thumbs_data IS NOT NULL),
    created_at DESC
);

\echo '   ✓ Index empreintes digitales créés'

-- 5. INDEX POUR STATISTIQUES TEMPORELLES
\echo '5. Création des index pour statistiques temporelles...'

CREATE INDEX idx_person_created_date ON person(DATE(created_at));
CREATE INDEX idx_person_created_month ON person(EXTRACT(YEAR FROM created_at), EXTRACT(MONTH FROM created_at));
CREATE INDEX idx_person_created_week ON person(EXTRACT(YEAR FROM created_at), EXTRACT(WEEK FROM created_at));

\echo '   ✓ Index temporels créés'

-- 6. INDEX POUR PERFORMANCE GENERALE
\echo '6. Création des index pour performance générale...'

-- Index pour l'ordre par défaut des API (plus récents en premier)
CREATE INDEX idx_person_recent_first ON person(created_at DESC, id);

-- Index pour la recherche textuelle (noms)
CREATE INDEX idx_person_name_lower ON person(LOWER(name));

\echo '   ✓ Index de performance créés'

-- 7. OPTIMISATION DES STATISTIQUES
\echo '7. Optimisation des statistiques PostgreSQL...'

-- Augmenter les statistiques pour de meilleures optimisations
ALTER TABLE person ALTER COLUMN nationality SET STATISTICS 1000;
ALTER TABLE person ALTER COLUMN gender SET STATISTICS 1000;
ALTER TABLE person ALTER COLUMN age SET STATISTICS 500;

-- Analyser la table pour mettre à jour les statistiques
ANALYZE person;

\echo '   ✓ Statistiques optimisées'