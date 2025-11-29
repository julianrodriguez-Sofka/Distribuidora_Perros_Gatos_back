# Credenciales de Administrador

## Usuario Administrador Predeterminado

Para acceder a la aplicación como administrador, utiliza las siguientes credenciales:

### Credenciales de Login

- **Email:** `admin@distribuidora.com`
- **Contraseña:** `Admin@2024`
- **Rol:** Administrador

### Características de la Cuenta

- ✅ Cuenta verificada (is_active = true)
- ✅ Permisos de administrador (es_admin = true)
- ✅ Acceso completo a todas las funcionalidades administrativas

### Endpoints Disponibles para Admin

Con estas credenciales puedes acceder a:

- `/api/admin/productos/*` - Gestión de productos
- `/api/admin/categorias/*` - Gestión de categorías
- `/api/admin/inventario/*` - Gestión de inventario
- `/api/admin/carrusel/*` - Gestión del carrusel
- `/api/admin/pedidos/*` - Gestión de pedidos
- `/api/admin/usuarios/*` - Gestión de usuarios

### Cómo Iniciar Sesión

1. **Frontend (React):**
   - Accede a `http://localhost:3000/login`
   - Ingresa el email: `admin@distribuidora.com`
   - Ingresa la contraseña: `Admin@2024`
   - Haz clic en "Iniciar sesión"

2. **API directamente (Swagger):**
   - Accede a `http://localhost:8000/docs`
   - Busca el endpoint `POST /api/auth/login`
   - Usa el botón "Try it out"
   - Ingresa:
     ```json
     {
       "email": "admin@distribuidora.com",
       "password": "Admin@2024"
     }
     ```
   - Copia el `access_token` de la respuesta
   - Haz clic en el botón "Authorize" en la parte superior
   - Ingresa: `Bearer <tu_access_token>`

3. **Usando cURL:**
   ```bash
   curl -X POST "http://localhost:8000/api/auth/login" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "admin@distribuidora.com",
       "password": "Admin@2024"
     }'
   ```

   Respuesta esperada:
   ```json
   {
     "status": "success",
     "message": "Inicio de sesión exitoso",
     "access_token": "eyJ...",
     "cart_merge": {
       "merged": false,
       "items_adjusted": []
     }
   }
   ```

### Cambiar Contraseña

⚠️ **IMPORTANTE:** Por razones de seguridad, se recomienda cambiar esta contraseña después del primer inicio de sesión, especialmente en ambientes de producción.

Actualmente no hay un endpoint específico para cambiar contraseña, pero puedes:

1. Implementar un endpoint `/api/auth/change-password`
2. O actualizar manualmente en la base de datos:
   ```sql
   -- Generar un nuevo hash de contraseña con bcrypt
   -- y actualizar el registro
   UPDATE Usuarios 
   SET password_hash = '<nuevo_hash_bcrypt>'
   WHERE email = 'admin@distribuidora.com';
   ```

### Script de Creación

El usuario administrador fue creado mediante el script Python:
`backend/api/create_admin_user.py`

Este script se puede ejecutar manualmente si necesitas recrear o actualizar el usuario:

```bash
# Desde fuera del contenedor:
docker exec -i distribuidora-api python /app/create_admin_user.py

# O copiar el script y ejecutar:
docker cp backend/api/create_admin_user.py distribuidora-api:/app/
docker exec -i distribuidora-api python /app/create_admin_user.py
```

**¿Por qué usar Python y no SQL directo?**
El hash de bcrypt debe ser generado usando el mismo código de la aplicación para garantizar compatibilidad. SQL Server puede escapar caracteres especiales en el hash, causando problemas de autenticación.

### Notas de Seguridad

- ✅ La contraseña cumple con los requisitos de seguridad:
  - Mínimo 10 caracteres
  - Al menos una mayúscula (A)
  - Al menos un número (2024)
  - Al menos un carácter especial (@)
- ✅ La contraseña está hasheada con bcrypt en la base de datos
- ⚠️ Este es un usuario de desarrollo/prueba
- ⚠️ NUNCA uses estas credenciales en producción
- ⚠️ Cambia la contraseña inmediatamente en entornos de producción

### Solución de Problemas

Si no puedes iniciar sesión:

1. Verifica que el contenedor de la API esté corriendo:
   ```bash
   docker ps | grep distribuidora-api
   ```

2. Verifica que el usuario existe en la base de datos:
   ```bash
   docker exec -i sqlserver /opt/mssql-tools18/bin/sqlcmd \
     -S localhost -U SA -P "yourStrongPassword123#" -C \
     -Q "USE distribuidora_db; SELECT * FROM Usuarios WHERE email = 'admin@distribuidora.com'"
   ```

3. Revisa los logs de la API:
   ```bash
   docker logs distribuidora-api
   ```

4. Verifica que el frontend esté apuntando a la URL correcta de la API.

---

**Fecha de creación:** 29 de noviembre de 2025
