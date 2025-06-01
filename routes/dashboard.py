# routes/dashboard.py
from flask import Blueprint, jsonify, current_app, request
from sqlalchemy import func, cast, Date, extract
from datetime import datetime, timedelta
import os
import json
import logging
from models.database import db
from models.person import Person

logger = logging.getLogger(__name__)

# Créer le Blueprint
dashboard = Blueprint('dashboard', __name__)

# Fonction pour créer un journal d'activité (pour tracer les identifications)
def log_identification(person_id=None, success=None, details=None):
    """
    Enregistre une activité d'identification dans un journal JSON
    
    Args:
        person_id: ID de la personne identifiée (optionnel)
        success: Si l'identification a réussi
        details: Détails supplémentaires (optionnel)
    """
    log_dir = current_app.config.get('LOG_DIR', 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    log_file = os.path.join(log_dir, 'identification_log.json')
    
    # Créer l'entrée de journal
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'activity_type': 'identification',
        'person_id': person_id,
        'success': success,
        'details': details
    }
    
    # Charger le journal existant ou créer un nouveau
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                logs = json.load(f)
        except Exception as e:
            logger.error(f"Erreur lors de la lecture du journal d'identification: {e}")
            logs = {'logs': []}
    else:
        logs = {'logs': []}
    
    # Ajouter la nouvelle entrée
    logs['logs'].append(log_entry)
    
    # Limiter la taille du journal (garder les 10000 dernières entrées)
    if len(logs['logs']) > 10000:
        logs['logs'] = logs['logs'][-10000:]
    
    # Enregistrer le journal
    try:
        with open(log_file, 'w') as f:
            json.dump(logs, f)
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement du journal d'identification: {e}")

# Fonction pour lire le journal d'identification
def get_identification_logs(days=None):
    """
    Récupère les entrées du journal d'identification
    
    Args:
        days: Nombre de jours à considérer (optionnel)
        
    Returns:
        list: Liste des entrées du journal
    """
    log_dir = current_app.config.get('LOG_DIR', 'logs')
    log_file = os.path.join(log_dir, 'identification_log.json')
    
    if not os.path.exists(log_file):
        return []
    
    try:
        with open(log_file, 'r') as f:
            logs = json.load(f)
    except Exception as e:
        logger.error(f"Erreur lors de la lecture du journal d'identification: {e}")
        return []
    
    entries = logs.get('logs', [])
    
    # Filtrer par date
    if days:
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
        entries = [entry for entry in entries if entry.get('timestamp') >= cutoff_date]
    
    return entries

