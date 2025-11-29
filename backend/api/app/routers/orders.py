"""
Orders router: View and manage orders for admin
Handles HU_MANAGE_ORDERS
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.orm import Session
from typing import List, Optional
from sqlalchemy import desc, text
import json
from app.schemas import (
    PedidoCreate,
    PedidoResponse,
    PedidoItemResponse,
    PedidoEstadoUpdate,
)
from app.database import get_db
from app.utils.rabbitmq import RabbitMQProducer
import app.models as models
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/pedidos",
    tags=["orders"]
)


def _pedido_to_response(db, pedido: models.Pedido):
    # Query pedido directly with all columns to ensure we get subtotal, costo_envio, metodo_pago
    # Handle both cases: pedido can be a model instance or just an id
    pedido_id = pedido.id if hasattr(pedido, 'id') else pedido
    
    logger.info(f"_pedido_to_response called for pedido_id={pedido_id}")
    
    # Execute direct SQL query to get all columns including new ones
    try:
        result = db.execute(
            text("""
                SELECT id, usuario_id, estado, total, subtotal, costo_envio, metodo_pago, 
                       direccion_entrega, telefono_contacto, nota_especial, fecha_creacion
                FROM Pedidos 
                WHERE id = :pedido_id
            """),
            {"pedido_id": pedido_id}
        )
        pedido_full = result.first()
        logger.info(f"SQL query executed, pedido_full={pedido_full}")
    except Exception as e:
        logger.error(f"Error executing SQL query for pedido {pedido_id}: {e}")
        logger.exception(e)
        raise
    
    if not pedido_full:
        logger.error(f"Pedido {pedido_id} not found in database")
        raise ValueError(f"Pedido {pedido_id} not found")
    
    # Access row columns by index (SQLAlchemy Row object)
    # Column order: id, usuario_id, estado, total, subtotal, costo_envio, metodo_pago, 
    #               direccion_entrega, telefono_contacto, nota_especial, fecha_creacion
    try:
        pedido_id_val = pedido_full[0]
        usuario_id_val = pedido_full[1]
        estado_val = pedido_full[2]
        total_val = pedido_full[3]
        subtotal_val = pedido_full[4]
        costo_envio_val = pedido_full[5]
        metodo_pago_val = pedido_full[6]
        direccion_entrega_val = pedido_full[7]
        telefono_contacto_val = pedido_full[8]
        nota_especial_val = pedido_full[9]
        fecha_creacion_val = pedido_full[10]
        
        logger.info(f"Pedido {pedido_id_val} loaded: direccion={direccion_entrega_val}, telefono={telefono_contacto_val}, metodo_pago={metodo_pago_val}, subtotal={subtotal_val}, costo_envio={costo_envio_val}")
    except Exception as e:
        logger.error(f"Error accessing row columns for pedido {pedido_id}: {e}")
        logger.exception(e)
        raise
    
    items = db.query(models.PedidoItem).filter(models.PedidoItem.pedido_id == pedido_id).all()
    
    # Get product IDs to fetch names
    producto_ids = [item.producto_id for item in items]
    productos_map = {}
    
    # Fetch product names in batch
    if producto_ids:
        try:
            producto_ids_list = [int(x) for x in producto_ids]
            if producto_ids_list:
                # Use parameterized query to prevent SQL injection
                placeholders = ','.join([f':prod_id_{i}' for i in range(len(producto_ids_list))])
                params = {f'prod_id_{i}': prod_id for i, prod_id in enumerate(producto_ids_list)}
                q_prod = text(f"SELECT id, nombre FROM Productos WHERE id IN ({placeholders})")
                result = db.execute(q_prod, params)
                for prod_row in result.fetchall():
                    # Access Row by index: id=0, nombre=1
                    productos_map[prod_row[0]] = prod_row[1]
                logger.info(f"Fetched {len(productos_map)} product names for pedido {pedido_id}")
        except Exception as e:
            logger.error(f"Error fetching product names for pedido {pedido_id}: {e}")
            logger.exception(e)
    
    items_resp = [
        {
            "id": item.id,
            "producto_id": item.producto_id,
            "nombre": productos_map.get(item.producto_id, f"Producto ID: {item.producto_id}"),
            "cantidad": item.cantidad,
            "precio_unitario": float(item.precio_unitario),
        }
        for item in items
    ]

    # Get user information
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id_val).first()
    cliente_nombre = usuario.nombre_completo if usuario else f"Usuario ID: {usuario_id_val}"
    cliente_id = usuario_id_val
    cliente_email = usuario.email if usuario else None
    cliente_telefono = usuario.telefono if usuario else None

    # Format fecha_creacion to ISO string if it exists
    fecha_creacion_str = None
    if fecha_creacion_val:
        if hasattr(fecha_creacion_val, 'isoformat'):
            fecha_creacion_str = fecha_creacion_val.isoformat()
        else:
            fecha_creacion_str = str(fecha_creacion_val)

    # Convert values from SQL query (already extracted above)
    subtotal_float = float(subtotal_val) if subtotal_val is not None else float(total_val)
    costo_envio_float = float(costo_envio_val) if costo_envio_val is not None else 0.0
    metodo_pago_str = metodo_pago_val if metodo_pago_val else None
    direccion_str = direccion_entrega_val or "" if direccion_entrega_val else ""
    telefono_str = telefono_contacto_val or "" if telefono_contacto_val else ""

    return {
        "id": pedido_id_val,
        "usuario_id": usuario_id_val,
        "clienteId": cliente_id,
        "cliente_id": cliente_id,
        "clienteNombre": cliente_nombre,
        "cliente_nombre": cliente_nombre,
        "clienteEmail": cliente_email,
        "cliente_email": cliente_email,
        "clienteTelefono": cliente_telefono,
        "cliente_telefono": cliente_telefono,
        "estado": estado_val,
        "total": float(total_val),
        "subtotal": subtotal_float,
        "costo_envio": costo_envio_float,
        "metodo_pago": metodo_pago_str,
        "direccion_entrega": direccion_str,
        "direccionEnvio": direccion_str,  # Alias for frontend compatibility
        "telefono_contacto": telefono_str,
        "nota_especial": nota_especial_val,
        "fecha_creacion": fecha_creacion_str,
        "fecha": fecha_creacion_str,  # Alias for frontend compatibility
        "created_at": fecha_creacion_str,  # Another alias
        "items": items_resp,
    }


@router.get("/")
async def list_orders(
    estado: str = Query(None, regex="^(Pendiente|Enviado|Entregado|Cancelado)$"),
    usuario_id: int = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    List all orders with optional filtering
    
    Requirements (HU_MANAGE_ORDERS):
    - Filter by estado (Pendiente, Enviado, Entregado, Cancelado)
    - Filter by usuario_id
    - Sort by fecha_creacion DESC (newest first)
    - Return order with items and total
    - Pagination support
    """
    q = db.query(models.Pedido)
    if estado:
        q = q.filter(models.Pedido.estado == estado)
    if usuario_id:
        q = q.filter(models.Pedido.usuario_id == usuario_id)

    pedidos = q.order_by(desc(models.Pedido.fecha_creacion)).offset(skip).limit(limit).all()
    # Use _pedido_to_response for each pedido to ensure all columns are loaded via direct SQL query
    logger.info(f"Listing {len(pedidos)} orders with filters: estado={estado}, usuario_id={usuario_id}")
    # Return full order data without Pydantic filtering
    return [_pedido_to_response(db, p) for p in pedidos]

