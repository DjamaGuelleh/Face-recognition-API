# routes/dashboard.py - Version étendue avec dashboard régional sélectif
from flask import Blueprint, jsonify, current_app, request
from sqlalchemy import func, cast, Date, extract, or_, and_
from datetime import datetime, timedelta
import os
import json
import logging
from models.database import db
from models.person import Person
from models.enums import RegionEnum

logger = logging.getLogger(__name__)

# Créer le Blueprint
dashboard = Blueprint('dashboard', __name__)

# Fonctions utilitaires inchangées
def log_identification(person_id=None, success=None, details=None):
    """
    Enregistre une activité d'identification dans un journal JSON
    """
    log_dir = current_app.config.get('LOG_DIR', 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    log_file = os.path.join(log_dir, 'identification_log.json')
    
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'activity_type': 'identification',
        'person_id': person_id,
        'success': success,
        'details': details
    }
    
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                logs = json.load(f)
        except Exception as e:
            logger.error(f"Erreur lors de la lecture du journal d'identification: {e}")
            logs = {'logs': []}
    else:
        logs = {'logs': []}
    
    logs['logs'].append(log_entry)
    
    if len(logs['logs']) > 10000:
        logs['logs'] = logs['logs'][-10000:]
    
    try:
        with open(log_file, 'w') as f:
            json.dump(logs, f)
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement du journal d'identification: {e}")