@dashboard.route('/stats', methods=['GET'])
def get_stats():
    """
    Endpoint pour récupérer les statistiques du tableau de bord de manière flexible (CORRIGÉ)
    """
    try:
        # Sections demandées
        requested_sections = request.args.get('sections', 'all')
        
        if requested_sections.lower() == 'all':
            sections = ['volumetry', 'recent_activity', 'registration_evolution', 'demographics']
        else:
            sections = [s.strip() for s in requested_sections.split(',')]
        
        # Dictionnaire pour les statistiques
        stats = {}
        
        # Obtenir les dates de référence
        now = datetime.utcnow()
        
        # 1. Volumétrie (inchangé - semble correct)
        if 'volumetry' in sections:
            total_persons = Person.query.count()
            
            total_size_query = db.session.query(
                func.coalesce(func.sum(func.length(Person.photo_data)), 0) +
                func.coalesce(func.sum(func.length(Person.fingerprint_right_data)), 0) +
                func.coalesce(func.sum(func.length(Person.fingerprint_left_data)), 0) +
                func.coalesce(func.sum(func.length(Person.fingerprint_thumbs_data)), 0)
            ).scalar()
            
            total_size_mb = round((total_size_query or 0) / (1024 * 1024), 2)
            
            persons_with_fingerprints = Person.query.filter(
                db.or_(
                    Person.fingerprint_right_data.isnot(None),
                    Person.fingerprint_left_data.isnot(None),
                    Person.fingerprint_thumbs_data.isnot(None)
                )
            ).count()
            
            persons_without_fingerprints = total_persons - persons_with_fingerprints
            
            stats['volumetry'] = {
                "total_persons": total_persons,
                "persons_with_fingerprints": persons_with_fingerprints,
                "persons_without_fingerprints": persons_without_fingerprints,
                "total_biometric_size_mb": total_size_mb
            }
        
        # 2. Activité récente (inchangé - semble correct)
        if 'recent_activity' in sections:
            yesterday = now - timedelta(days=1)
            last_week = now - timedelta(days=7)
            last_month = now - timedelta(days=30)
            
            persons_last_24h = Person.query.filter(Person.created_at >= yesterday).count()
            persons_last_7d = Person.query.filter(Person.created_at >= last_week).count()
            persons_last_30d = Person.query.filter(Person.created_at >= last_month).count()
            
            identifications_24h = get_identification_logs(1)
            identifications_7d = get_identification_logs(7)
            identifications_30d = get_identification_logs(30)
            
            successful_identifications_24h = len([i for i in identifications_24h if i.get('success')])
            successful_identifications_7d = len([i for i in identifications_7d if i.get('success')])
            successful_identifications_30d = len([i for i in identifications_30d if i.get('success')])
            
            failed_identifications_24h = len([i for i in identifications_24h if i.get('success') is False])
            failed_identifications_7d = len([i for i in identifications_7d if i.get('success') is False])
            failed_identifications_30d = len([i for i in identifications_30d if i.get('success') is False])
            
            stats['recent_activity'] = {
                "new_persons": {
                    "last_24h": persons_last_24h,
                    "last_7d": persons_last_7d,
                    "last_30d": persons_last_30d
                },
                "successful_identifications": {
                    "last_24h": successful_identifications_24h,
                    "last_7d": successful_identifications_7d,
                    "last_30d": successful_identifications_30d
                },
                "failed_identifications": {
                    "last_24h": failed_identifications_24h,
                    "last_7d": failed_identifications_7d,
                    "last_30d": failed_identifications_30d
                }
            }
        
        # 3. Évolution des inscriptions dans le temps (CORRIGÉ)
        if 'registration_evolution' in sections:
            # Par jour (derniers 30 jours) - CORRECT
            registrations_by_day = []
            for i in range(30, -1, -1):
                date = now - timedelta(days=i)
                date_str = date.strftime('%Y-%m-%d')
                
                day_start = datetime(date.year, date.month, date.day, 0, 0, 0)
                day_end = datetime(date.year, date.month, date.day, 23, 59, 59)
                
                count = Person.query.filter(
                    Person.created_at >= day_start,
                    Person.created_at <= day_end
                ).count()
                
                registrations_by_day.append({
                    "date": date_str,
                    "count": count
                })
            
            # Par semaine (8 dernières semaines) - CORRIGÉ
            registrations_by_week = []
            for i in range(7, -1, -1):  # Changé de range(8) à range(7, -1, -1)
                week_end = now - timedelta(weeks=i)
                week_start = week_end - timedelta(days=7)
                
                # Obtenir le numéro de semaine ISO pour la fin de semaine
                week_num = week_end.isocalendar()[1]
                year = week_end.isocalendar()[0]
                
                count = Person.query.filter(
                    Person.created_at >= week_start,
                    Person.created_at < week_end
                ).count()
                
                registrations_by_week.append({
                    "week": f"W{week_num} {year}",
                    "count": count
                })
            
            # Par mois (12 derniers mois) - COMPLÈTEMENT CORRIGÉ
            registrations_by_month = []
            
            # Générer les 12 derniers mois de façon correcte
            for i in range(11, -1, -1):  # De 11 à 0 (12 mois)
                # Calculer le mois cible
                target_month = now.month - i
                target_year = now.year
                
                # Gérer le passage d'année
                while target_month <= 0:
                    target_month += 12
                    target_year -= 1
                
                # Premier jour du mois
                first_day = datetime(target_year, target_month, 1)
                
                # Premier jour du mois suivant
                if target_month == 12:
                    next_month_first = datetime(target_year + 1, 1, 1)
                else:
                    next_month_first = datetime(target_year, target_month + 1, 1)
                
                # Compter les personnes de ce mois
                count = Person.query.filter(
                    Person.created_at >= first_day,
                    Person.created_at < next_month_first
                ).count()
                
                # Formater le nom du mois
                month_name = first_day.strftime('%B %Y')
                
                registrations_by_month.append({
                    "month": month_name,
                    "count": count
                })
            
            stats['registration_evolution'] = {
                "daily": registrations_by_day,
                "weekly": registrations_by_week,
                "monthly": registrations_by_month
            }
        
        # 4. Données démographiques (inchangé - semble correct)
        if 'demographics' in sections:
            gender_distribution = db.session.query(
                Person.gender, func.count(Person.id)
            ).group_by(Person.gender).all()
            
            gender_stats = {gender: count for gender, count in gender_distribution}
            
            nationality_distribution = db.session.query(
                Person.nationality, func.count(Person.id)
            ).group_by(Person.nationality).order_by(func.count(Person.id).desc()).limit(10).all()
            
            top_nationalities = [
                {"nationality": nationality, "count": count}
                for nationality, count in nationality_distribution
            ]
            
            age_groups = {
                "0-18": Person.query.filter(Person.age <= 18).count(),
                "19-30": Person.query.filter(Person.age > 18, Person.age <= 30).count(),
                "31-45": Person.query.filter(Person.age > 30, Person.age <= 45).count(),
                "46-60": Person.query.filter(Person.age > 45, Person.age <= 60).count(),
                "60+": Person.query.filter(Person.age > 60).count()
            }
            
            stats['demographics'] = {
                "gender_distribution": gender_stats,
                "top_nationalities": top_nationalities,
                "age_groups": age_groups,
                "total_count": Person.query.count()
            }
        
        # Informations sur les sections disponibles
        stats['available_sections'] = [
            'volumetry', 'recent_activity', 'registration_evolution', 'demographics'
        ]
        
        # Vérification générale
        stats['total_persons_in_database'] = Person.query.count()
        
        return jsonify(stats), 200
        
    except Exception as e:
        logger.error(f"Erreur lors de la génération des statistiques: {e}")
        return jsonify({"error": f"Erreur interne du serveur: {str(e)}"}), 500