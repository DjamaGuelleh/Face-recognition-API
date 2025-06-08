-- optimize_database_complete_with_region_enum.sql
-- Script complet d'optimisation pour l'API Face Recognition
-- Version avec énumération des régions de Djibouti

\echo '========================================='
\echo '   OPTIMISATION COMPLETE BASE DE DONNEES'
\echo '    AVEC ENUMERATION DES REGIONS'
\echo '========================================='
\echo ''

-- 1. SUPPRESSION DES INDEX EXISTANTS (si besoin de refaire)
\echo '1. Nettoyage des anciens index...'
DROP INDEX IF EXISTS idx_person_created_at;
DROP INDEX IF EXISTS idx_person_updated_at;
DROP INDEX IF EXISTS idx_person_gender;
DROP INDEX IF EXISTS idx_person_nationality;
DROP INDEX IF EXISTS idx_person_region;
DROP INDEX IF EXISTS idx_person_age;
DROP INDEX IF EXISTS idx_person_gender_nationality;
DROP INDEX IF EXISTS idx_person_age_gender;
DROP INDEX IF EXISTS idx_person_created_gender;
DROP INDEX IF EXISTS idx_person_created_nationality;
DROP INDEX IF EXISTS idx_person_created_region;
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
DROP INDEX IF EXISTS idx_person_region_nationality;
DROP INDEX IF EXISTS idx_person_region_gender;
DROP INDEX IF EXISTS idx_person_nationality_region;
DROP INDEX IF EXISTS idx_person_region_lower;

\echo '   Anciens index supprimés'
\echo ''

-- 2. CREATION DES INDEX PRINCIPAUX
\echo '2. Création des index principaux...'

-- Index sur les colonnes de tri/filtrage (API standard)
CREATE INDEX idx_person_created_at ON person(created_at);
CREATE INDEX idx_person_updated_at ON person(updated_at);
CREATE INDEX idx_person_gender ON person(gender);
CREATE INDEX idx_person_nationality ON person(nationality);
CREATE INDEX idx_person_region ON person(region);  -- Index pour l'énumération des régions
CREATE INDEX idx_person_age ON person(age);

\echo '   ✓ Index principaux créés (avec énumération des régions)'

-- 3. INDEX COMPOSITES POUR DASHBOARD
\echo '3. Création des index composites pour dashboard...'

CREATE INDEX idx_person_gender_nationality ON person(gender, nationality);
CREATE INDEX idx_person_age_gender ON person(age, gender);
CREATE INDEX idx_person_created_gender ON person(created_at, gender);
CREATE INDEX idx_person_created_nationality ON person(created_at, nationality);
CREATE INDEX idx_person_created_region ON person(created_at, region);  -- Pour statistiques régionales

-- Index composites avec région (optimisés pour les 6 régions de Djibouti)
CREATE INDEX idx_person_region_nationality ON person(region, nationality);
CREATE INDEX idx_person_region_gender ON person(region, gender);
CREATE INDEX idx_person_nationality_region ON person(nationality, region);

\echo '   ✓ Index composites créés (avec régions de Djibouti)'

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

-- Index pour la recherche textuelle (noms et régions)
CREATE INDEX idx_person_name_lower ON person(LOWER(name));
CREATE INDEX idx_person_region_lower ON person(LOWER(region));

\echo '   ✓ Index de performance créés (avec régions)'

-- 7. INDEX SPECIFIQUES POUR LES REGIONS DE DJIBOUTI
\echo '7. Création des index spécifiques aux régions...'

-- Index partiel pour chaque région (optimisation pour les 6 régions)
CREATE INDEX idx_person_region_djibouti ON person(created_at, gender, nationality) WHERE region = 'Djibouti';
CREATE INDEX idx_person_region_arta ON person(created_at, gender, nationality) WHERE region = 'Arta';
CREATE INDEX idx_person_region_ali_sabieh ON person(created_at, gender, nationality) WHERE region = 'Ali-Sabieh';
CREATE INDEX idx_person_region_dikhil ON person(created_at, gender, nationality) WHERE region = 'Dikhil';
CREATE INDEX idx_person_region_tadjourah ON person(created_at, gender, nationality) WHERE region = 'Tadjourah';
CREATE INDEX idx_person_region_obock ON person(created_at, gender, nationality) WHERE region = 'Obock';

\echo '   ✓ Index partiels pour les 6 régions créés'

-- 8. OPTIMISATION DES STATISTIQUES
\echo '8. Optimisation des statistiques PostgreSQL...'

-- Augmenter les statistiques pour de meilleures optimisations
ALTER TABLE person ALTER COLUMN nationality SET STATISTICS 1000;
ALTER TABLE person ALTER COLUMN gender SET STATISTICS 1000;
ALTER TABLE person ALTER COLUMN region SET STATISTICS 1000;  -- Optimisé pour 6 régions
ALTER TABLE person ALTER COLUMN age SET STATISTICS 500;

-- Analyser la table pour mettre à jour les statistiques
ANALYZE person;

\echo '   ✓ Statistiques optimisées (avec régions)'

-- 9. VERIFICATION DES REGIONS
\echo '9. Vérification des régions dans la base de données...'

-- Afficher la distribution actuelle des régions
SELECT 
    region,
    COUNT(*) as nombre_personnes,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as pourcentage
