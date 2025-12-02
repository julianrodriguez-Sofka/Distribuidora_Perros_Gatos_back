"""
Home/Products router: Public product browsing and cart management
Handles HU_HOME_PRODUCTS
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from app.schemas import ProductoResponse, CartResponse, CartItemCreate, CartItemResponse
from app.database import get_db
from app.utils.security import security_utils
import logging
from sqlalchemy import text
import uuid
from app.utils.rabbitmq import rabbitmq_producer
import time

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["home-products"]
)


@router.get("/home/productos", response_model=List[ProductoResponse])
async def browse_products(
    categoria_id: int = Query(None),
    subcategoria_id: int = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(12, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Browse products by category/subcategory

    Requirements (HU_HOME_PRODUCTS):
    - Return hierarchical structure: Category -> Subcategory -> Products
    - Filter by categoria_id and/or subcategoria_id
    - Only return active products with stock > 0
    - Pagination support
    - Default limit 12 (typical grid layout)
    """
    params = {"skip": int(skip), "limit": int(limit)}
    where = ["p.activo = 1", "p.cantidad_disponible > 0"]
    if categoria_id:
        where.append("p.categoria_id = :categoria_id")
        params["categoria_id"] = int(categoria_id)
    if subcategoria_id:
        where.append("p.subcategoria_id = :subcategoria_id")
        params["subcategoria_id"] = int(subcategoria_id)

    where_sql = " AND ".join(where)
    try:
        q = text(
            f"SELECT p.id, p.nombre, p.descripcion, p.precio, p.peso_gramos, p.cantidad_disponible, p.categoria_id, p.subcategoria_id, p.activo, p.fecha_creacion FROM Productos p WHERE {where_sql} ORDER BY p.fecha_creacion DESC OFFSET :skip ROWS FETCH NEXT :limit ROWS ONLY"
        )
        rows = db.execute(q, params).fetchall()
    except Exception as e:
        logger.exception("Error querying home products: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al listar productos.")

    products = []
    if not rows:
        return []

    # collect ids for batch fetch
    prod_ids = [r.id for r in rows]
    cat_ids = set(r.categoria_id for r in rows if r.categoria_id)
    subcat_ids = set(r.subcategoria_id for r in rows if r.subcategoria_id)

    cats = {}
    subcats = {}
    try:
        if cat_ids:
            qcat = text(
                f"SELECT id, nombre, fecha_creacion, fecha_actualizacion FROM Categorias WHERE id IN ({', '.join([str(int(x)) for x in cat_ids])})"
            )
            for c in db.execute(qcat).fetchall():
                cats[c.id] = {
                    "id": c.id,
                    "nombre": c.nombre,
                    "created_at": c.fecha_creacion,
                    "updated_at": c.fecha_actualizacion,
                    "subcategorias": []
                }
        if subcat_ids:
            qsub = text(
                f"SELECT id, nombre, categoria_id, fecha_creacion FROM Subcategorias WHERE id IN ({', '.join([str(int(x)) for x in subcat_ids])})"
            )
            for s in db.execute(qsub).fetchall():
                subcats[s.id] = {
                    "id": s.id,
                    "nombre": s.nombre,
                    "categoria_id": s.categoria_id,
                    "created_at": s.fecha_creacion,
                    "updated_at": None  # Subcategorias no tiene fecha_actualizacion
                }
    except Exception:
        logger.exception("Error fetching category/subcategory names")

    # images map
    images_map = {}
    try:
        if prod_ids:
            qimg = text(
                f"SELECT producto_id, ruta_imagen FROM ProductoImagenes WHERE producto_id IN ({', '.join([str(int(x)) for x in prod_ids])}) ORDER BY orden ASC"
            )
            for img in db.execute(qimg).fetchall():
                images_map.setdefault(img.producto_id, []).append(img.ruta_imagen)
    except Exception:
        logger.exception("Error fetching product images")

    for r in rows:
        products.append(
            {
                "id": int(r.id),
                "nombre": r.nombre,
                "descripcion": r.descripcion,
                "precio": float(r.precio),
                "peso_gramos": int(r.peso_gramos),
                "cantidad_disponible": int(r.cantidad_disponible or 0),
                "categoria_id": int(r.categoria_id) if r.categoria_id is not None else None,
                "subcategoria_id": int(r.subcategoria_id) if r.subcategoria_id is not None else None,
                "activo": bool(r.activo),
                "fecha_creacion": r.fecha_creacion,
                "categoria": cats.get(r.categoria_id),
                "subcategoria": subcats.get(r.subcategoria_id),
                "imagenes": images_map.get(r.id, []),
            }
        )

    return products