def get_identification_logs(days=None, region_filter=None):
    """
    Récupère les entrées du journal d'identification
    
    Args:
        days: Nombre de jours à considérer (optionnel)
        region_filter: Filtrer par région (optionnel - pour futures extensions)
        
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
    
    # Future extension: filtrer par région si person_id correspond à une région
    # if region_filter:
    #     filtered_entries = []
    #     for entry in entries:
    #         if entry.get('person_id'):
    #             person = Person.query.get(entry['person_id'])
    #             if person and person.region == region_filter:
    #                 filtered_entries.append(entry)
    #     entries = filtered_entries
    
    return entries

@dashboard.route('/stats', methods=['GET'])
def get_stats():
    """
    Endpoint pour récupérer les statistiques du tableau de bord
    NOUVEAU: Support du filtrage par région
    
    Query parameters:
    - sections: Sections demandées (par défaut: all)
      Valeurs possibles: volumetry,recent_activity,registration_evolution,demographics,regions
    - region_details: true/false (défaut: true) - Inclure les détails par région
    - region_filter: Nom de région pour filtrer toutes les stats par cette région
      Valeurs possibles: Djibouti, Arta, Ali-Sabieh, Dikhil, Tadjourah, Obock
    - include_comparisons: true/false (défaut: false) - Inclure comparaisons région vs national
    """
    try:
        # Paramètres existants
        requested_sections = request.args.get('sections', 'all')
        region_details = request.args.get('region_details', 'true').lower() in ('true', '1', 'yes')
        
        # NOUVEAUX paramètres pour le dashboard régional
        region_filter = request.args.get('region_filter', '').strip()
        include_comparisons = request.args.get('include_comparisons', 'false').lower() in ('true', '1', 'yes')
        
        # Validation du filtre régional
        if region_filter:
            valid_regions = RegionEnum.get_values()
            if region_filter not in valid_regions:
                return jsonify({
                    "error": f"Région invalide. Utilisez: {', '.join(valid_regions)}",
                    "valid_regions": valid_regions,
                    "region_filter_provided": region_filter
                }), 400
        
        if requested_sections.lower() == 'all':
            sections = ['volumetry', 'recent_activity', 'registration_evolution', 'demographics', 'regions']
        else:
            sections = [s.strip() for s in requested_sections.split(',')]
        
        # Dictionnaire pour les statistiques
        stats = {}
        
        # Obtenir les dates de référence
        now = datetime.utcnow()
        
        # Base query pour filtrage régional
        base_query = Person.query
        if region_filter:
            base_query = base_query.filter(Person.region == region_filter)
        
        # ================================================
        # 1. VOLUMÉTRIE (avec support régional)
        # ================================================
        if 'volumetry' in sections:
            # Statistiques de base (filtrées par région si demandé)
            total_persons = base_query.count()
            
            # Taille totale des données biométriques
            size_query = base_query.with_entities(
                func.coalesce(func.sum(func.length(Person.photo_data)), 0) +
                func.coalesce(func.sum(func.length(Person.fingerprint_right_data)), 0) +
                func.coalesce(func.sum(func.length(Person.fingerprint_left_data)), 0) +
                func.coalesce(func.sum(func.length(Person.fingerprint_thumbs_data)), 0)
            ).scalar()
            
            total_size_mb = round((size_query or 0) / (1024 * 1024), 2)
            
            # Personnes avec empreintes (dans la région si filtrée)
            persons_with_fingerprints = base_query.filter(
                or_(
                    Person.fingerprint_right_data.isnot(None),
                    Person.fingerprint_left_data.isnot(None),
                    Person.fingerprint_thumbs_data.isnot(None)
                )
            ).count()
            
            persons_without_fingerprints = total_persons - persons_with_fingerprints
            
            volumetry_data = {
                "total_persons": total_persons,
                "persons_with_fingerprints": persons_with_fingerprints,
                "persons_without_fingerprints": persons_without_fingerprints,
                "fingerprint_percentage": round((persons_with_fingerprints / total_persons * 100), 1) if total_persons > 0 else 0,
                "total_biometric_size_mb": total_size_mb
            }
            
            # Ajout des comparaisons si région filtrée et demandées
            if region_filter and include_comparisons:
                # Statistiques nationales pour comparaison
                national_total = Person.query.count()
                national_with_fingerprints = Person.query.filter(
                    or_(
                        Person.fingerprint_right_data.isnot(None),
                        Person.fingerprint_left_data.isnot(None),
                        Person.fingerprint_thumbs_data.isnot(None)
                    )
                ).count()
                
                volumetry_data["comparisons"] = {
                    "region_percentage_of_national": round((total_persons / national_total * 100), 2) if national_total > 0 else 0,
                    "national_total_persons": national_total,
                    "national_fingerprint_percentage": round((national_with_fingerprints / national_total * 100), 1) if national_total > 0 else 0,
                    "region_vs_national_fingerprint_rate": round((volumetry_data["fingerprint_percentage"] - (national_with_fingerprints / national_total * 100)), 1) if national_total > 0 else 0
                }
            
            # Ajout des métadonnées régionales
            if region_filter:
                volumetry_data["filtered_by_region"] = region_filter
                volumetry_data["region_scope"] = "single_region"
            else:
                volumetry_data["region_scope"] = "national"
            
            stats['volumetry'] = volumetry_data
        
        # ================================================
        # 2. ACTIVITÉ RÉCENTE (avec support régional)
        # ================================================
        if 'recent_activity' in sections:
            yesterday = now - timedelta(days=1)
            last_week = now - timedelta(days=7)
            last_month = now - timedelta(days=30)
            
            # Nouvelles personnes (filtrées par région)
            persons_last_24h = base_query.filter(Person.created_at >= yesterday).count()
            persons_last_7d = base_query.filter(Person.created_at >= last_week).count()
            persons_last_30d = base_query.filter(Person.created_at >= last_month).count()
            
            # Identifications (global pour le moment, peut être étendu pour filtrer par région)
            identifications_24h = get_identification_logs(1)
            identifications_7d = get_identification_logs(7)
            identifications_30d = get_identification_logs(30)
            
            successful_identifications_24h = len([i for i in identifications_24h if i.get('success')])
            successful_identifications_7d = len([i for i in identifications_7d if i.get('success')])
            successful_identifications_30d = len([i for i in identifications_30d if i.get('success')])
            
            failed_identifications_24h = len([i for i in identifications_24h if i.get('success') is False])
            failed_identifications_7d = len([i for i in identifications_7d if i.get('success') is False])
            failed_identifications_30d = len([i for i in identifications_30d if i.get('success') is False])
            
            activity_data = {
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
                },
                "total_identifications": {
                    "last_24h": len(identifications_24h),
                    "last_7d": len(identifications_7d),
                    "last_30d": len(identifications_30d)
                }
            }
            
            # Comparaisons régionales
            if region_filter and include_comparisons:
                # Activité nationale pour comparaison
                national_last_30d = Person.query.filter(Person.created_at >= last_month).count()
                
                activity_data["comparisons"] = {
                    "national_new_persons_last_30d": national_last_30d,
                    "region_percentage_of_national_activity": round((persons_last_30d / national_last_30d * 100), 2) if national_last_30d > 0 else 0
                }
            
            # Métadonnées
            if region_filter:
                activity_data["filtered_by_region"] = region_filter
                activity_data["note"] = "Identifications sont globales (non filtrées par région)"
            
            stats['recent_activity'] = activity_data
        
        # ================================================
        # 3. ÉVOLUTION DES INSCRIPTIONS (avec support régional)
        # ================================================
        if 'registration_evolution' in sections:
            evolution_data = {}
            
            # Par jour (derniers 30 jours) - avec filtre régional
            registrations_by_day = []
            for i in range(30, -1, -1):
                date = now - timedelta(days=i)
                date_str = date.strftime('%Y-%m-%d')
                
                day_start = datetime(date.year, date.month, date.day, 0, 0, 0)
                day_end = datetime(date.year, date.month, date.day, 23, 59, 59)
                
                day_query = base_query.filter(
                    Person.created_at >= day_start,
                    Person.created_at <= day_end
                )
                count = day_query.count()
                
                registrations_by_day.append({
                    "date": date_str,
                    "count": count
                })
            
            # Par semaine (8 dernières semaines) - avec filtre régional
            registrations_by_week = []
            for i in range(7, -1, -1):
                week_end = now - timedelta(weeks=i)
                week_start = week_end - timedelta(days=7)
                
                week_num = week_end.isocalendar()[1]
                year = week_end.isocalendar()[0]
                
                week_query = base_query.filter(
                    Person.created_at >= week_start,
                    Person.created_at < week_end
                )
                count = week_query.count()
                
                registrations_by_week.append({
                    "week": f"W{week_num} {year}",
                    "count": count
                })
            
            # Par mois (12 derniers mois) - avec filtre régional
            registrations_by_month = []
            for i in range(11, -1, -1):
                target_month = now.month - i
                target_year = now.year
                
                while target_month <= 0:
                    target_month += 12
                    target_year -= 1
                
                first_day = datetime(target_year, target_month, 1)
                
                if target_month == 12:
                    next_month_first = datetime(target_year + 1, 1, 1)
                else:
                    next_month_first = datetime(target_year, target_month + 1, 1)
                
                month_query = base_query.filter(
                    Person.created_at >= first_day,
                    Person.created_at < next_month_first
                )
                count = month_query.count()
                
                month_name = first_day.strftime('%B %Y')
                
                registrations_by_month.append({
                    "month": month_name,
                    "count": count
                })
            
            evolution_data = {
                "daily": registrations_by_day,
                "weekly": registrations_by_week,
                "monthly": registrations_by_month
            }
            
            # Calculs de croissance pour la région
            if region_filter:
                # Croissance mensuelle dans la région
                current_month_count = registrations_by_month[-1]["count"] if registrations_by_month else 0
                previous_month_count = registrations_by_month[-2]["count"] if len(registrations_by_month) > 1 else 0
                
                if previous_month_count > 0:
                    monthly_growth_rate = round(((current_month_count - previous_month_count) / previous_month_count) * 100, 1)
                else:
                    monthly_growth_rate = 0
                
                evolution_data["regional_metrics"] = {
                    "monthly_growth_rate_percentage": monthly_growth_rate,
                    "current_month_registrations": current_month_count,
                    "previous_month_registrations": previous_month_count,
                    "filtered_by_region": region_filter
                }
            
            stats['registration_evolution'] = evolution_data
        
        # ================================================
        # 4. DONNÉES DÉMOGRAPHIQUES (avec support régional)
        # ================================================
        if 'demographics' in sections:
            # Distribution par genre (dans la région si filtrée)
            gender_distribution = db.session.query(
                Person.gender, func.count(Person.id)
            )
            if region_filter:
                gender_distribution = gender_distribution.filter(Person.region == region_filter)
            gender_distribution = gender_distribution.group_by(Person.gender).all()
            
            gender_stats = {gender: count for gender, count in gender_distribution}
            
            # Top nationalités (dans la région si filtrée)
            nationality_query = db.session.query(
                Person.nationality, func.count(Person.id)
            )
            if region_filter:
                nationality_query = nationality_query.filter(Person.region == region_filter)
            nationality_distribution = nationality_query.group_by(Person.nationality).order_by(func.count(Person.id).desc()).limit(10).all()
            
            top_nationalities = [
                {"nationality": nationality, "count": count}
                for nationality, count in nationality_distribution
            ]
            
            # Groupes d'âge (dans la région si filtrée)
            age_groups = {
                "0-18": base_query.filter(Person.age <= 18).count(),
                "19-30": base_query.filter(Person.age > 18, Person.age <= 30).count(),
                "31-45": base_query.filter(Person.age > 30, Person.age <= 45).count(),
                "46-60": base_query.filter(Person.age > 45, Person.age <= 60).count(),
                "60+": base_query.filter(Person.age > 60).count()
            }
            
            # Statistiques d'âge avancées
            age_stats_query = db.session.query(
                func.avg(Person.age).label('avg_age'),
                func.min(Person.age).label('min_age'),
                func.max(Person.age).label('max_age')
            )
            if region_filter:
                age_stats_query = age_stats_query.filter(Person.region == region_filter)
            age_stats = age_stats_query.first()
            
            demographics_data = {
                "gender_distribution": gender_stats,
                "top_nationalities": top_nationalities,
                "age_groups": age_groups,
                "age_statistics": {
                    "average_age": round(age_stats.avg_age, 1) if age_stats.avg_age else 0,
                    "min_age": age_stats.min_age or 0,
                    "max_age": age_stats.max_age or 0
                },
                "total_count": base_query.count()
            }
            
            # Métadonnées régionales
            if region_filter:
                demographics_data["filtered_by_region"] = region_filter
                demographics_data["scope"] = f"Demographics for {region_filter} region only"
            else:
                demographics_data["scope"] = "National demographics"
            
            stats['demographics'] = demographics_data
        
        # ================================================
        # 5. STATISTIQUES RÉGIONALES (modifiées selon le contexte)
        # ================================================
        if 'regions' in sections:
            if region_filter:
                # Si une région est filtrée, montrer les détails de cette région + comparaisons
                region_stats = db.session.query(
                    Person.region,
                    func.count(Person.id).label('count')
                ).group_by(Person.region).all()
                
                # Distribution complète pour contexte
                region_distribution = {stat.region: stat.count for stat in region_stats}
                all_regions = RegionEnum.get_values()
                for region in all_regions:
                    if region not in region_distribution:
                        region_distribution[region] = 0
                
                total_persons_national = sum(region_distribution.values())
                
                # Focus sur la région sélectionnée
                selected_region_count = region_distribution.get(region_filter, 0)
                
                regions_data = {
                    "selected_region": {
                        "name": region_filter,
                        "count": selected_region_count,
                        "percentage_of_national": round((selected_region_count / total_persons_national * 100), 2) if total_persons_national > 0 else 0
                    },
                    "context": {
                        "national_distribution": region_distribution,
                        "total_persons_national": total_persons_national,
                        "available_regions": all_regions
                    },
                    "mode": "regional_focus"
                }
                
                # Détails de la région sélectionnée si demandés
                if region_details and selected_region_count > 0:
                    # Statistiques détaillées pour la région sélectionnée
                    region_persons = Person.query.filter_by(region=region_filter)
                    
                    gender_in_region = db.session.query(
                        Person.gender, func.count(Person.id)
                    ).filter_by(region=region_filter).group_by(Person.gender).all()
                    
                    avg_age_in_region = db.session.query(
                        func.avg(Person.age)
                    ).filter_by(region=region_filter).scalar()
                    
                    nationalities_in_region = db.session.query(
                        Person.nationality, func.count(Person.id)
                    ).filter_by(region=region_filter).group_by(Person.nationality).order_by(
                        func.count(Person.id).desc()
                    ).limit(5).all()
                    
                    fingerprints_in_region = region_persons.filter(
                        or_(
                            Person.fingerprint_right_data.isnot(None),
                            Person.fingerprint_left_data.isnot(None),
                            Person.fingerprint_thumbs_data.isnot(None)
                        )
                    ).count()
                    
                    first_day_month = datetime(now.year, now.month, 1)
                    new_this_month_region = region_persons.filter(
                        Person.created_at >= first_day_month
                    ).count()
                    
                    regions_data["selected_region"]["details"] = {
                        "gender_distribution": dict(gender_in_region),
                        "average_age": round(avg_age_in_region, 1) if avg_age_in_region else 0,
                        "top_nationalities": [
                            {"nationality": nat, "count": count} 
                            for nat, count in nationalities_in_region
                        ],
                        "persons_with_fingerprints": fingerprints_in_region,
                        "fingerprint_percentage": round((fingerprints_in_region / selected_region_count * 100), 1) if selected_region_count > 0 else 0,
                        "new_this_month": new_this_month_region
                    }
            else:
                # Mode normal - toutes les régions
                region_stats = db.session.query(
                    Person.region,
                    func.count(Person.id).label('count')
                ).group_by(Person.region).all()
                
                region_distribution = {stat.region: stat.count for stat in region_stats}
                all_regions = RegionEnum.get_values()
                for region in all_regions:
                    if region not in region_distribution:
                        region_distribution[region] = 0
                
                total_persons = sum(region_distribution.values())
                
                region_percentages = {}
                if total_persons > 0:
                    region_percentages = {
                        region: round((count / total_persons * 100), 2) 
                        for region, count in region_distribution.items()
                    }
                
                regions_data = {
                    "distribution": region_distribution,
                    "percentages": region_percentages,
                    "total_persons": total_persons,
                    "regions_with_data": len([count for count in region_distribution.values() if count > 0]),
                    "available_regions": all_regions,
                    "default_region": RegionEnum.get_default(),
                    "mode": "national_overview"
                }
                
                # Détails pour toutes les régions si demandés
                if region_details:
                    region_details_data = {}
                    
                    for region in all_regions:
                        if region_distribution.get(region, 0) > 0:
                            region_persons = Person.query.filter_by(region=region)
                            
                            gender_in_region = db.session.query(
                                Person.gender, func.count(Person.id)
                            ).filter_by(region=region).group_by(Person.gender).all()
                            
                            avg_age_in_region = db.session.query(
                                func.avg(Person.age)
                            ).filter_by(region=region).scalar()
                            
                            nationalities_in_region = db.session.query(
                                Person.nationality, func.count(Person.id)
                            ).filter_by(region=region).group_by(Person.nationality).order_by(
                                func.count(Person.id).desc()
                            ).limit(5).all()
                            
                            fingerprints_in_region = region_persons.filter(
                                or_(
                                    Person.fingerprint_right_data.isnot(None),
                                    Person.fingerprint_left_data.isnot(None),
                                    Person.fingerprint_thumbs_data.isnot(None)
                                )
                            ).count()
                            
                            first_day_month = datetime(now.year, now.month, 1)
                            new_this_month_region = region_persons.filter(
                                Person.created_at >= first_day_month
                            ).count()
                            
                            region_details_data[region] = {
                                "total_count": region_distribution[region],
                                "gender_distribution": dict(gender_in_region),
                                "average_age": round(avg_age_in_region, 1) if avg_age_in_region else 0,
                                "top_nationalities": [
                                    {"nationality": nat, "count": count} 
                                    for nat, count in nationalities_in_region
                                ],
                                "persons_with_fingerprints": fingerprints_in_region,
                                "fingerprint_percentage": round((fingerprints_in_region / region_distribution[region] * 100), 1) if region_distribution[region] > 0 else 0,
                                "new_this_month": new_this_month_region
                            }
                    
                    regions_data['details'] = region_details_data
            
            stats['regions'] = regions_data
        
        # ================================================
        # MÉTADONNÉES DE LA RÉPONSE
        # ================================================
        
        stats['available_sections'] = [
            'volumetry', 'recent_activity', 'registration_evolution', 'demographics', 'regions'
        ]
        
        # Métadonnées spécifiques au filtrage régional
        if region_filter:
            stats['regional_dashboard'] = {
                "filtered_by_region": region_filter,
                "mode": "regional_dashboard",
                "all_sections_filtered": True,
                "comparisons_included": include_comparisons,
                "note": "Toutes les statistiques sont filtrées pour la région sélectionnée"
            }
        else:
            stats['regional_dashboard'] = {
                "mode": "national_dashboard",
                "filtered_by_region": None
            }
        
        stats['total_persons_in_database'] = Person.query.count()
        
        return jsonify(stats), 200
        
    except Exception as e:
        logger.error(f"Erreur lors de la génération des statistiques: {e}")
        return jsonify({"error": f"Erreur interne du serveur: {str(e)}"}), 500

