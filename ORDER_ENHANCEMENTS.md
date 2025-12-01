# Mejoras en el Sistema de Pedidos

## Resumen de Cambios

Se han implementado mejoras significativas en el sistema de pedidos para proporcionar un desglose detallado de costos y métodos de pago.

## Cambios en el Backend

### 1. Modelo de Base de Datos (`app/models.py`)

Se agregaron tres nuevos campos a la tabla `Pedidos`:
- `subtotal`: Subtotal de los productos (sin envío)
- `costo_envio`: Costo del envío
- `metodo_pago`: Método de pago seleccionado por el usuario

### 2. Schema (`app/schemas.py`)

Se actualizó `PedidoCreate` para aceptar:
- `subtotal`: Opcional, se calcula si no se proporciona
- `costo_envio`: Opcional, se calcula si no se proporciona
- `metodo_pago`: Opcional, string con el método de pago

### 3. Endpoints

**`POST /api/pedidos`** (public_orders.py):
- Ahora acepta y guarda `subtotal`, `costo_envio` y `metodo_pago`
- Calcula el total como: `subtotal + costo_envio`
- Guarda toda la información en la base de datos

**Respuesta de pedidos**:
- Incluye `subtotal`, `costo_envio` y `metodo_pago` en todas las respuestas
- La función `_pedido_to_response` ha sido actualizada en ambos routers

## Cambios en el Frontend

### 1. Página del Carrito (`src/pages/cart/index.js`)

**Nuevas funcionalidades**:
- **Desglose de productos**: Muestra cada producto con su cantidad, precio unitario y subtotal
- **Desglose de costos**: Muestra subtotal, costo de envío y total por separado
- **Selector de método de pago**: Dropdown con opciones:
  - Efectivo
  - Tarjeta de Crédito
  - Tarjeta de Débito
  - Transferencia Bancaria
  - Nequi
  - Daviplata

**Validaciones**:
- El método de pago es obligatorio antes de procesar el pedido
- Se valida que todos los campos requeridos estén completos

### 2. Vista Administrativa (`src/pages/Admin/pedidos/index.js`)

**Mejoras en el modal de detalles**:
- **Sección de Productos**: Muestra tabla con nombre, cantidad, precio unitario y subtotal
- **Resumen de Costos**: Desglose visual de:
  - Subtotal
  - Costo de Envío
  - Total
- **Información de Pago**: Muestra:
  - Método de pago seleccionado
  - Teléfono de contacto
  - Nota especial (si existe)

## Migración de Base de Datos

Se creó un script de migración SQL (`sql/migrations/add_payment_method_and_shipping_cost.sql`) que:
- Agrega las columnas `subtotal`, `costo_envio` y `metodo_pago` a la tabla `Pedidos`
- Actualiza registros existentes para mantener compatibilidad hacia atrás
- Es seguro ejecutarlo múltiples veces (usa `IF NOT EXISTS`)

### Cómo aplicar la migración:

1. **Automático**: Si el sistema de migraciones está configurado, se aplicará automáticamente
2. **Manual**: Ejecutar el script SQL directamente en la base de datos:
   ```sql
   sqlcmd -S sqlserver -U SA -P 'yourStrongPassword123#' -d distribuidora_db -i sql/migrations/add_payment_method_and_shipping_cost.sql
   ```

## Flujo de Usuario Actualizado

1. Usuario agrega productos al carrito
2. Usuario ve el resumen con:
   - Lista de productos con cantidades y precios
   - Subtotal de productos
   - Costo de envío
   - Total
3. Usuario completa información de envío
4. Usuario selecciona método de pago (obligatorio)
5. Usuario hace clic en "Comprar"
6. El pedido se crea con toda la información
7. En la vista administrativa, se puede ver:
   - Desglose completo de productos
   - Desglose de costos
   - Método de pago utilizado

## Compatibilidad

- Los pedidos existentes mantienen su funcionalidad
- Si no se proporciona `subtotal` o `costo_envio`, se calculan automáticamente
- Si no se proporciona `metodo_pago`, se guarda como "No especificado"
- La migración es segura y no afecta datos existentes

## Próximas Mejoras Sugeridas

1. Guardar métodos de pago favoritos del usuario
2. Integración con pasarelas de pago reales
3. Historial de métodos de pago por usuario
4. Estadísticas de métodos de pago más utilizados
5. Cálculo dinámico de costo de envío basado en ubicación