@router.get("/cart")
async def get_cart(
    session_id: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Get current cart (anonymous or authenticated)
    
    Requirements (HU_HOME_PRODUCTS):
    - For anonymous users: use session_id from header/cookie
    - For authenticated users: use user_id from JWT
    - Return cart with items and total
    """
    # Determine usuario_id from JWT if provided
    usuario_id = None
    if authorization:
        try:
            token = authorization.split(" ")[-1]
            payload = security_utils.verify_jwt_token(token)
            usuario_id = payload.get('user_id') or payload.get('sub')
        except Exception:
            usuario_id = None

    cart_row = None
    try:
        if usuario_id:
            cart_row = db.execute(text("SELECT id, usuario_id, session_id FROM Carts WHERE usuario_id = :usuario_id"), {"usuario_id": usuario_id}).first()
        else:
            # anonymous flow: use session_id header to identify cart
            if not session_id:
                return {"id": None, "usuario_id": None, "session_id": None, "items": [], "total": 0.0}
            cart_row = db.execute(text("SELECT id, usuario_id, session_id FROM Carts WHERE session_id = :session_id"), {"session_id": session_id}).first()
    except Exception as e:
        logger.exception("Error querying cart: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al obtener el carrito.")

    if not cart_row:
        return {"id": None, "usuario_id": None, "session_id": session_id, "items": [], "total": 0.0}

    cart_id = cart_row.id
    items = []
    total = 0.0
    try:
        q = text("SELECT ci.id, ci.producto_id, ci.cantidad, p.precio FROM CartItems ci JOIN Productos p ON p.id = ci.producto_id WHERE ci.cart_id = :cart_id")
        for it in db.execute(q, {"cart_id": cart_id}).fetchall():
            subtotal = float(it.precio) * int(it.cantidad)
            total += subtotal
            items.append({"id": int(it.id), "producto_id": int(it.producto_id), "cantidad": int(it.cantidad), "precio_unitario": float(it.precio)})
    except Exception as e:
        logger.exception("Error fetching cart items: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al obtener los items del carrito.")

    return {"id": int(cart_id), "usuario_id": getattr(cart_row, 'usuario_id', None), "session_id": session_id, "items": items, "total": float(total)}


@router.post("/cart/add", response_model=CartResponse)
async def add_to_cart(
    request: CartItemCreate,
    session_id: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Add product to cart (anonymous or authenticated)
    
    Requirements (HU_HOME_PRODUCTS):
    - For anonymous: create cart if not exists, use session_id
    - For authenticated: use user cart
    - Validate product exists and stock available
    - If product already in cart: add to quantity (check stock limit)
    - Publishes cart.item.agregar queue message
    """
    # Validate input
    producto_id = int(request.producto_id)
    cantidad = int(request.cantidad)

    # 1. Validate producto exists and stock
    try:
        p = db.execute(text("SELECT id, precio, cantidad_disponible FROM Productos WHERE id = :id AND activo = 1"), {"id": producto_id}).first()
    except Exception as e:
        logger.exception("Error querying producto for cart add: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al validar producto.")

    if not p:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"status": "error", "message": "Producto no encontrado."})

    if cantidad <= 0:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "La cantidad debe ser un número entero positivo."})

    if int(p.cantidad_disponible) < cantidad:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"status": "error", "message": "Sin existencias"})

    # 2. Determine cart owner: prefer authenticated usuario_id from JWT
    usuario_id = None
    if authorization:
        try:
            token = authorization.split(" ")[-1]
            payload = security_utils.verify_jwt_token(token)
            usuario_id = payload.get('user_id') or payload.get('sub')
        except Exception:
            usuario_id = None

    # If authenticated, find or create cart for usuario_id
    if usuario_id:
        try:
            cart = db.execute(text("SELECT id FROM Carts WHERE usuario_id = :usuario_id"), {"usuario_id": usuario_id}).first()
            if not cart:
                db.execute(text("INSERT INTO Carts (usuario_id, created_at, updated_at) VALUES (:usuario_id, GETUTCDATE(), GETUTCDATE())"), {"usuario_id": usuario_id})
                db.commit()
                cart = db.execute(text("SELECT id FROM Carts WHERE usuario_id = :usuario_id"), {"usuario_id": usuario_id}).first()
        except Exception as e:
            logger.exception("Error creating/fetching cart for usuario: %s", e)
            db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al obtener carrito.")
        session_id = getattr(cart, 'session_id', None)
    else:
        # anonymous flow: create or use session_id
        if not session_id:
            session_id = str(uuid.uuid4())
            try:
                db.execute(text("INSERT INTO Carts (session_id, created_at, updated_at) VALUES (:session_id, GETUTCDATE(), GETUTCDATE())"), {"session_id": session_id})
                db.commit()
            except Exception as e:
                logger.exception("Error creating cart: %s", e)
                db.rollback()
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al crear carrito.")
        try:
            cart = db.execute(text("SELECT id FROM Carts WHERE session_id = :session_id"), {"session_id": session_id}).first()
            # If a session_id was provided but no cart exists yet, create it so anonymous users can continue
            if not cart:
                try:
                    db.execute(text("INSERT INTO Carts (session_id, created_at, updated_at) VALUES (:session_id, GETUTCDATE(), GETUTCDATE())"), {"session_id": session_id})
                    db.commit()
                except Exception as e_inner:
                    logger.exception("Error creating cart for provided session_id: %s", e_inner)
                    db.rollback()
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al crear carrito.")
                try:
                    cart = db.execute(text("SELECT id FROM Carts WHERE session_id = :session_id"), {"session_id": session_id}).first()
                except Exception as e2:
                    logger.exception("Error querying cart after create: %s", e2)
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al obtener carrito.")
        except Exception as e:
            logger.exception("Error querying cart after create: %s", e)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al obtener carrito.")

    if not cart:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": "Error interno al obtener carrito"})

    cart_id = int(cart.id)

    # 3. Check if product already in cart
    try:
        ci = db.execute(text("SELECT id, cantidad FROM CartItems WHERE cart_id = :cart_id AND producto_id = :producto_id"), {"cart_id": cart_id, "producto_id": producto_id}).first()
    except Exception as e:
        logger.exception("Error querying cart item: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al procesar carrito.")

    try:
        if ci:
            new_total = int(ci.cantidad) + cantidad
            if new_total > int(p.cantidad_disponible):
                return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"status": "error", "message": "Sin existencias"})
            # update quantity and refresh precio_unitario with current product price
            db.execute(text("UPDATE CartItems SET cantidad = :cantidad, precio_unitario = :precio_unitario WHERE id = :id"), {"cantidad": new_total, "precio_unitario": float(p.precio), "id": int(ci.id)})
        else:
            # insert with precio_unitario from product
            db.execute(text("INSERT INTO CartItems (cart_id, producto_id, cantidad, precio_unitario) VALUES (:cart_id, :producto_id, :cantidad, :precio_unitario)"), {"cart_id": cart_id, "producto_id": producto_id, "cantidad": cantidad, "precio_unitario": float(p.precio)})
        db.commit()
    except Exception as e:
        logger.exception("Error inserting/updating cart item: %s", e)
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al actualizar carrito.")

    # Publish cart event (optional)
    try:
        message = {"requestId": str(uuid.uuid4()), "action": "cart_add", "payload": {"cartId": cart_id, "productoId": producto_id, "cantidad": cantidad, "userId": None}, "meta": {"timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ')}}
        rabbitmq_producer.connect()
        rabbitmq_producer.publish(queue_name="cart.events", message=message)
    except Exception:
        logger.exception("Failed to publish cart.events - continuing")
    finally:
        try:
            rabbitmq_producer.close()
        except Exception:
            pass

    # Return updated cart
    # reuse get_cart logic
    return await get_cart(session_id=session_id, db=db)


@router.put("/cart/items/{item_id}")
async def update_cart_item(
    item_id: int,
    cantidad: int = Query(..., gt=0),
    session_id: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Update quantity of cart item
    
    Requirements (HU_HOME_PRODUCTS):
    - Validate new cantidad doesn't exceed stock
    - Publishes cart.item.actualizar queue message
    """
    # Validate input (cantidad already has Query gt=0 but return HU message)
    if cantidad is None or int(cantidad) <= 0:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "La cantidad debe ser un número entero positivo."})

    # Determine usuario_id from JWT if provided
    usuario_id = None
    if authorization:
        try:
            token = authorization.split(" ")[-1]
            payload = security_utils.verify_jwt_token(token)
            usuario_id = payload.get('user_id') or payload.get('sub')
        except Exception:
            usuario_id = None

    # Find the cart for the user or session
    try:
        if usuario_id:
            cart_row = db.execute(text("SELECT id FROM Carts WHERE usuario_id = :usuario_id"), {"usuario_id": usuario_id}).first()
            # if user has no cart but session_id is provided, try session fallback
            if not cart_row and session_id:
                cart_row = db.execute(text("SELECT id FROM Carts WHERE session_id = :session_id"), {"session_id": session_id}).first()
        else:
            if not session_id:
                return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "Por favor, completa todos los campos obligatorios."})
            cart_row = db.execute(text("SELECT id FROM Carts WHERE session_id = :session_id"), {"session_id": session_id}).first()
    except Exception as e:
        logger.exception("Error querying cart for update: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al obtener carrito.")

    if not cart_row:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"status": "error", "message": "Producto no encontrado."})

    cart_id = int(cart_row.id)

    # Fetch cart item and product stock
    try:
        q = text("SELECT ci.id, ci.cantidad, ci.producto_id, p.cantidad_disponible, p.precio FROM CartItems ci JOIN Productos p ON p.id = ci.producto_id WHERE ci.id = :item_id AND ci.cart_id = :cart_id")
        row = db.execute(q, {"item_id": item_id, "cart_id": cart_id}).first()
    except Exception as e:
        logger.exception("Error querying cart item for update: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al procesar carrito.")

    if not row:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"status": "error", "message": "Producto no encontrado."})

    producto_id = int(row.producto_id)
    disponible = int(row.cantidad_disponible or 0)

    if int(cantidad) > disponible:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"status": "error", "message": "Sin existencias"})

    # Update the CartItem (update cantidad and persist precio_unitario)
    try:
        db.execute(text("UPDATE CartItems SET cantidad = :cantidad, precio_unitario = :precio_unitario WHERE id = :id"), {"cantidad": int(cantidad), "precio_unitario": float(row.precio), "id": item_id})
        db.commit()
    except Exception as e:
        logger.exception("Error updating cart item: %s", e)
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al actualizar carrito.")

    # Publish event (optional)
    try:
        message = {"requestId": str(uuid.uuid4()), "action": "cart_update", "payload": {"cartId": cart_id, "itemId": item_id, "productoId": producto_id, "cantidad": int(cantidad), "userId": usuario_id}, "meta": {"timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ')}}
        rabbitmq_producer.connect()
        rabbitmq_producer.publish(queue_name="cart.events", message=message)
    except Exception:
        logger.exception("Failed to publish cart.events - continuing")
    finally:
        try:
            rabbitmq_producer.close()
        except Exception:
            pass

    return await get_cart(session_id=session_id, authorization=authorization, db=db)


@router.delete("/cart/items/{item_id}")
async def remove_from_cart(
    item_id: int,
    session_id: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Remove item from cart
    
    Requirements (HU_HOME_PRODUCTS):
    - Delete CartItem record
    - Publishes cart.item.eliminar queue message
    """
    # Determine usuario_id from JWT if provided
    usuario_id = None
    if authorization:
        try:
            token = authorization.split(" ")[-1]
            payload = security_utils.verify_jwt_token(token)
            usuario_id = payload.get('user_id') or payload.get('sub')
        except Exception:
            usuario_id = None

    # Find cart by usuario_id or session_id
    try:
        if usuario_id:
            cart_row = db.execute(text("SELECT id FROM Carts WHERE usuario_id = :usuario_id"), {"usuario_id": usuario_id}).first()
            if not cart_row and session_id:
                cart_row = db.execute(text("SELECT id FROM Carts WHERE session_id = :session_id"), {"session_id": session_id}).first()
        else:
            if not session_id:
                return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "Por favor, completa todos los campos obligatorios."})
            cart_row = db.execute(text("SELECT id FROM Carts WHERE session_id = :session_id"), {"session_id": session_id}).first()
    except Exception as e:
        logger.exception("Error querying cart for remove: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al obtener carrito.")

    if not cart_row:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"status": "error", "message": "Producto no encontrado."})

    cart_id = int(cart_row.id)

    # Check that the CartItem exists and belongs to the cart
    try:
        ci = db.execute(text("SELECT id, producto_id FROM CartItems WHERE id = :item_id AND cart_id = :cart_id"), {"item_id": item_id, "cart_id": cart_id}).first()
    except Exception as e:
        logger.exception("Error querying cart item for remove: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al procesar carrito.")

    if not ci:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"status": "error", "message": "Producto no encontrado."})

    producto_id = int(ci.producto_id)

    # Delete the CartItem
    try:
        db.execute(text("DELETE FROM CartItems WHERE id = :id AND cart_id = :cart_id"), {"id": item_id, "cart_id": cart_id})
        db.commit()
    except Exception as e:
        logger.exception("Error deleting cart item: %s", e)
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al eliminar item del carrito.")

    # Publish event
    try:
        message = {"requestId": str(uuid.uuid4()), "action": "cart_remove", "payload": {"cartId": cart_id, "itemId": item_id, "productoId": producto_id, "userId": usuario_id}, "meta": {"timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ')}}
        rabbitmq_producer.connect()
        rabbitmq_producer.publish(queue_name="cart.events", message=message)
    except Exception:
        logger.exception("Failed to publish cart.events - continuing")
    finally:
        try:
            rabbitmq_producer.close()
        except Exception:
            pass

    # Return updated cart
    return await get_cart(session_id=session_id, authorization=authorization, db=db)


@router.delete("/cart")
async def clear_cart(
    session_id: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Clear entire cart
    
    Requirements:
    - Delete all CartItems for cart
    - Publishes cart.vaciar queue message
    """
    # TODO: Implement clear cart logic
    # Determine usuario_id from JWT if provided (allow session-only clears too)
    usuario_id = None
    # Try to obtain Authorization header from request context if available via dependency
    # But this function signature doesn't accept authorization header; try retrieving from request headers via fastapi dependency is heavier
    # Simpler: accept that anonymous clear uses session_id header; authenticated clears handled via session_id or by adding Authorization header param if needed.

    if not session_id:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "Por favor, completa todos los campos obligatorios."})

    # Find cart by session_id
    try:
        cart_row = db.execute(text("SELECT id FROM Carts WHERE session_id = :session_id"), {"session_id": session_id}).first()
    except Exception as e:
        logger.exception("Error querying cart for clear: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al obtener carrito.")

    if not cart_row:
        # No cart found — nothing to clear
        return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "success", "message": "Carrito vacío"})

    cart_id = int(cart_row.id)

    # Delete all CartItems for cart
    try:
        db.execute(text("DELETE FROM CartItems WHERE cart_id = :cart_id"), {"cart_id": cart_id})
        db.commit()
    except Exception as e:
        logger.exception("Error clearing cart items: %s", e)
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al vaciar carrito.")

    # Publish cart.vaciar event (optional)
    try:
        message = {"requestId": str(uuid.uuid4()), "action": "cart_clear", "payload": {"cartId": cart_id, "userId": usuario_id}, "meta": {"timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ')}}
        rabbitmq_producer.connect()
        rabbitmq_producer.publish(queue_name="cart.vaciar", message=message)
    except Exception:
        logger.exception("Failed to publish cart.vaciar - continuing")
    finally:
        try:
            rabbitmq_producer.close()
        except Exception:
            pass

    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "success", "message": "Carrito vaciado"})
