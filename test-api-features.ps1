# Test complet des nouvelles fonctionnalités - API Face Recognition
# Version: 2.0.0-regions-final (CORRIGÉ)

param(
    [string]$ApiUrl = "http://localhost:5000",
    [switch]$Verbose
)

# Configuration
$headers = @{ "Content-Type" = "application/json" }
$testResults = @()

# Fonction pour afficher les résultats (CORRIGÉE)
function Write-TestResult {
    param($TestName, $Status, $Details = "", $ResponseTime = 0)
    
    $color = if ($Status -eq "PASS") { "Green" } else { "Red" }
    $symbol = if ($Status -eq "PASS") { "✅" } else { "❌" }
    
    Write-Host "$symbol $TestName" -ForegroundColor $color
    if ($Details) { Write-Host "   $Details" -ForegroundColor Gray }
    if ($ResponseTime -gt 0) { Write-Host "   Temps: ${ResponseTime}ms" -ForegroundColor Gray }
    
    # FIX: Utiliser un objet PSCustomObject au lieu d'un hashtable
    $script:testResults += [PSCustomObject]@{
        Test = $TestName
        Status = $Status
        Details = $Details
        ResponseTime = $ResponseTime
    }
}

# Fonction pour faire une requête HTTP
function Invoke-ApiTest {
    param($Method, $Endpoint, $Body = $null, $ExpectedStatus = 200)
    
    try {
        $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
        
        $params = @{
            Uri = "$ApiUrl$Endpoint"
            Method = $Method
            Headers = $headers
        }
        
        if ($Body) { $params.Body = $Body }
        
        $response = Invoke-RestMethod @params
        $stopwatch.Stop()
        
        return @{
            Success = $true
            Data = $response
            ResponseTime = $stopwatch.ElapsedMilliseconds
            StatusCode = 200
        }
    }
    catch {
        $stopwatch.Stop()
        $statusCode = if ($_.Exception.Response) { 
            $_.Exception.Response.StatusCode.Value__ 
        } else { 
            0 
        }
        
        return @{
            Success = $false
            Error = $_.Exception.Message
            ResponseTime = $stopwatch.ElapsedMilliseconds
            StatusCode = $statusCode
        }
    }
}

Write-Host "🚀 TEST COMPLET DES NOUVELLES FONCTIONNALITÉS" -ForegroundColor Cyan
Write-Host "API URL: $ApiUrl" -ForegroundColor Yellow
Write-Host "=" * 60

# TEST 1: Santé de l'API
Write-Host "`n📊 1. TESTS DE SANTÉ" -ForegroundColor Cyan
$result = Invoke-ApiTest "GET" "/api/health"
if ($result.Success) {
    Write-TestResult "Santé API" "PASS" "Version: $($result.Data.api_version)" $result.ResponseTime
} else {
    Write-TestResult "Santé API" "FAIL" $result.Error $result.ResponseTime
}

# TEST 2: Dashboard unifié - Toutes les sections
Write-Host "`n📈 2. TESTS DASHBOARD UNIFIÉ" -ForegroundColor Cyan

$dashboardTests = @(
    @{ Name = "Toutes les sections"; Endpoint = "/api/dashboard/stats" },
    @{ Name = "Section régions"; Endpoint = "/api/dashboard/stats?sections=regions" },
    @{ Name = "Régions avec détails"; Endpoint = "/api/dashboard/stats?sections=regions&region_details=true" },
    @{ Name = "Volumétrie + Démographie"; Endpoint = "/api/dashboard/stats?sections=volumetry,demographics" },
    @{ Name = "Activité récente"; Endpoint = "/api/dashboard/stats?sections=recent_activity" }
)

foreach ($test in $dashboardTests) {
    $result = Invoke-ApiTest "GET" $test.Endpoint
    if ($result.Success) {
        $sectionsCount = ($result.Data.PSObject.Properties.Name | Where-Object { $_ -ne "available_sections" -and $_ -ne "total_persons_in_database" }).Count
        Write-TestResult $test.Name "PASS" "$sectionsCount sections retournées" $result.ResponseTime
        
        if ($Verbose -and $test.Name -eq "Section régions") {
            Write-Host "   Régions disponibles: $($result.Data.regions.available_regions -join ', ')" -ForegroundColor Gray
            Write-Host "   Région par défaut: $($result.Data.regions.default_region)" -ForegroundColor Gray
        }
    } else {
        Write-TestResult $test.Name "FAIL" $result.Error $result.ResponseTime
    }
}

# TEST 3: Endpoints supprimés (doivent échouer)
Write-Host "`n❌ 3. TESTS ENDPOINTS SUPPRIMÉS (doivent échouer)" -ForegroundColor Cyan

$removedEndpoints = @(
    "/api/stats",
    "/api/regions", 
    "/api/regions/stats",
    "/api/analytics/duplicates"
)

foreach ($endpoint in $removedEndpoints) {
    $result = Invoke-ApiTest "GET" $endpoint
    if (!$result.Success -and $result.StatusCode -eq 404) {
        Write-TestResult "Endpoint supprimé: $endpoint" "PASS" "404 comme attendu" $result.ResponseTime
    } else {
        Write-TestResult "Endpoint supprimé: $endpoint" "FAIL" "Devrait retourner 404" $result.ResponseTime
    }
}

# TEST 4: Métadonnées mises à jour
Write-Host "`n📋 4. TESTS MÉTADONNÉES" -ForegroundColor Cyan

