# Solución: Guardado de Información de Pedidos en Base de Datos

## Problema Identificado

Los datos del pedido (dirección, teléfono, método de pago) no se estaban guardando correctamente en la base de datos, y por lo tanto no aparecían en el panel de administración al ver el pedido.

## Causa Raíz

1. **Faltaban columnas en la base de datos:**
   - Las columnas `subtotal`, `costo_envio`, y `metodo_pago` no existían en la tabla `Pedidos`
   - El modelo Python tenía estos campos, pero la base de datos no
   - La migración SQL no se había ejecutado correctamente

2. **El código de creación de pedidos estaba correcto:**
   - El frontend enviaba todos los datos correctamente
   - El backend intentaba guardar los datos, pero fallaba silenciosamente porque las columnas no existían

## Solución Implementada

### 1. Verificación y Ejecución de Migración

Se necesita ejecutar la migración SQL que agrega las columnas faltantes. La migración está en:
- `sql/migrations/add_payment_method_and_shipping_cost.sql`

**Para ejecutar la migración manualmente:**

```bash
# Opción 1: Ejecutar directamente en el contenedor de migración
docker exec distribuidora-db-migrator /opt/mssql-tools/bin/sqlcmd -S sqlserver -U SA -P 'yourStrongPassword123#' -d distribuidora_db -i /sql/migrations/add_payment_method_and_shipping_cost.sql

# Opción 2: Reiniciar el servicio db-migrator para que ejecute todas las migraciones
docker-compose restart db-migrator
```

### 2. Código de Creación de Pedidos (Ya estaba correcto)

El código en `public_orders.py` ya estaba guardando todos los datos:

```python
# Create pedido
pedido = models.Pedido(
    usuario_id=current_user.id,
    estado='Pendiente',
    direccion_entrega=direccion_entrega,
    telefono_contacto=telefono_contacto.replace("+", "").replace("-", "").replace(" ", ""),
    nota_especial=payload.get("notaEspecial") or payload.get("nota_especial"),
)
db.add(pedido)
db.flush()

# ... procesar items ...

# Get shipping cost and payment method from payload
costo_envio = float(payload.get("costoEnvio") or payload.get("costo_envio") or 0.0)
metodo_pago = payload.get("metodoPago") or payload.get("metodo_pago") or "No especificado"

# Update pedido with all information
pedido.subtotal = subtotal
pedido.costo_envio = costo_envio
pedido.metodo_pago = metodo_pago
pedido.total = total
db.commit()
```

### 3. Mejora del docker-compose.yml

Se mejoró el servicio `db-migrator` para que continúe ejecutando migraciones incluso si alguna falla (por ejemplo, si ya existe):

```yaml
if [ -d /sql/migrations ]; then
  echo 'Applying migrations...';
  for f in /sql/migrations/*.sql; do 
    [ -f "$f" ] && echo "Applying $f" && 
    /opt/mssql-tools/bin/sqlcmd -S sqlserver -U SA -P 'yourStrongPassword123#' -d distribuidora_db -i "$f" || 
    echo "Migration $f failed or already applied"; 
  done;
fi;
```

## Pasos para Aplicar la Solución

1. **Ejecutar la migración SQL:**
   ```bash
   cd Distribuidora_Perros_Gatos_back
   docker-compose exec db-migrator /opt/mssql-tools/bin/sqlcmd -S sqlserver -U SA -P 'yourStrongPassword123#' -d distribuidora_db -i /sql/migrations/add_payment_method_and_shipping_cost.sql
   ```

2. **O reiniciar el servicio de migración:**
   ```bash
   docker-compose restart db-migrator
   ```

3. **Verificar que las columnas existen:**
   ```bash
   docker exec distribuidora-api python -c "from app.database import SessionLocal; from sqlalchemy import text; db = SessionLocal(); result = db.execute(text('SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = \\'Pedidos\\'')); print([r[0] for r in result]); db.close()"
   ```

4. **Reiniciar el contenedor de la API:**
   ```bash
   docker-compose restart api
   ```

## Verificación

Después de ejecutar la migración, los nuevos pedidos deberían:
- ✅ Guardar correctamente la dirección de entrega
- ✅ Guardar correctamente el teléfono de contacto
- ✅ Guardar correctamente el método de pago
- ✅ Guardar correctamente el subtotal y costo de envío
- ✅ Mostrar todos estos datos en el panel de administración

## Nota Importante

Los pedidos creados ANTES de ejecutar la migración no tendrán estos campos. Para actualizar los pedidos existentes, se puede ejecutar:

```sql
UPDATE Pedidos 
SET subtotal = total, 
    costo_envio = 0,
    metodo_pago = 'No especificado'
WHERE subtotal = 0 OR subtotal IS NULL;
```