FROM person 
GROUP BY region 
ORDER BY COUNT(*) DESC;

\echo ''
\echo 'Régions autorisées: Djibouti, Arta, Ali-Sabieh, Dikhil, Tadjourah, Obock'
\echo ''

-- 10. VERIFICATION DES INDEX
\echo '10. Vérification des index créés...'

SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes 
WHERE tablename = 'person' 
    AND indexname LIKE 'idx_person_%'
ORDER BY indexname;

\echo ''

-- 11. VERIFICATION DES PERFORMANCES
\echo '11. Test de performance des requêtes régionales...'

-- Test des requêtes par région
EXPLAIN (ANALYZE, BUFFERS) 
SELECT COUNT(*) FROM person WHERE region = 'Djibouti';

EXPLAIN (ANALYZE, BUFFERS) 
SELECT region, gender, COUNT(*) 
FROM person 
GROUP BY region, gender 
ORDER BY region;

\echo ''
\echo '========================================='
\echo '   OPTIMISATION TERMINEE AVEC SUCCES'
\echo '   Index créés pour les 6 régions'
\echo '   de Djibouti avec Djibouti par défaut'
\echo '========================================='-- optimize_database_complete_with_region.sql
-- Script complet d'optimisation pour l'API Face Recognition
-- Version avec support du champ région

\echo '========================================='
\echo '   OPTIMISATION COMPLETE BASE DE DONNEES'
\echo '          AVEC SUPPORT REGION'
\echo '========================================='
\echo ''

-- 1. SUPPRESSION DES INDEX EXISTANTS (si besoin de refaire)
\echo '1. Nettoyage des anciens index...'
DROP INDEX IF EXISTS idx_person_created_at;
DROP INDEX IF EXISTS idx_person_updated_at;
DROP INDEX IF EXISTS idx_person_gender;
DROP INDEX IF EXISTS idx_person_nationality;
DROP INDEX IF EXISTS idx_person_region;
DROP INDEX IF EXISTS idx_person_age;
DROP INDEX IF EXISTS idx_person_gender_nationality;
DROP INDEX IF EXISTS idx_person_age_gender;
DROP INDEX IF EXISTS idx_person_created_gender;
DROP INDEX IF EXISTS idx_person_created_nationality;
DROP INDEX IF EXISTS idx_person_created_region;
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
DROP INDEX IF EXISTS idx_person_region_nationality;
DROP INDEX IF EXISTS idx_person_region_gender;
DROP INDEX IF EXISTS idx_person_nationality_region;

\echo '   Anciens index supprimés'
\echo ''

-- 2. CREATION DES INDEX PRINCIPAUX
\echo '2. Création des index principaux...'

-- Index sur les colonnes de tri/filtrage (API standard)
CREATE INDEX idx_person_created_at ON person(created_at);
CREATE INDEX idx_person_updated_at ON person(updated_at);
CREATE INDEX idx_person_gender ON person(gender);
CREATE INDEX idx_person_nationality ON person(nationality);
CREATE INDEX idx_person_region ON person(region);  -- Nouvel index pour région
CREATE INDEX idx_person_age ON person(age);

\echo '   ✓ Index principaux créés (avec région)'

-- 3. INDEX COMPOSITES POUR DASHBOARD
\echo '3. Création des index composites pour dashboard...'

CREATE INDEX idx_person_gender_nationality ON person(gender, nationality);
CREATE INDEX idx_person_age_gender ON person(age, gender);
CREATE INDEX idx_person_created_gender ON person(created_at, gender);
CREATE INDEX idx_person_created_nationality ON person(created_at, nationality);
CREATE INDEX idx_person_created_region ON person(created_at, region);  -- Nouveau pour région

-- Index composites avec région
CREATE INDEX idx_person_region_nationality ON person(region, nationality);
CREATE INDEX idx_person_region_gender ON person(region, gender);
CREATE INDEX idx_person_nationality_region ON person(nationality, region);

\echo '   ✓ Index composites créés (avec région)'

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

-- Index pour la recherche textuelle (noms et régions)
CREATE INDEX idx_person_name_lower ON person(LOWER(name));
CREATE INDEX idx_person_region_lower ON person(LOWER(region));

\echo '   ✓ Index de performance créés (avec région)'

-- 7. OPTIMISATION DES STATISTIQUES
\echo '7. Optimisation des statistiques PostgreSQL...'

-- Augmenter les statistiques pour de meilleures optimisations
ALTER TABLE person ALTER COLUMN nationality SET STATISTICS 1000;
ALTER TABLE person ALTER COLUMN gender SET STATISTICS 1000;
ALTER TABLE person ALTER COLUMN region SET STATISTICS 1000;  -- Nouveau pour région
ALTER TABLE person ALTER COLUMN age SET STATISTICS 500;

-- Analyser la table pour mettre à jour les statistiques
ANALYZE person;

\echo '   ✓ Statistiques optimisées (avec région)'

-- 8. VERIFICATION DES INDEX
\echo '8. Vérification des index créés...'

SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes 
WHERE tablename = 'person' 
    AND indexname LIKE 'idx_person_%'
ORDER BY indexname;

\echo ''
\echo '========================================='
\echo '   OPTIMISATION TERMINEE AVEC SUCCES'
\echo '   Index créés pour le champ région'
\echo '========================================='