$result = Invoke-ApiTest "GET" "/api/metadata/fields"
if ($result.Success) {
    $hasRegions = $null -ne $result.Data.enums.regions
    $hasStatsEndpoint = $null -ne $result.Data.statistics_endpoint
    
    if ($hasRegions -and $hasStatsEndpoint) {
        Write-TestResult "Métadonnées des champs" "PASS" "Régions et stats endpoint inclus" $result.ResponseTime
        if ($Verbose) {
            Write-Host "   Endpoint stats: $($result.Data.statistics_endpoint)" -ForegroundColor Gray
            Write-Host "   Régions: $($result.Data.enums.regions.values -join ', ')" -ForegroundColor Gray
        }
    } else {
        Write-TestResult "Métadonnées des champs" "FAIL" "Données manquantes" $result.ResponseTime
    }
} else {
    Write-TestResult "Métadonnées des champs" "FAIL" $result.Error $result.ResponseTime
}

# TEST 5: Informations API
$result = Invoke-ApiTest "GET" "/api/info"
if ($result.Success) {
    $hasRemovedSection = $null -ne $result.Data.removed_endpoints
    $hasRegionsSupport = $null -ne $result.Data.regions_support
    
    if ($hasRemovedSection -and $hasRegionsSupport) {
        Write-TestResult "Informations API" "PASS" "Version: $($result.Data.api_version)" $result.ResponseTime
        if ($Verbose) {
            Write-Host "   Endpoints supprimés: $($result.Data.removed_endpoints.removed.Count)" -ForegroundColor Gray
        }
    } else {
        Write-TestResult "Informations API" "FAIL" "Sections manquantes" $result.ResponseTime
    }
} else {
    Write-TestResult "Informations API" "FAIL" $result.Error $result.ResponseTime
}

# TEST 6: Support des régions dans les personnes
Write-Host "`n🗺️ 5. TESTS SUPPORT RÉGIONS" -ForegroundColor Cyan

# Test filtrage par région
$result = Invoke-ApiTest "GET" "/api/persons?region=Djibouti&limit=1"
if ($result.Success) {
    Write-TestResult "Filtrage par région" "PASS" "Endpoint fonctionnel" $result.ResponseTime
} else {
    Write-TestResult "Filtrage par région" "FAIL" $result.Error $result.ResponseTime
}

# Test recherche avec région
$result = Invoke-ApiTest "GET" "/api/persons?q=test&region=Djibouti&limit=1"
if ($result.Success) {
    Write-TestResult "Recherche avec région" "PASS" "Endpoint fonctionnel" $result.ResponseTime
} else {
    Write-TestResult "Recherche avec région" "FAIL" $result.Error $result.ResponseTime
}

# TEST 7: Performance comparative
Write-Host "`n⚡ 6. TESTS DE PERFORMANCE" -ForegroundColor Cyan

# Test dashboard complet
$result = Invoke-ApiTest "GET" "/api/dashboard/stats"
if ($result.Success) {
    $perfStatus = if ($result.ResponseTime -lt 1000) { "PASS" } else { "FAIL" }
    $perfMessage = if ($result.ResponseTime -lt 1000) { "Performance acceptable" } else { "Performance lente (>1s)" }
    Write-TestResult "Performance dashboard" $perfStatus $perfMessage $result.ResponseTime
}

# Test section régions seule
$result = Invoke-ApiTest "GET" "/api/dashboard/stats?sections=regions"
if ($result.Success) {
    $perfStatus = if ($result.ResponseTime -lt 500) { "PASS" } else { "FAIL" }
    $perfMessage = if ($result.ResponseTime -lt 500) { "Section rapide" } else { "Section lente (>500ms)" }
    Write-TestResult "Performance section régions" $perfStatus $perfMessage $result.ResponseTime
}

# RÉSUMÉ FINAL (CORRIGÉ)
Write-Host "`n" + "=" * 60
Write-Host "📊 RÉSUMÉ DES TESTS" -ForegroundColor Cyan

$totalTests = $testResults.Count
$passedTests = ($testResults | Where-Object { $_.Status -eq "PASS" }).Count
$failedTests = $totalTests - $passedTests

# FIX: Vérifier division par zéro
if ($totalTests -gt 0) {
    $successRate = [math]::Round(($passedTests / $totalTests) * 100, 1)
} else {
    $successRate = 0
}

Write-Host "Total des tests: $totalTests" -ForegroundColor White
Write-Host "✅ Réussis: $passedTests" -ForegroundColor Green
Write-Host "❌ Échoués: $failedTests" -ForegroundColor Red
Write-Host "📈 Taux de réussite: $successRate%" -ForegroundColor $(if ($successRate -ge 80) { "Green" } else { "Red" })

# Temps de réponse moyen
$responseTimes = $testResults | Where-Object { $_.ResponseTime -gt 0 } | Select-Object -ExpandProperty ResponseTime
if ($responseTimes.Count -gt 0) {
    $avgResponseTime = [math]::Round(($responseTimes | Measure-Object -Average).Average, 0)
    Write-Host "⚡ Temps de réponse moyen: ${avgResponseTime}ms" -ForegroundColor Yellow
}

# Tests échoués en détail
if ($failedTests -gt 0) {
    Write-Host "`n❌ TESTS ÉCHOUÉS:" -ForegroundColor Red
    $testResults | Where-Object { $_.Status -eq "FAIL" } | ForEach-Object {
        Write-Host "  - $($_.Test): $($_.Details)" -ForegroundColor Red
    }
}

Write-Host "`n🎉 Tests terminés!" -ForegroundColor Cyan

# Retourner le code d'erreur approprié
if ($failedTests -eq 0) {
    Write-Host "✅ Tous les tests sont passés avec succès!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "⚠️ Certains tests ont échoué. Vérifiez les erreurs ci-dessus." -ForegroundColor Yellow
    exit 1
}