@router.post("/", response_model=PedidoResponse, status_code=status.HTTP_201_CREATED)
async def create_order(payload: PedidoCreate, db: Session = Depends(get_db)):
    # Validate usuario exists
    usuario = db.query(models.Usuario).filter(models.Usuario.id == payload.usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuario no existe")

    pedido = models.Pedido(
        usuario_id=payload.usuario_id,
        estado='Pendiente',
        direccion_entrega=payload.direccion_entrega,
        telefono_contacto=payload.telefono_contacto,
        nota_especial=payload.nota_especial,
    )
    db.add(pedido)
    db.flush()

    total = 0
    items_payload = getattr(payload, 'items', []) or []
    for it in items_payload:
        producto_id = int(it.get('producto_id'))
        cantidad = int(it.get('cantidad'))
        precio = float(it.get('precio_unitario')) if it.get('precio_unitario') is not None else 0.0
        total += cantidad * precio
        pi = models.PedidoItem(
            pedido_id=pedido.id,
            producto_id=producto_id,
            cantidad=cantidad,
            precio_unitario=precio,
        )
        db.add(pi)

    pedido.total = total
    db.add(pedido)
    db.commit()
    db.refresh(pedido)

    return _pedido_to_response(db, pedido)


@router.put("/{pedido_id}", response_model=PedidoResponse)
async def update_order(pedido_id: int, payload: PedidoCreate, db: Session = Depends(get_db)):
    pedido = db.query(models.Pedido).filter(models.Pedido.id == pedido_id).first()
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")

    # Update simple fields
    pedido.direccion_entrega = payload.direccion_entrega
    pedido.telefono_contacto = payload.telefono_contacto
    pedido.nota_especial = payload.nota_especial
    db.add(pedido)

    # Replace items: delete existing and add new
    db.query(models.PedidoItem).filter(models.PedidoItem.pedido_id == pedido.id).delete()
    total = 0
    items_payload = getattr(payload, 'items', []) or []
    for it in items_payload:
        producto_id = int(it.get('producto_id'))
        cantidad = int(it.get('cantidad'))
        precio = float(it.get('precio_unitario')) if it.get('precio_unitario') is not None else 0.0
        total += cantidad * precio
        pi = models.PedidoItem(
            pedido_id=pedido.id,
            producto_id=producto_id,
            cantidad=cantidad,
            precio_unitario=precio,
        )
        db.add(pi)

    pedido.total = total
    db.commit()
    db.refresh(pedido)
    return _pedido_to_response(db, pedido)


@router.delete("/{pedido_id}")
async def delete_order(pedido_id: int, db: Session = Depends(get_db)):
    pedido = db.query(models.Pedido).filter(models.Pedido.id == pedido_id).first()
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")
    db.delete(pedido)
    db.commit()
    return {"status": "success", "message": "Pedido eliminado"}

@router.get("/{pedido_id}")
async def get_order(pedido_id: int, db: Session = Depends(get_db)):
    """
    Get order details with items
    
    Requirements:
    - Return full order information
    - Include all PedidoItems with product info
    - Include estado history
    """
    pedido = db.query(models.Pedido).filter(models.Pedido.id == pedido_id).first()
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")
    # Use _pedido_to_response which does a direct SQL query to get all columns
    # This ensures we get subtotal, costo_envio, metodo_pago even if SQLAlchemy model doesn't have them
    logger.info(f"Fetching order {pedido_id} with full details")
    result = _pedido_to_response(db, pedido)
    logger.info(f"Order {pedido_id} response: clienteNombre={result.get('clienteNombre')}, direccion={result.get('direccion_entrega')}, metodo_pago={result.get('metodo_pago')}")
    # Return as JSON directly to avoid Pydantic filtering
    # FastAPI will automatically serialize the dict to JSON
    return result


@router.put("/{pedido_id}/status", response_model=PedidoResponse)
async def update_order_status(
    pedido_id: int,
    request: PedidoEstadoUpdate,
    db: Session = Depends(get_db)
):
    """
    Update order status
    
    Requirements (HU_MANAGE_ORDERS):
    - Valid status: Pendiente, Enviado, Entregado, Cancelado
    - Create audit entry in PedidosHistorialEstado
    - Record estado change with timestamp and usuario_id
    - Publishes pedido.estado.cambiar queue message
    - Include optional nota with change reason
    """
    pedido = db.query(models.Pedido).filter(models.Pedido.id == pedido_id).first()
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")

    estado_anterior = pedido.estado
    pedido.estado = request.estado
    db.add(pedido)

    historial = models.PedidosHistorialEstado(
        pedido_id=pedido.id,
        estado_anterior=estado_anterior,
        estado_nuevo=request.estado,
        usuario_id=None,
        nota=request.nota,
    )
    db.add(historial)
    db.commit()
    db.refresh(pedido)

    # Publish event to RabbitMQ (best-effort)
    try:
        producer = RabbitMQProducer()
        producer.connect()
        message = {
            "pedido_id": pedido.id,
            "estado_anterior": estado_anterior,
            "estado_nuevo": request.estado,
        }
        producer.publish("pedido.estado.cambiado", message)
    except Exception:
        # do not fail the request if publishing fails
        pass
    finally:
        try:
            producer.close()
        except Exception:
            pass

    return _pedido_to_response(db, pedido)
    # 1. Validate pedido exists
    # 2. Validate new estado
    # 3. Update Pedido.estado
    # 4. Create PedidosHistorialEstado entry
    # 5. Publish pedido.estado.cambiar queue message
    # 6. Return updated order


@router.get("/{pedido_id}/history")
async def get_order_history(pedido_id: int, db: Session = Depends(get_db)):
    """
    Get order status change history
    
    Requirements:
    - Return all estado changes for order
    - Sorted by fecha DESC (newest first)
    - Include usuario_id who made change
    - Include change notes
    """
    items = (
        db.query(models.PedidosHistorialEstado)
        .filter(models.PedidosHistorialEstado.pedido_id == pedido_id)
        .order_by(desc(models.PedidosHistorialEstado.fecha))
        .all()
    )

    return [
        {
            "id": it.id,
            "pedido_id": it.pedido_id,
            "estado_anterior": it.estado_anterior,
            "estado_nuevo": it.estado_nuevo,
            "usuario_id": it.usuario_id,
            "nota": it.nota,
            "fecha": it.fecha,
        }
        for it in items
    ]
    


@router.get("/user/{usuario_id}", response_model=List[PedidoResponse])
async def get_user_orders(
    usuario_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get all orders for a specific user
    
    Requirements:
    - Filter orders by usuario_id
    - Pagination support
    - Return orders with items
    """
    pedidos = (
        db.query(models.Pedido)
        .filter(models.Pedido.usuario_id == usuario_id)
        .order_by(desc(models.Pedido.fecha_creacion))
        .all()
    )
    return [_pedido_to_response(db, p) for p in pedidos]
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented")
