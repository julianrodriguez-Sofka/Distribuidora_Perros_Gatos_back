"""
Public orders router: Create and view orders for authenticated users
Handles user order creation and retrieval
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
from app.schemas import (
    PedidoResponse,
)
from app.database import get_db
from app.routers.auth import get_current_user
from app.routers.orders import _pedido_to_response
from app.routers.auth import UsuarioPublicResponse
import app.models as models
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/pedidos",
    tags=["public-orders"]
)


@router.post("/", response_model=PedidoResponse, status_code=status.HTTP_201_CREATED)
async def create_user_order(
    payload: dict,
    current_user: UsuarioPublicResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new order for the authenticated user
    
    Expected payload format:
    {
        "productos": [
            {
                "sku": int,  # producto_id
                "nombre": str,
                "cantidad": int,
                "precioUnitario": float
            }
        ],
        "direccionEnvio": str,
        "telefonoContacto": str (optional, will use user's phone if not provided),
        "notaEspecial": str (optional)
    }
    """
    try:
        # Validate required fields
        if not payload.get("productos") or len(payload.get("productos", [])) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "El carrito está vacío."}
            )
        
        direccion_entrega = payload.get("direccionEnvio") or payload.get("direccion_entrega")
        if not direccion_entrega or len(direccion_entrega.strip()) < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "La dirección de envío debe tener al menos 10 caracteres."}
            )
        
        # Get user's phone if not provided
        usuario = db.query(models.Usuario).filter(models.Usuario.id == current_user.id).first()
        if not usuario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Usuario no encontrado."}
            )
        
        telefono_contacto = payload.get("telefonoContacto") or payload.get("telefono_contacto") or usuario.telefono
        if not telefono_contacto:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Debes proporcionar un número de teléfono de contacto."}
            )
        
        # Validate phone format (7-15 digits)
        if not telefono_contacto.replace("+", "").replace("-", "").replace(" ", "").isdigit():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "El número de teléfono debe contener solo dígitos."}
            )
        
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
        
        # Process items and calculate subtotal
        subtotal = 0
        productos = payload.get("productos", [])
        
        for item in productos:
            # Support both formats: sku/producto_id
            producto_id = int(item.get("sku") or item.get("producto_id") or item.get("id"))
            cantidad = int(item.get("cantidad") or item.get("quantity") or 1)
            precio_unitario = float(item.get("precioUnitario") or item.get("precio_unitario") or item.get("precio") or 0.0)
            
            if cantidad <= 0:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"status": "error", "message": f"La cantidad del producto {producto_id} debe ser mayor a 0."}
                )
            
            if precio_unitario < 0:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"status": "error", "message": f"El precio del producto {producto_id} no puede ser negativo."}
                )
            
            subtotal += cantidad * precio_unitario
            
            pedido_item = models.PedidoItem(
                pedido_id=pedido.id,
                producto_id=producto_id,
                cantidad=cantidad,
                precio_unitario=precio_unitario,
            )
            db.add(pedido_item)
        
        # Get shipping cost and payment method from payload
        costo_envio = float(payload.get("costoEnvio") or payload.get("costo_envio") or 0.0)
        metodo_pago = payload.get("metodoPago") or payload.get("metodo_pago") or "Efectivo"
        
        # Calculate total
        total = subtotal + costo_envio
        
        # Update pedido with all information
        pedido.subtotal = subtotal
        pedido.costo_envio = costo_envio
        pedido.metodo_pago = metodo_pago
        pedido.total = total
        db.commit()
        db.refresh(pedido)
        
        logger.info(f"Order created: pedido_id={pedido.id}, usuario_id={current_user.id}, total={total}")
        
        return _pedido_to_response(db, pedido)
        
    except HTTPException:
        raise
    except ValueError as e:
        db.rollback()
        logger.error(f"Validation error creating order: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": f"Error de validación: {str(e)}"}
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating order: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Error interno al procesar el pedido."}
        )


@router.get("/", response_model=List[PedidoResponse])
async def get_user_orders(
    current_user: UsuarioPublicResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all orders for the authenticated user
    """
    try:
        pedidos = (
            db.query(models.Pedido)
            .filter(models.Pedido.usuario_id == current_user.id)
            .order_by(desc(models.Pedido.fecha_creacion))
            .all()
        )
        return [_pedido_to_response(db, p) for p in pedidos]
    except Exception as e:
        logger.error(f"Error fetching user orders: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Error al obtener los pedidos."}
        )


@router.get("/{pedido_id}", response_model=PedidoResponse)
async def get_user_order(
    pedido_id: int,
    current_user: UsuarioPublicResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific order by ID (only if it belongs to the authenticated user)
    """
    try:
        pedido = db.query(models.Pedido).filter(
            models.Pedido.id == pedido_id,
            models.Pedido.usuario_id == current_user.id
        ).first()
        
        if not pedido:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Pedido no encontrado."}
            )
        
        return _pedido_to_response(db, pedido)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching order {pedido_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Error al obtener el pedido."}
        )

