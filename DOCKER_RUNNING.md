# 🐳 Backend Ejecutándose en Docker

**Fecha:** 2024  
**Estado:** ✅ FUNCIONANDO

---

## ✅ Servicios en Ejecución

### 1. Backend API (FastAPI)
- **Contenedor:** `distribuidora-api`
- **Estado:** ✅ RUNNING
- **Puerto:** 8000
- **URL:** http://localhost:8000
- **Documentación:** http://localhost:8000/docs
- **Logs:** `docker-compose logs api`

### 2. SQL Server
- **Contenedor:** `sqlserver`
- **Estado:** ✅ RUNNING (healthy)
- **Puerto:** 1433
- **Base de datos:** `distribuidora_db`
- **Usuario:** SA
- **Password:** yourStrongPassword123#

### 3. RabbitMQ
- **Contenedor:** `rabbitmq`
- **Estado:** ✅ RUNNING (healthy)
- **Puerto AMQP:** 5672
- **Puerto Management:** 15672
- **Management UI:** http://localhost:15672
- **Usuario:** guest
- **Password:** guest

### 4. DB Migrator
- **Contenedor:** `distribuidora-db-migrator`
- **Estado:** ✅ COMPLETED
- **Función:** Inicializa la base de datos con schema, migraciones y seeders

---

## 🚀 Comandos Útiles

### Ver estado de todos los servicios
```bash
docker-compose ps
```

### Ver logs del API
```bash
docker-compose logs api
docker-compose logs api --follow  # Seguir logs en tiempo real
docker-compose logs api --tail 50 # Últimas 50 líneas
```

### Reiniciar el API
```bash
docker-compose restart api
```

### Detener todos los servicios
```bash
docker-compose down
```

### Iniciar todos los servicios
```bash
docker-compose up -d
```

### Reconstruir el API después de cambios
```bash
docker-compose build api
docker-compose up -d api
```

### Ver logs de todos los servicios
```bash
docker-compose logs
docker-compose logs --follow  # Seguir todos los logs
```

---

## 🔧 Problemas Resueltos

### 1. Script init-db.sh con finales de línea CRLF
**Problema:** El script bash tenía finales de línea Windows (CRLF) que causaban errores en Linux.

**Solución:** Actualizado `docker-compose.yml` para usar comandos inline en lugar del script, evitando problemas de formato.

### 2. Dependencias de servicios
**Problema:** El API necesita que SQL Server y RabbitMQ estén saludables antes de iniciar.

**Solución:** Configurado `depends_on` con `condition: service_healthy` en docker-compose.yml.

### 3. Inicialización de base de datos
**Problema:** La base de datos necesita ser inicializada antes de que el API la use.

**Solución:** Servicio `db-migrator` que se ejecuta primero y crea la base de datos, aplica schema, migraciones y seeders.

---

## 📊 Estado de la Base de Datos

La base de datos `distribuidora_db` ha sido inicializada con:
- ✅ Schema completo (14 tablas)
- ✅ Índices de rendimiento
- ✅ Migraciones aplicadas
- ✅ Seeders ejecutados (categorías y productos de ejemplo)

**Nota:** Algunos errores menores en logs de migraciones son esperados (intentos de crear objetos que ya existen).

---

## 🌐 Acceso a Servicios

### Backend API
- **API Base:** http://localhost:8000
- **Documentación:** http://localhost:8000/docs
- **OpenAPI JSON:** http://localhost:8000/openapi.json

### RabbitMQ Management
- **URL:** http://localhost:15672
- **Usuario:** guest
- **Password:** guest

### SQL Server
- **Host:** localhost
- **Puerto:** 1433
- **Base de datos:** distribuidora_db
- **Usuario:** SA
- **Password:** yourStrongPassword123#

---

## 🧪 Pruebas Rápidas

### 1. Verificar que el API responde
```bash
curl http://localhost:8000/docs
```

### 2. Probar endpoint de autenticación
```bash
curl http://localhost:8000/api/auth/me
# Debe retornar 401 (no autenticado) - esto es correcto
```

### 3. Ver logs en tiempo real
```bash
docker-compose logs -f api
```

---

## ⚠️ Notas Importantes

### Volúmenes Persistentes
- **SQL Server:** Los datos se persisten en el volumen `sqlserver_data`
- **Uploads:** Los archivos subidos se persisten en `./backend/api/app/uploads`

### Reinicio de Servicios
Si necesitas reiniciar todo:
```bash
docker-compose down
docker-compose up -d
```

### Limpiar Todo (CUIDADO: Elimina datos)
```bash
docker-compose down -v  # Elimina volúmenes también
```

---

## ✅ Verificación de Funcionalidad

- ✅ Backend API corriendo en Docker
- ✅ SQL Server conectado y saludable
- ✅ RabbitMQ conectado y saludable
- ✅ Base de datos inicializada
- ✅ API respondiendo en http://localhost:8000
- ✅ Documentación disponible en http://localhost:8000/docs

---

## 🎯 Próximos Pasos

1. **Probar endpoints** usando la documentación en `/docs`
2. **Verificar conexión a base de datos** probando endpoints que requieren BD
3. **Probar RabbitMQ** enviando mensajes y verificando en la UI de management
4. **Conectar frontend** al backend en Docker

---

**¡Backend funcionando correctamente en Docker!** 🎉

