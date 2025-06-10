# Test Dashboard Régional - API Face Recognition
# ================================================

Write-Host "🧪 TEST DASHBOARD RÉGIONAL - API Face Recognition" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

$BaseUrl = "http://localhost:5000/api/dashboard/stats"

# Fonction pour tester un endpoint
function Test-Endpoint {
    param(
        [string]$TestName,
        [string]$Url
    )
    
    Write-Host "🔍 Test: $TestName" -ForegroundColor Yellow
    Write-Host "URL: $Url" -ForegroundColor Gray
    Write-Host "---"
    
    try {
        $response = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 10
        Write-Host "✅ SUCCESS" -ForegroundColor Green
        
        # Afficher les informations clés
        if ($response.regional_dashboard) {
            $region = $response.regional_dashboard.filtered_by_region
            if ($region) {
                Write-Host "📊 Région filtrée: $region" -ForegroundColor White
            } else {
                Write-Host "📊 Mode: National" -ForegroundColor White
            }
        }
        
        # Afficher les sections disponibles
        $sections = @()
        if ($response.volumetry) { $sections += "volumetry" }
        if ($response.recent_activity) { $sections += "recent_activity" }
        if ($response.registration_evolution) { $sections += "registration_evolution" }
        if ($response.demographics) { $sections += "demographics" }
        if ($response.regions) { $sections += "regions" }
        
        if ($sections.Count -gt 0) {
            Write-Host "📈 Sections: $($sections -join ', ')" -ForegroundColor White
        }
        
        # Afficher des métriques spécifiques selon la section
        if ($response.volumetry) {
            Write-Host "👥 Total personnes: $($response.volumetry.total_persons)" -ForegroundColor White
        }
        
        if ($response.recent_activity) {
            Write-Host "📅 Nouvelles (30j): $($response.recent_activity.new_persons.last_30d)" -ForegroundColor White
            if ($response.recent_activity.comparisons) {
                Write-Host "🔄 Comparaisons incluses" -ForegroundColor Magenta
            }
        }
        
        if ($response.demographics) {
            Write-Host "🎯 Âge moyen: $($response.demographics.age_statistics.average_age)" -ForegroundColor White
        }
        
        if ($response.regions) {
            Write-Host "🗺️  Mode régional: $($response.regions.mode)" -ForegroundColor White
        }
        
    } catch {
        $statusCode = "Unknown"
        if ($_.Exception.Response) {
            $statusCode = $_.Exception.Response.StatusCode.value__
        }
        Write-Host "❌ ERREUR (HTTP $statusCode)" -ForegroundColor Red
        
        # Essayer d'extraire le message d'erreur
        try {
            if ($_.ErrorDetails.Message) {
                $errorResponse = $_.ErrorDetails.Message | ConvertFrom-Json
                if ($errorResponse.error) {
                    Write-Host "💬 Message: $($errorResponse.error)" -ForegroundColor Red
                }
                if ($errorResponse.valid_regions) {
                    Write-Host "🌍 Régions valides: $($errorResponse.valid_regions -join ', ')" -ForegroundColor Red
                }
            }
        } catch {
            Write-Host "💬 Erreur de connexion: $($_.Exception.Message)" -ForegroundColor Red
        }
    }
    
    Write-Host ""
    Write-Host "----------------------------------------" -ForegroundColor Gray
    Write-Host ""
}

# Tests principaux
Write-Host "🚀 Lancement des tests..." -ForegroundColor Green
Write-Host ""

Test-Endpoint "Volumétrie Djibouti" `
    "${BaseUrl}?region_filter=Djibouti&sections=volumetry"

Test-Endpoint "Activité Ali-Sabieh + Comparaisons" `
    "${BaseUrl}?region_filter=Ali-Sabieh&sections=recent_activity&include_comparisons=true"

Test-Endpoint "Évolution Dikhil" `
    "${BaseUrl}?region_filter=Dikhil&sections=registration_evolution"

Test-Endpoint "Démographie Tadjourah" `
    "${BaseUrl}?region_filter=Tadjourah&sections=demographics"

Test-Endpoint "Statistiques Obock" `
    "${BaseUrl}?region_filter=Obock&sections=regions"

# Test de validation d'erreur
Test-Endpoint "Test Région Invalide (doit échouer)" `
    "${BaseUrl}?region_filter=RegionInvalide&sections=volumetry"

# Test national pour comparaison
Test-Endpoint "Dashboard National (référence)" `
    "${BaseUrl}?sections=volumetry"

# Résumé final
Write-Host "🏁 TESTS TERMINÉS" -ForegroundColor Cyan
Write-Host ""
Write-Host "💡 Conseils:" -ForegroundColor Yellow
Write-Host "   - Vérifiez que les counts diffèrent entre régions" -ForegroundColor White
Write-Host "   - Les métadonnées 'filtered_by_region' doivent être présentes" -ForegroundColor White
Write-Host "   - Le test d'erreur doit retourner HTTP 400" -ForegroundColor White
Write-Host ""

# Test rapide de connectivité
Write-Host "🔗 Test de connectivité rapide..." -ForegroundColor Cyan
try {
    $healthCheck = Invoke-RestMethod -Uri "http://localhost:5000/health" -Method Get -TimeoutSec 5
    Write-Host "✅ API accessible - Status: $($healthCheck.status)" -ForegroundColor Green
} catch {
    Write-Host "❌ API non accessible - Vérifiez que le serveur est démarré" -ForegroundColor Red
}