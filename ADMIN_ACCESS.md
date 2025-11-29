# 🔑 Acceso Rápido - Usuario Administrador

## Credenciales de Administrador

```
Email:    admin@distribuidora.com
Password: Admin@2024
```

## ¿Cómo usar?

### 1. Iniciar sesión en el Frontend
Accede a `http://localhost:3000/login` e ingresa las credenciales.

### 2. Probar con el script de prueba
```powershell
.\test_admin_login.ps1
```

### 3. Usar la API directamente
```powershell
$response = Invoke-RestMethod -Uri "http://localhost:8000/api/auth/login" `
  -Method Post `
  -Body (@{email="admin@distribuidora.com"; password="Admin@2024"} | ConvertTo-Json) `
  -ContentType "application/json"

$response.access_token
```

## ¿Necesitas recrear el usuario?

```bash
docker exec -i distribuidora-api python /app/create_admin_user.py
```

---

📖 **Documentación completa:** Ver [CREDENCIALES_ADMIN.md](./CREDENCIALES_ADMIN.md)
