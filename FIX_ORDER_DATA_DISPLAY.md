# Solución: Visualización de Información de Pedidos

## Problema Identificado

Los datos del pedido (dirección, teléfono, método de pago, subtotal, costo de envío) no se mostraban en el panel de administración, aunque se estaban guardando correctamente en la base de datos.

## Causa Raíz

1. **SQLAlchemy no cargaba las nuevas columnas:**
   - Las columnas `subtotal`, `costo_envio`, y `metodo_pago` fueron agregadas a la base de datos mediante migración
   - El modelo Python tenía estas columnas definidas
   - Pero SQLAlchemy estaba haciendo queries que solo seleccionaban las columnas antiguas
   - El `db.refresh()` tampoco funcionaba porque SQLAlchemy no sabía que estas columnas existían

2. **Pedidos antiguos sin datos:**
   - Los pedidos creados antes de la migración no tenían valores para `subtotal`, `costo_envio`, y `metodo_pago`
   - Estos valores estaban en NULL o 0

## Solución Implementada

### Backend (`orders.py`)

1. **Query SQL directo en `_pedido_to_response`:**
   - Cambiado de usar el objeto `pedido` directamente a hacer un query SQL explícito
   - El query incluye todas las columnas necesarias, incluyendo las nuevas

   ```python
   def _pedido_to_response(db, pedido: models.Pedido):
       # Query pedido directly with all columns to ensure we get subtotal, costo_envio, metodo_pago
       pedido_full = db.execute(
           text("""
               SELECT id, usuario_id, estado, total, subtotal, costo_envio, metodo_pago, 
                      direccion_entrega, telefono_contacto, nota_especial, fecha_creacion
               FROM Pedidos 
               WHERE id = :pedido_id
           """),
           {"pedido_id": pedido.id}
       ).first()
   ```

2. **Uso de valores del query directo:**
   - Todos los valores ahora se obtienen del resultado del query SQL directo
   - Esto asegura que todas las columnas se carguen correctamente

   ```python
   subtotal_val = float(pedido_full.subtotal) if pedido_full.subtotal is not None else float(pedido_full.total)
   costo_envio_val = float(pedido_full.costo_envio) if pedido_full.costo_envio is not None else 0.0
   metodo_pago_val = pedido_full.metodo_pago if pedido_full.metodo_pago else None
   direccion_entrega_val = pedido_full.direccion_entrega or ""
   telefono_contacto_val = pedido_full.telefono_contacto or ""
   ```

3. **Actualización de pedidos antiguos:**
   - Script para actualizar pedidos creados antes de la migración
   - Establece `subtotal = total`, `costo_envio = 0`, y `metodo_pago = 'Efectivo'` para pedidos antiguos

### Frontend

El frontend ya estaba correctamente configurado para mostrar todos los datos. No se requirieron cambios.

## Archivos Modificados

### Backend
- `backend/api/app/routers/orders.py`: Modificada función `_pedido_to_response` para usar query SQL directo

## Resultado

✅ **Todos los datos se muestran correctamente:**
- Nombre del cliente
- Email del cliente (si está disponible)
- Teléfono del cliente (si está disponible)
- Dirección de entrega
- Teléfono de contacto
- Método de pago
- Subtotal
- Costo de envío
- Total
- Lista de productos con nombres

✅ **Pedidos antiguos actualizados:**
- Los pedidos creados antes de la migración ahora tienen valores por defecto
- `subtotal` = `total`
- `costo_envio` = 0
- `metodo_pago` = 'Efectivo'

✅ **Nuevos pedidos:**
- Todos los datos se guardan correctamente
- Todos los datos se muestran correctamente en el panel de administración

## Pruebas Realizadas

- ✅ Visualización de pedidos antiguos (con valores por defecto)
- ✅ Visualización de nuevos pedidos (con todos los datos completos)
- ✅ Verificación de que todos los campos se muestran en el modal
- ✅ Verificación de que los nombres de productos se muestran correctamente

## Nota Técnica

El problema era que SQLAlchemy estaba usando un caché o un mapeo que no incluía las nuevas columnas. Al hacer un query SQL directo, nos aseguramos de que todas las columnas se carguen correctamente, independientemente del estado del mapeo de SQLAlchemy.

