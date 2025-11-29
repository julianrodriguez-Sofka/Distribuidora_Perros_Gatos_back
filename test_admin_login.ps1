# Script para probar el login del administrador
# Uso: .\test_admin_login.ps1

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "  TEST LOGIN ADMINISTRADOR" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

$apiUrl = "http://localhost:8000/api/auth/login"
$email = "admin@distribuidora.com"
$password = "Admin@2024"

$body = @{
    email = $email
    password = $password
} | ConvertTo-Json

Write-Host "Credenciales utilizadas:" -ForegroundColor Yellow
Write-Host "  Email: $email" -ForegroundColor White
Write-Host "  Password: $password" -ForegroundColor White
Write-Host ""

Write-Host "Enviando petición a: $apiUrl" -ForegroundColor Yellow
Write-Host ""

try {
    $response = Invoke-RestMethod -Uri $apiUrl -Method Post -Body $body -ContentType "application/json"
    
    Write-Host "✅ LOGIN EXITOSO!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Respuesta:" -ForegroundColor Cyan
    Write-Host "  Status: $($response.status)" -ForegroundColor White
    Write-Host "  Message: $($response.message)" -ForegroundColor White
    Write-Host ""
    Write-Host "Token de Acceso:" -ForegroundColor Cyan
    Write-Host "  $($response.access_token)" -ForegroundColor Gray
    Write-Host ""
    
    # Guardar el token en un archivo para uso posterior
    $response.access_token | Out-File -FilePath "admin_token.txt" -NoNewline
    Write-Host "✅ Token guardado en: admin_token.txt" -ForegroundColor Green
    Write-Host ""
    
    # Probar el token obteniendo información del usuario
    Write-Host "Probando token con /api/auth/me..." -ForegroundColor Yellow
    $meUrl = "http://localhost:8000/api/auth/me"
    $headers = @{
        "Authorization" = "Bearer $($response.access_token)"
    }
    
    $meResponse = Invoke-RestMethod -Uri $meUrl -Method Get -Headers $headers
    
    Write-Host "✅ Token válido!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Información del usuario:" -ForegroundColor Cyan
    Write-Host "  ID: $($meResponse.id)" -ForegroundColor White
    Write-Host "  Nombre: $($meResponse.nombre_completo)" -ForegroundColor White
    Write-Host "  Email: $($meResponse.email)" -ForegroundColor White
    Write-Host "  Rol: $($meResponse.rol)" -ForegroundColor White
    Write-Host ""
    
    if ($meResponse.rol -eq "admin") {
        Write-Host "✅ CONFIRMADO: Usuario con permisos de ADMINISTRADOR" -ForegroundColor Green
    } else {
        Write-Host "⚠️  ADVERTENCIA: Usuario NO tiene permisos de administrador" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "❌ ERROR al hacer login" -ForegroundColor Red
    Write-Host ""
    Write-Host "Detalles del error:" -ForegroundColor Yellow
    Write-Host $_.Exception.Message -ForegroundColor Red
    
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $reader.BaseStream.Position = 0
        $reader.DiscardBufferedData()
        $responseBody = $reader.ReadToEnd()
        Write-Host ""
        Write-Host "Respuesta del servidor:" -ForegroundColor Yellow
        Write-Host $responseBody -ForegroundColor Red
    }
    
    Write-Host ""
    Write-Host "Posibles causas:" -ForegroundColor Yellow
    Write-Host "  1. La API no está corriendo (verifica con: docker ps)" -ForegroundColor White
    Write-Host "  2. El puerto 8000 no está disponible" -ForegroundColor White
    Write-Host "  3. El usuario administrador no fue creado correctamente" -ForegroundColor White
    Write-Host ""
    Write-Host "Para verificar el estado de los contenedores:" -ForegroundColor Cyan
    Write-Host "  docker ps" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Para ver los logs de la API:" -ForegroundColor Cyan
    Write-Host "  docker logs distribuidora-api" -ForegroundColor Gray
}

Write-Host ""
Write-Host "==================================" -ForegroundColor Cyan
