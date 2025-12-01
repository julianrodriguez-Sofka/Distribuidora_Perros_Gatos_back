# Instrucciones para Ejecutar la Migración de Pedidos

## Problema

Las columnas `subtotal`, `costo_envio`, y `metodo_pago` no existen en la tabla `Pedidos` de la base de datos, lo que impide guardar correctamente la información de los pedidos.

## Solución: Ejecutar la Migración

### Opción 1: Reiniciar el servicio db-migrator (Recomendado)

```powershell
cd Distribuidora_Perros_Gatos_back
docker-compose restart db-migrator
```

Esto ejecutará automáticamente todas las migraciones en la carpeta `sql/migrations/`.

### Opción 2: Ejecutar la migración manualmente

Si el contenedor `db-migrator` ya terminó, puedes ejecutar la migración directamente:

```powershell
cd Distribuidora_Perros_Gatos_back
docker-compose run --rm db-migrator /opt/mssql-tools/bin/sqlcmd -S sqlserver -U SA -P "yourStrongPassword123#" -d distribuidora_db -i /sql/migrations/add_payment_method_and_shipping_cost.sql
```

### Opción 3: Ejecutar SQL directamente desde el contenedor de la API

```powershell
docker exec distribuidora-api python -c "import sys; sys.path.insert(0, '/app'); from app.database import SessionLocal; from sqlalchemy import text; db = SessionLocal(); db.execute(text('ALTER TABLE Pedidos ADD subtotal NUMERIC(10, 2) NOT NULL DEFAULT 0')); db.commit(); print('OK'); db.close()"
```

Repite para `costo_envio` y `metodo_pago`.

## Verificación

Después de ejecutar la migración, verifica que las columnas existen:

```powershell
docker exec distribuidora-api python -c "from app.database import SessionLocal; from sqlalchemy import text; db = SessionLocal(); cols = db.execute(text('SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = \\'Pedidos\\'')).fetchall(); print([c[0] for c in cols]); db.close()"
```

Deberías ver: `subtotal`, `costo_envio`, y `metodo_pago` en la lista.

## Reiniciar la API

Después de ejecutar la migración, reinicia el contenedor de la API:

```powershell
docker-compose restart api
```

## Probar

1. Crea un nuevo pedido desde el frontend
2. Verifica que se guardan todos los datos (dirección, teléfono, método de pago)
3. Abre el pedido en el panel de administración
4. Verifica que todos los datos se muestran correctamente

