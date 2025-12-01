# 🔐 Cómo Obtener el Código de Verificación en Desarrollo

## 📋 Problema

Cuando registras un usuario, el sistema genera un código de verificación de 6 dígitos que se envía por email a través de RabbitMQ. En desarrollo, si no tienes configurado un servicio de email real, necesitas una forma de obtener este código para verificar tu cuenta.

## ✅ Soluciones Implementadas

### 1. **Logging Automático en Consola (Modo DEBUG)**

Cuando `DEBUG=True`, el código de verificación se imprime automáticamente en los logs del servidor cuando se genera.

**Formato del log:**
```
🔐 [DEV MODE] Verification code for usuario@email.com: 123456
📧 [DEV MODE] User can verify email at: POST /api/auth/verify-email with code: 123456
```

**Cómo ver los logs:**
- Si estás ejecutando localmente: Los logs aparecen en la consola donde ejecutaste el servidor
- Si estás usando Docker: `docker logs distribuidora-api` o `docker-compose logs api`

### 2. **Endpoint de Desarrollo** (Solo en modo DEBUG)

Se agregó un endpoint especial para obtener información sobre el código de verificación:

```
GET /api/auth/dev/verification-code/{email}
```

**Ejemplo:**
```bash
curl http://localhost:8000/api/auth/dev/verification-code/Julian@mail.com
```

**Nota importante:** Este endpoint NO puede recuperar el código real (está hasheado en la BD), pero te da información sobre el estado del código. El código real solo está disponible en los logs cuando se genera.

## 🚀 Pasos para Obtener el Código

### Opción 1: Revisar Logs del Servidor (Recomendado)

1. **Si estás ejecutando localmente:**
   - Busca en la consola donde ejecutaste `uvicorn` o `python main.py`
   - Busca el mensaje: `🔐 [DEV MODE] Verification code for...`

2. **Si estás usando Docker:**
   ```bash
   # Ver logs en tiempo real
   docker logs -f distribuidora-api
   
   # O con docker-compose
   docker-compose logs -f api
   ```

3. **Busca el código:**
   - El código aparece justo después de registrar un usuario
   - Formato: `🔐 [DEV MODE] Verification code for {email}: {código}`

### Opción 2: Revisar Logs Después del Registro

Si ya registraste el usuario, puedes:

1. **Ver logs históricos:**
   ```bash
   docker logs distribuidora-api | grep "DEV MODE"
   ```

2. **O reenviar el código:**
   - Usa el botón "Reenviar código" en el frontend
   - El nuevo código aparecerá en los logs

### Opción 3: Usar el Endpoint de Desarrollo

```bash
# Obtener información del código (no el código real)
curl http://localhost:8000/api/auth/dev/verification-code/Julian@mail.com
```

Esto te dirá:
- Si el código existe
- Si está expirado
- Si ya fue usado
- Cuándo fue creado

## ⚙️ Configuración

### Activar Modo DEBUG

El modo DEBUG ya está activado en `docker-compose.yml` con:
```yaml
environment:
  - DEBUG=True
```

Si ejecutas localmente, asegúrate de tener `DEBUG=True` en tu `.env` o config.

### Verificar que DEBUG está activo

El endpoint de desarrollo solo funciona si `DEBUG=True`. Si intentas acceder y está desactivado, recibirás un error 403.

## 📝 Ejemplo Completo

1. **Registrar usuario:**
   ```bash
   curl -X POST http://localhost:8000/api/auth/register \
     -H "Content-Type: application/json" \
     -d '{
       "email": "test@example.com",
       "password": "Test123!@#",
       "nombre": "Test User",
       "cedula": "12345678"
     }'
   ```

2. **Ver logs inmediatamente:**
   ```bash
   docker logs distribuidora-api | tail -20
   ```
   
   Deberías ver:
   ```
   🔐 [DEV MODE] Verification code for test@example.com: 456789
   ```

3. **Usar el código en el frontend:**
   - Ve a la página de verificación
   - Ingresa el código que viste en los logs
   - ¡Listo!

## 🔒 Seguridad

⚠️ **IMPORTANTE:**
- El modo DEBUG y el endpoint de desarrollo **NUNCA** deben estar activos en producción
- Los códigos de verificación están hasheados en la base de datos por seguridad
- Solo se pueden ver en los logs cuando se generan (en modo DEBUG)
- El endpoint de desarrollo solo proporciona información, no el código real

## 🐛 Troubleshooting

### No veo los logs con el código

1. Verifica que `DEBUG=True` esté configurado:
   ```bash
   docker exec distribuidora-api env | grep DEBUG
   ```

2. Verifica que el servidor esté ejecutándose:
   ```bash
   docker ps | grep distribuidora-api
   ```

3. Revisa todos los logs:
   ```bash
   docker logs distribuidora-api | grep -i "verification"
   ```

### El endpoint de desarrollo no funciona

- Asegúrate de que `DEBUG=True`
- Verifica que el email sea correcto (case-insensitive)
- Revisa que el usuario exista en la base de datos

### El código expiró

- Los códigos expiran en 10 minutos
- Usa el botón "Reenviar código" para generar uno nuevo
- El nuevo código aparecerá en los logs

---

**Fecha de creación:** 2024  
**Última actualización:** 2024

