-- create_indexes.sql
-- Optimisation des index pour l'API Face Recognition

\echo 'Création des index pour optimisation des performances...'

-- 1. Index sur les colonnes de tri/filtrage principales
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_person_created_at 
ON person(created_at);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_person_updated_at 
ON person(updated_at);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_person_gender 
ON person(gender);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_person_nationality 
ON person(nationality);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_person_age 
ON person(age);

-- 2. Index composites pour requêtes combinées (Dashboard)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_person_gender_nationality 
ON person(gender, nationality);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_person_age_gender 
ON person(age, gender);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_person_created_gender 
ON person(created_at, gender);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_person_created_nationality 
ON person(created_at, nationality);

-- 3. Index pour les requêtes d'empreintes digitales
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_person_fingerprint_right 
ON person(fingerprint_right_data) 
WHERE fingerprint_right_data IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_person_fingerprint_left 
ON person(fingerprint_left_data) 
WHERE fingerprint_left_data IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_person_fingerprint_thumbs 
ON person(fingerprint_thumbs_data) 
WHERE fingerprint_thumbs_data IS NOT NULL;

-- 4. Index partiel pour les personnes avec empreintes (optimise with-fingerprints)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_person_has_any_fingerprint 
ON person(id, created_at DESC) 
WHERE fingerprint_right_data IS NOT NULL 
   OR fingerprint_left_data IS NOT NULL 
   OR fingerprint_thumbs_data IS NOT NULL;

-- 5. Index pour les requêtes de statistiques temporelles
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_person_created_date 
ON person(DATE(created_at));

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_person_created_month 
ON person(EXTRACT(YEAR FROM created_at), EXTRACT(MONTH FROM created_at));

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_person_created_week 
ON person(EXTRACT(YEAR FROM created_at), EXTRACT(WEEK FROM created_at));

-- 6. Index pour l'ordre par défaut des API (plus récents en premier)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_person_recent_first 
ON person(created_at DESC, id);

-- 7. Index pour la recherche textuelle (si nécessaire)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_person_name_lower 
ON person(LOWER(name));

\echo 'Index créés avec succès!'

-- Vérifier l'espace utilisé par les index
SELECT 
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes 
WHERE tablename = 'person'
ORDER BY pg_relation_size(indexrelid) DESC;

-- Analyser la table pour mettre à jour les statistiques
ANALYZE person;

\echo 'Optimisation terminée!'