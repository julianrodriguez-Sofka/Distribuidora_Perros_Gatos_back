"""
Products router: Create, Read, Update products for admin
Handles HU_CREATE_PRODUCT
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Body, Request, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from app.schemas import ProductoCreate, ProductoResponse, ProductoUpdate, ProductoImagenResponse
from app.database import get_db
import logging
import base64
import json
import os
from app.config import settings
from app.utils.rabbitmq import publish_message_safe
from app.utils.constants import (
    MIN_PRODUCT_NAME_LENGTH,
    MIN_PRODUCT_DESCRIPTION_LENGTH,
    MIN_PRODUCT_PRICE,
    MIN_PRODUCT_WEIGHT_GRAMS,
    MAX_PAGE_SIZE
)
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
import time
import uuid

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/productos",
    tags=["products"]
)


@router.post("")
async def create_product(
    request: Request,
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Create new product with details
    
    Requirements (HU_CREATE_PRODUCT):
    - Validates product name, price, weight, category, subcategory
    - Price > 0, weight > 0
    - Category and subcategory must exist
    - Publishes productos.crear queue message
    - Handles image uploads separately
    """
    # Basic producer-side validations (fields, image format/size, numeric values)
    # AC2: Missing required fields -> specific error message
    # Support both application/json and multipart/form-data with a 'payload' field
    content_type = request.headers.get('content-type', '')
    payload = None
    if content_type.startswith('multipart/form-data'):
        form = await request.form()
        # payload may be a JSON string in the form field 'payload'
        raw = form.get('payload')
        if raw:
            if isinstance(raw, str):
                try:
                    payload = json.loads(raw)
                except Exception:
                    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "El campo 'payload' debe ser JSON válido."})
            else:
                # Unexpected type, attempt to convert
                try:
                    payload = json.loads(str(raw))
                except Exception:
                    payload = None
        else:
            # Support clients sending fields directly in form without payload wrapper
            payload = {}
            for k, v in form.multi_items():
                # skip file fields
                if k == 'file':
                    continue
                payload[k] = v
    else:
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "Validation error", "errors": [{"field": "body -> payload", "message": "Input should be a valid dictionary", "type": "dict_type"}]})

    # payload is now a dict parsed from JSON or form
    nombre = payload.get('nombre') if isinstance(payload, dict) else None
    descripcion = payload.get('descripcion') if isinstance(payload, dict) else None
    precio = payload.get('precio') if isinstance(payload, dict) else None
    peso_gramos = (payload.get('peso_gramos') or payload.get('peso')) if isinstance(payload, dict) else None
    categoria_id = (payload.get('categoria_id') or payload.get('categoria')) if isinstance(payload, dict) else None
    subcategoria_id = (payload.get('subcategoria_id') or payload.get('subcategoria')) if isinstance(payload, dict) else None

    required_fields = [nombre, descripcion, precio, peso_gramos, categoria_id, subcategoria_id]
    if any(f is None for f in required_fields):
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "Por favor, completa todos los campos obligatorios."})

    # Field-specific validations using constants
    if not isinstance(nombre, str) or len(nombre.strip()) < MIN_PRODUCT_NAME_LENGTH:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": f"El nombre debe tener al menos {MIN_PRODUCT_NAME_LENGTH} caracteres."})

    if not isinstance(descripcion, str) or len(descripcion.strip()) < MIN_PRODUCT_DESCRIPTION_LENGTH:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": f"La descripción debe tener al menos {MIN_PRODUCT_DESCRIPTION_LENGTH} caracteres."})

    try:
        precio = float(precio)
        if precio < MIN_PRODUCT_PRICE:
            raise ValueError()
    except Exception:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": f"El precio debe ser un número mayor a {MIN_PRODUCT_PRICE}."})

    try:
        peso_gramos = int(peso_gramos)
        if peso_gramos < MIN_PRODUCT_WEIGHT_GRAMS:
            raise ValueError()
    except Exception:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": f"El peso debe ser un entero mayor a {MIN_PRODUCT_WEIGHT_GRAMS} (gramos)."})

    imagen_b64 = None
    imagen_filename = None
    # Prefer file upload; if not provided, allow JSON-embedded base64
    if file is not None:
        # Validate filename and extension
        imagen_filename = file.filename or ""
        _, ext = os.path.splitext(imagen_filename.lower())
        if ext not in settings.ALLOWED_IMAGE_EXTENSIONS:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "Formato o tamaño de imagen no válido."})

        # Read file content to check size and encode
        contents = await file.read()
        if len(contents) > settings.MAX_FILE_SIZE:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "Formato o tamaño de imagen no válido."})

        # Base64 encode so the worker can store it
        try:
            imagen_b64 = base64.b64encode(contents).decode('utf-8')
        finally:
            await file.close()

    # Build message payload for RabbitMQ. Consumer will perform uniqueness and category checks.
    cantidad_disponible = payload.get('cantidad_disponible', 0)

    # Resolve categoria_id and subcategoria_id: allow the client to send either an integer id
    # or a name string (e.g. "Perros"). If a name is provided, look it up in the DB.
    def resolve_category(value, table_name, db_session):
        # try integer first
        try:
            return int(value)
        except Exception:
            pass
        # otherwise try lookup by name (case-insensitive)
        try:
            q = text(f"SELECT id FROM {table_name} WHERE LOWER(nombre) = :name")
            res = db.execute(q, {"name": str(value).strip().lower()}).fetchone()
            if res:
                return int(res.id)
        except Exception:
            return None
        return None

    categoria_resolved = resolve_category(categoria_id, 'Categorias', db)
    subcategoria_resolved = resolve_category(subcategoria_id, 'Subcategorias', db)

    if categoria_resolved is None:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "Categoría no encontrada o id inválido."})
    if subcategoria_resolved is None:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "Subcategoría no encontrada o id inválido."})

    message = {
        "nombre": nombre.strip(),
        "descripcion": descripcion.strip(),
        "precio": float(precio),
        "peso_gramos": int(peso_gramos),
        "categoria_id": int(categoria_resolved),
        "subcategoria_id": int(subcategoria_resolved),
        "cantidad_disponible": int(cantidad_disponible or 0),
    }
    # Allow cliente to send imagen_b64 and imagen_filename inside the JSON payload
    if not imagen_b64:
        imagen_b64 = payload.get('imagen_b64')
    if not imagen_filename:
        imagen_filename = payload.get('imagen_filename')

    if imagen_b64 and imagen_filename:
        message.update({"imagen_filename": imagen_filename, "imagen_b64": imagen_b64})

    # Publish message to RabbitMQ
    # AC5: Prevent duplicate product names (case-insensitive) at Producer level
    try:
        existing = db.execute(text("SELECT id FROM Productos WHERE LOWER(nombre) = :name"), {"name": nombre.strip().lower()}).first()
    except SQLAlchemyError as err:
        logger.exception("Error checking existing product name in DB: %s", err)
        db.rollback()
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": "Error interno al verificar duplicados."})

    if existing:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "Ya existe un producto con ese nombre."})

    # Publish to RabbitMQ (connection is persistent, no need to close)
    published = rabbitmq_producer.publish(queue_name="productos.crear", message=message, retry=True)
    if not published:
        logger.error(f"Failed to publish message to productos.crear after retries. Message: {message}")
        # Don't fail the request, but log the error
        # The worker can retry from the queue if needed

    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"status": "success", "message": "Producto creado exitosamente"})


@router.get("", response_model=List[ProductoResponse])
async def list_products(
    categoria_id: int = Query(None, ge=1),
    subcategoria_id: int = Query(None, ge=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    List products with optional filtering by category/subcategory
    
    Requirements:
    - Filter by category_id and/or subcategory_id
    - Pagination support
    - Return active products
    """
    # Build base query with filters
    params = {"skip": int(skip), "limit": int(limit)}
    where_clauses = ["p.activo = 1"]
    if categoria_id:
        where_clauses.append("p.categoria_id = :categoria_id")
        params["categoria_id"] = int(categoria_id)
    if subcategoria_id:
        where_clauses.append("p.subcategoria_id = :subcategoria_id")
        params["subcategoria_id"] = int(subcategoria_id)

    where_sql = " AND ".join(where_clauses)

    try:
        q = text(f"SELECT p.id, p.nombre, p.descripcion, p.precio, p.peso_gramos, p.cantidad_disponible, p.categoria_id, p.subcategoria_id, p.activo, p.fecha_creacion FROM Productos p WHERE {where_sql} ORDER BY p.fecha_creacion DESC OFFSET :skip ROWS FETCH NEXT :limit ROWS ONLY")
        rows = db.execute(q, params).fetchall()
    except Exception as e:
        logger.exception("Error querying products: %s", e)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": "Error interno al listar productos."})

    products = []
    if not rows:
        return []

    # Collect category/subcategory ids to fetch names in batch
    cat_ids = set()
    subcat_ids = set()
    prod_ids = []
    for r in rows:
        prod_ids.append(r.id)
        if r.categoria_id:
            cat_ids.add(r.categoria_id)
        if r.subcategoria_id:
            subcat_ids.add(r.subcategoria_id)

    cats = {}
    subcats = {}
    try:
        if cat_ids:
            # Use parameterized query to prevent SQL injection
            cat_ids_list = [int(x) for x in cat_ids]
            placeholders = ','.join([f':cat_id_{i}' for i in range(len(cat_ids_list))])
            params = {f'cat_id_{i}': cat_id for i, cat_id in enumerate(cat_ids_list)}
            qcat = text(f"SELECT id, nombre, fecha_creacion AS created_at, fecha_actualizacion AS updated_at FROM Categorias WHERE id IN ({placeholders})")
            for c in db.execute(qcat, params).fetchall():
                cats[c.id] = {"id": c.id, "nombre": c.nombre, "created_at": c.created_at, "updated_at": c.updated_at}
        if subcat_ids:
            # Use parameterized query to prevent SQL injection
            subcat_ids_list = [int(x) for x in subcat_ids]
            placeholders = ','.join([f':subcat_id_{i}' for i in range(len(subcat_ids_list))])
            params = {f'subcat_id_{i}': subcat_id for i, subcat_id in enumerate(subcat_ids_list)}
            qsub = text(f"SELECT id, categoria_id, nombre, fecha_creacion AS created_at FROM Subcategorias WHERE id IN ({placeholders})")
            for s in db.execute(qsub, params).fetchall():
                subcats[s.id] = {"id": s.id, "categoria_id": s.categoria_id, "nombre": s.nombre, "created_at": s.created_at, "updated_at": s.created_at}
    except SQLAlchemyError:
        # Non-fatal: proceed without names
        logger.exception("Error fetching category/subcategory names")

    # Fetch images for products in batch (using parameterized query)
    images_map = {}
    try:
        if prod_ids:
            prod_ids_list = [int(x) for x in prod_ids]
            placeholders = ','.join([f':prod_id_{i}' for i in range(len(prod_ids_list))])
            params = {f'prod_id_{i}': prod_id for i, prod_id in enumerate(prod_ids_list)}
            qimg = text(f"SELECT producto_id, ruta_imagen FROM ProductoImagenes WHERE producto_id IN ({placeholders}) ORDER BY orden ASC")
            for img in db.execute(qimg, params).fetchall():
                images_map.setdefault(img.producto_id, []).append(img.ruta_imagen)
    except SQLAlchemyError:
        logger.exception("Error fetching product images")

    for r in rows:
        prod = {
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
            "imagenes": images_map.get(r.id, [])
        }
        products.append(prod)

    return products


@router.get("/{producto_id}", response_model=ProductoResponse)
async def get_product(producto_id: int, include_inactive: bool = Query(False), db: Session = Depends(get_db)):
    """
    Get product details

    - Returns full product information including images, category and subcategory
    - By default only active products are returned (activo = 1). Set `include_inactive=true` to allow fetching inactive products for admin purposes.
    """
    # Build query depending on include_inactive flag
    try:
        if include_inactive:
            q = text("SELECT id, nombre, descripcion, precio, peso_gramos, cantidad_disponible, categoria_id, subcategoria_id, activo, fecha_creacion, fecha_actualizacion FROM Productos WHERE id = :id")
            row = db.execute(q, {"id": producto_id}).first()
        else:
            q = text("SELECT id, nombre, descripcion, precio, peso_gramos, cantidad_disponible, categoria_id, subcategoria_id, activo, fecha_creacion, fecha_actualizacion FROM Productos WHERE id = :id AND activo = 1")
            row = db.execute(q, {"id": producto_id}).first()
    except Exception as e:
        logger.exception("Error querying product by id: %s", e)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": "Error interno al obtener el producto."})

    if not row:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"status": "error", "message": "Producto no encontrado."})

    producto = {
        "id": int(row.id),
        "nombre": row.nombre,
        "descripcion": row.descripcion,
        "precio": float(row.precio),
        "peso_gramos": int(row.peso_gramos),
        "cantidad_disponible": int(row.cantidad_disponible or 0),
        "categoria_id": int(row.categoria_id) if row.categoria_id is not None else None,
        "subcategoria_id": int(row.subcategoria_id) if row.subcategoria_id is not None else None,
        "activo": bool(row.activo),
        "fecha_creacion": row.fecha_creacion
    }

    # Fetch category and subcategory names
    try:
        cat_row = None
        sub_row = None
        if producto['categoria_id']:
            cat_row = db.execute(text("SELECT id, nombre, fecha_creacion AS created_at, fecha_actualizacion AS updated_at FROM Categorias WHERE id = :id"), {"id": producto['categoria_id']}).first()
        if producto['subcategoria_id']:
            sub_row = db.execute(text("SELECT id, categoria_id, nombre, fecha_creacion AS created_at FROM Subcategorias WHERE id = :id"), {"id": producto['subcategoria_id']}).first()
        producto['categoria'] = {"id": cat_row.id, "nombre": cat_row.nombre, "created_at": cat_row.created_at, "updated_at": cat_row.updated_at} if cat_row else None
        producto['subcategoria'] = {"id": sub_row.id, "categoria_id": sub_row.categoria_id, "nombre": sub_row.nombre, "created_at": sub_row.created_at, "updated_at": sub_row.created_at} if sub_row else None
    except Exception:
        logger.exception("Error fetching category/subcategory for product %s", producto_id)
        producto['categoria'] = None
        producto['subcategoria'] = None

    # Fetch images
    try:
        imgs = []
        qimg = text("SELECT ruta_imagen FROM ProductoImagenes WHERE producto_id = :id ORDER BY orden ASC")
        for img in db.execute(qimg, {"id": producto_id}).fetchall():
            imgs.append(img.ruta_imagen)
        producto['imagenes'] = imgs
    except Exception:
        logger.exception("Error fetching images for product %s", producto_id)
        producto['imagenes'] = []

    return producto


@router.put("/{producto_id}", response_model=ProductoResponse, tags=["Inventory","Products"])
async def update_product(
    producto_id: int,
    request: ProductoUpdate,
    db: Session = Depends(get_db)
):
    """
    Update product information
    
    Requirements (HU_CREATE_PRODUCT):
    - Update name, price, weight, category, subcategory
    - Validates all fields
    - Publishes productos.actualizar queue message
    """
    # Fetch existing product (allow updating activo as well)
    try:
        existing = db.execute(text("SELECT * FROM Productos WHERE id = :id"), {"id": producto_id}).first()
    except Exception as e:
        logger.exception("Error fetching product for update: %s", e)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": "Error interno al verificar producto."})

    if not existing:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"status": "error", "message": "Producto no encontrado."})

    data = request.model_dump(exclude_unset=True) if hasattr(request, 'model_dump') else request.dict(exclude_unset=True)
    if not data:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "No se proporcionaron campos para actualizar."})

    # Validate nombre if provided (only validate length on update — allow same names)
    if 'nombre' in data and data.get('nombre'):
        nombre_val = data.get('nombre').strip()
        if len(nombre_val) < 2:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "El nombre debe tener al menos 2 caracteres."})

    # Validate numeric constraints (Pydantic already enforces but double-check)
    if 'precio' in data:
        try:
            precio = float(data.get('precio'))
            if precio <= 0:
                raise ValueError()
        except Exception:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "El precio debe ser un número mayor a 0."})

    if 'peso_gramos' in data:
        try:
            peso = int(data.get('peso_gramos'))
            if peso <= 0:
                raise ValueError()
        except Exception:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "El peso debe ser un entero mayor a 0 (gramos)."})

    if 'cantidad_disponible' in data:
        try:
            cant = int(data.get('cantidad_disponible'))
            if cant < 0:
                raise ValueError()
        except Exception:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "La cantidad disponible debe ser un entero >= 0."})

    # If categoria_id or subcategoria_id provided, validate existence and consistency
    if 'categoria_id' in data:
        try:
            cat = db.execute(text("SELECT id FROM Categorias WHERE id = :id AND activo = 1"), {"id": int(data.get('categoria_id'))}).first()
        except Exception as e:
            logger.exception("Error checking categoria during update: %s", e)
            return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": "Error interno al verificar categoría."})
        if not cat:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "Categoría no encontrada."})

    if 'subcategoria_id' in data:
        try:
            sub = db.execute(text("SELECT id, categoria_id FROM Subcategorias WHERE id = :id AND activo = 1"), {"id": int(data.get('subcategoria_id'))}).first()
        except Exception as e:
            logger.exception("Error checking subcategoria during update: %s", e)
            return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": "Error interno al verificar subcategoría."})
        if not sub:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "Subcategoría no encontrada."})
        # If categoria_id provided, ensure subcategoria belongs to that categoria
        target_cat = data.get('categoria_id') if 'categoria_id' in data else existing.categoria_id
        if int(sub.categoria_id) != int(target_cat):
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "La subcategoría no pertenece a la categoría indicada."})

    # Build dynamic UPDATE statement
    set_clauses = []
    params = {"id": producto_id}
    column_map = {
        'nombre': 'nombre',
        'descripcion': 'descripcion',
        'precio': 'precio',
        'peso_gramos': 'peso_gramos',
        'categoria_id': 'categoria_id',
        'subcategoria_id': 'subcategoria_id',
        'cantidad_disponible': 'cantidad_disponible',
        'activo': 'activo'
    }

    for key, col in column_map.items():
        if key in data:
            set_clauses.append(f"{col} = :{key}")
            params[key] = data.get(key)

    if not set_clauses:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "No hay campos válidos para actualizar."})

    # Always update fecha_actualizacion
    set_sql = ", ".join(set_clauses) + ", fecha_actualizacion = GETUTCDATE()"
    upd_sql = text(f"UPDATE Productos SET {set_sql} OUTPUT inserted.id, inserted.nombre, inserted.descripcion, inserted.precio, inserted.peso_gramos, inserted.cantidad_disponible, inserted.categoria_id, inserted.subcategoria_id, inserted.activo, inserted.fecha_creacion, inserted.fecha_actualizacion WHERE id = :id")

    try:
        res = db.execute(upd_sql, params)
        row = res.fetchone()
        db.commit()
    except SQLAlchemyError as e:
        logger.exception("Error updating product: %s", e)
        db.rollback()
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": "Error interno al actualizar el producto."})

    if not row:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"status": "error", "message": "Producto no encontrado."})

    # Build response object
    producto = {
        "id": int(row.id),
        "nombre": row.nombre,
        "descripcion": row.descripcion,
        "precio": float(row.precio),
        "peso_gramos": int(row.peso_gramos),
        "cantidad_disponible": int(row.cantidad_disponible or 0),
        "categoria_id": int(row.categoria_id) if row.categoria_id is not None else None,
        "subcategoria_id": int(row.subcategoria_id) if row.subcategoria_id is not None else None,
        "activo": bool(row.activo),
        "fecha_creacion": row.fecha_creacion,
        "fecha_actualizacion": row.fecha_actualizacion
    }

    # Fetch category and subcategory names
    try:
        cat_row = None
        sub_row = None
        if producto['categoria_id']:
            cat_row = db.execute(text("SELECT id, nombre, fecha_creacion AS created_at, fecha_actualizacion AS updated_at FROM Categorias WHERE id = :id"), {"id": producto['categoria_id']}).first()
        if producto['subcategoria_id']:
            sub_row = db.execute(text("SELECT id, categoria_id, nombre, fecha_creacion AS created_at FROM Subcategorias WHERE id = :id"), {"id": producto['subcategoria_id']}).first()
        producto['categoria'] = {"id": cat_row.id, "nombre": cat_row.nombre, "created_at": cat_row.created_at, "updated_at": cat_row.updated_at} if cat_row else None
        producto['subcategoria'] = {"id": sub_row.id, "categoria_id": sub_row.categoria_id, "nombre": sub_row.nombre, "created_at": sub_row.created_at, "updated_at": sub_row.created_at} if sub_row else None
    except Exception:
        logger.exception("Error fetching category/subcategory names after update")
        producto['categoria'] = None
        producto['subcategoria'] = None

    # Fetch images
    try:
        imgs = []
        qimg = text("SELECT ruta_imagen FROM ProductoImagenes WHERE producto_id = :id ORDER BY orden ASC")
        for img in db.execute(qimg, {"id": producto_id}).fetchall():
            imgs.append(img.ruta_imagen)
        producto['imagenes'] = imgs
    except Exception:
        logger.exception("Error fetching images after update")
        producto['imagenes'] = []

    # Publish productos.actualizar message
    message = {"producto_id": producto_id, "producto": producto}
    published = publish_message_safe("productos.actualizar", message, retry=True)
    if not published:
        logger.warning(f"Failed to publish productos.actualizar message for product {producto_id}")

    return producto
 

@router.put("/{producto_id}/stock", tags=["Inventory","Products"])
async def update_product_stock(producto_id: int, request_obj: Request, db: Session = Depends(get_db)):
    """
    Producer endpoint: manually update product stock (only publishes message to RabbitMQ)

    Validations and exact messages required by the HU:
    - Missing required fields -> "Por favor, completa todos los campos obligatorios."
    - cantidad must be positive -> "La cantidad debe ser un número positivo."
    - If product missing -> "Producto no encontrado."
    - On success -> "Existencias actualizadas exitosamente"
    """
    # Parse body manually to provide exact validation messages
    try:
        payload = await request_obj.json()
    except Exception:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "Por favor, completa todos los campos obligatorios."})

    cantidad = payload.get('cantidad') if isinstance(payload, dict) else None
    if cantidad is None:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "Por favor, completa todos los campos obligatorios."})

    try:
        cantidad_val = int(cantidad)
        if cantidad_val <= 0:
            raise ValueError()
    except Exception:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "La cantidad debe ser un número positivo."})

    # Verify product exists
    try:
        prod = db.execute(text("SELECT id FROM Productos WHERE id = :id"), {"id": producto_id}).first()
    except Exception as e:
        logger.exception("Error checking product existence for stock update: %s", e)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": "Error interno al verificar producto."})

    if not prod or not getattr(prod, 'id', None):
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"status": "error", "message": "Producto no encontrado."})

    # Publish message to RabbitMQ in exact format required
    msg = {"requestId": str(uuid.uuid4()), "productoId": int(producto_id), "cantidad": int(cantidad_val)}
    published = publish_message_safe("inventario.reabastecer", msg, retry=True)
    if not published:
        logger.error(f"Failed to publish inventario.reabastecer message for product {producto_id}")
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": "Error interno al procesar la solicitud."})

    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "success", "message": "Existencias actualizadas exitosamente"})


@router.post("/{producto_id}/images")
async def upload_product_image(
    producto_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload product image
    
    Requirements (HU_CREATE_PRODUCT):
    - Max 10 MB file size
    - Allowed formats: jpg, jpeg, png, svg, webp
    - Stores in uploads/productos/{producto_id}/
    - Publishes productos.imagen.crear queue message
    """
    # 1. Validate product exists
    try:
        prod = db.execute(text("SELECT id FROM Productos WHERE id = :id AND activo = 1"), {"id": producto_id}).first()
    except Exception as e:
        logger.exception("Error checking product existence: %s", e)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": "Error interno al verificar producto."})

    if not prod:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"status": "error", "message": "Producto no encontrado."})

    # 2. Validate file size and extension
    filename = file.filename or ""
    _, ext = os.path.splitext(filename.lower())
    if ext not in settings.ALLOWED_IMAGE_EXTENSIONS:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "Formato o tamaño de imagen no válido."})

    try:
        contents = await file.read()
    except Exception as e:
        logger.exception("Error reading uploaded file: %s", e)
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "Error al leer el archivo de imagen."})

    if len(contents) > settings.MAX_FILE_SIZE:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "Formato o tamaño de imagen no válido."})

    # 3. Save file to uploads/productos/{producto_id}/
    try:
        upload_dir = os.path.abspath(settings.UPLOAD_DIR)
        product_dir = os.path.join(upload_dir, 'productos', str(producto_id))
        os.makedirs(product_dir, exist_ok=True)
        safe_name = f"{int(time.time())}_{''.join(c if c.isalnum() or c in '._-' else '_' for c in filename)}"
        file_path = os.path.join(product_dir, safe_name)
        with open(file_path, 'wb') as f:
            f.write(contents)
    except Exception as e:
        logger.exception("Error saving uploaded file: %s", e)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": "Error interno al guardar la imagen."})

    # 4. Create ProductoImagen record (within transaction)
    try:
        db.execute(text("INSERT INTO ProductoImagenes (producto_id, ruta_imagen, es_principal, orden) VALUES (:producto_id, :ruta_imagen, 1, 0)"), {"producto_id": producto_id, "ruta_imagen": file_path})
        db.commit()
    except SQLAlchemyError as e:
        logger.exception("Error inserting ProductoImagenes record: %s", e)
        db.rollback()
        # attempt to remove saved file on failure
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as cleanup_error:
            logger.error(f"Error removing file after DB failure: {cleanup_error}")
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": "Error interno al guardar la imagen en la base de datos."})

    # 5. Publish productos.imagen.crear queue message (non-blocking)
    message = {"producto_id": producto_id, "ruta_imagen": file_path}
    published = publish_message_safe("productos.imagen.crear", message, retry=True)
    if not published:
        logger.warning(f"Failed to publish productos.imagen.crear message for product {producto_id}, image {file_path}")
        # Not critical for upload success; return warning but 201

    return JSONResponse(status_code=status.HTTP_201_CREATED, content={"status": "success", "message": "Imagen subida correctamente", "ruta": file_path})


@router.get("/{producto_id}/images")
async def list_product_images(producto_id: int, db: Session = Depends(get_db)):
    """List all images for a product

    Returns an array of image records with `id`, `ruta_imagen`, `es_principal` and `orden`.
    """
    # Verify product exists and is active
    try:
        prod = db.execute(text("SELECT id FROM Productos WHERE id = :id AND activo = 1"), {"id": producto_id}).first()
    except Exception as e:
        logger.exception("Error checking product existence for images: %s", e)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": "Error interno al verificar producto."})

    if not prod:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"status": "error", "message": "Producto no encontrado."})

    try:
        q = text("SELECT id, producto_id, ruta_imagen, es_principal, orden FROM ProductoImagenes WHERE producto_id = :id ORDER BY orden ASC")
        rows = db.execute(q, {"id": producto_id}).fetchall()
    except Exception as e:
        logger.exception("Error querying product images: %s", e)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": "Error interno al listar imágenes."})

    images = []
    for r in rows:
        images.append({
            "id": int(r.id),
            "producto_id": int(r.producto_id),
            "ruta_imagen": r.ruta_imagen,
            "es_principal": bool(r.es_principal),
            "orden": int(r.orden)
        })

    return images


@router.get("/{producto_id}/images/{imagen_id}", response_model=ProductoImagenResponse)
async def get_product_image(producto_id: int, imagen_id: int, db: Session = Depends(get_db)):
    """Get a single product image by id

    - Validates that the product exists and is active
    - Validates that the image exists and belongs to the given product
    - Returns a `ProductoImagenResponse` object
    """
    # Verify product exists and is active
    try:
        prod = db.execute(text("SELECT id FROM Productos WHERE id = :id AND activo = 1"), {"id": producto_id}).first()
    except Exception as e:
        logger.exception("Error checking product existence for image fetch: %s", e)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": "Error interno al verificar producto."})

    if not prod:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"status": "error", "message": "Producto no encontrado."})

    # Fetch image record
    try:
        q = text("SELECT id, producto_id, ruta_imagen, es_principal, orden, fecha_creacion FROM ProductoImagenes WHERE id = :imagen_id AND producto_id = :producto_id")
        row = db.execute(q, {"imagen_id": imagen_id, "producto_id": producto_id}).first()
    except Exception as e:
        logger.exception("Error querying product image: %s", e)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": "Error interno al obtener la imagen."})

    if not row:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"status": "error", "message": "Imagen no encontrada."})

    image = {
        "id": int(row.id),
        "producto_id": int(row.producto_id),
        "ruta_imagen": row.ruta_imagen,
        "es_principal": bool(row.es_principal),
        "orden": int(row.orden),
    }

    return image


@router.put("/{producto_id}/images/{imagen_id}")
async def update_product_image(
    producto_id: int,
    imagen_id: int,
    file: UploadFile = File(...),
    es_principal: Optional[str] = Form(None),
    orden: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """Update product image (replace file and/or metadata)

    - Accepts multipart/form-data with optional `file` and optional fields `es_principal` and `orden`.
    - Validates product and image existence, validates file extension and size, saves new file, updates DB, deletes old file on success, and publishes `productos.imagen.actualizar`.
    """
    # 1. Verify product exists and is active
    try:
        prod = db.execute(text("SELECT id FROM Productos WHERE id = :id AND activo = 1"), {"id": producto_id}).first()
    except Exception as e:
        logger.exception("Error checking product existence for image update: %s", e)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": "Error interno al verificar producto."})

    if not prod:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"status": "error", "message": "Producto no encontrado."})

    # 2. Verify image exists and belongs to product
    try:
        img_row = db.execute(text("SELECT id, producto_id, ruta_imagen, es_principal, orden FROM ProductoImagenes WHERE id = :imagen_id AND producto_id = :producto_id"), {"imagen_id": imagen_id, "producto_id": producto_id}).first()
    except Exception as e:
        logger.exception("Error fetching image for update: %s", e)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": "Error interno al obtener la imagen."})

    if not img_row:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"status": "error", "message": "Imagen no encontrada."})

    old_path = img_row.ruta_imagen

    # 3. Use injected form params and file UploadFile
    provided_file = file
    new_path = None
    # Normalize es_principal value (can be '0'/'1' or 'true'/'false')
    if es_principal is not None:
        if isinstance(es_principal, str):
            es_principal = es_principal.lower() in ('1', 'true', 'yes')
        else:
            es_principal = bool(es_principal)

    # Validate orden if provided
    if orden is not None:
        try:
            orden = int(orden)
        except Exception:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "El campo 'orden' debe ser un entero."})

    # 4. If file provided, validate and save new file
    if provided_file is not None:
        filename = getattr(provided_file, 'filename', '') or ''
        _, ext = os.path.splitext(filename.lower())
        if ext not in settings.ALLOWED_IMAGE_EXTENSIONS:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "Formato o tamaño de imagen no válido."})

        try:
            contents = await provided_file.read()
        except Exception as e:
            logger.exception("Error reading provided file for update: %s", e)
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "Error al leer el archivo de imagen."})

        if len(contents) > settings.MAX_FILE_SIZE:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "Formato o tamaño de imagen no válido."})

        # Save new file
        try:
            upload_dir = os.path.abspath(settings.UPLOAD_DIR)
            product_dir = os.path.join(upload_dir, 'productos', str(producto_id))
            os.makedirs(product_dir, exist_ok=True)
            safe_name = f"{int(time.time())}_{''.join(c if c.isalnum() or c in '._-' else '_' for c in filename)}"
            new_path = os.path.join(product_dir, safe_name)
            with open(new_path, 'wb') as f:
                f.write(contents)
        except Exception as e:
            logger.exception("Error saving new image file during update: %s", e)
            return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": "Error interno al guardar la nueva imagen."})

    # 5. Build UPDATE statement for metadata and ruta_imagen if changed
    set_clauses = []
    params = {"imagen_id": imagen_id, "producto_id": producto_id}
    if new_path:
        set_clauses.append("ruta_imagen = :ruta_imagen")
        params['ruta_imagen'] = new_path
    if es_principal is not None:
        set_clauses.append("es_principal = :es_principal")
        params['es_principal'] = 1 if es_principal else 0
    if orden is not None:
        if orden < 0:
            # cleanup new file if saved
            try:
                if new_path and os.path.exists(new_path):
                    os.remove(new_path)
            except Exception:
                pass
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "El campo 'orden' debe ser un entero >= 0."})
        set_clauses.append("orden = :orden")
        params['orden'] = orden

    if not set_clauses:
        # Nothing to update
        # If file was uploaded but no metadata, still update ruta_imagen
        if new_path:
            set_clauses.append("ruta_imagen = :ruta_imagen")
            params['ruta_imagen'] = new_path
        else:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "No se proporcionaron campos para actualizar."})

    set_sql = ", ".join(set_clauses) + ", fecha_creacion = fecha_creacion"
    # perform update and return the inserted/updated record
    upd_sql = text(f"UPDATE ProductoImagenes SET {set_sql} OUTPUT inserted.id, inserted.producto_id, inserted.ruta_imagen, inserted.es_principal, inserted.orden, inserted.fecha_creacion WHERE id = :imagen_id AND producto_id = :producto_id")

    try:
        res = db.execute(upd_sql, params)
        row = res.fetchone()
        db.commit()
    except Exception as e:
        logger.exception("Error updating ProductoImagenes: %s", e)
        db.rollback()
        # remove new file to avoid orphan
        try:
            if new_path and os.path.exists(new_path):
                os.remove(new_path)
        except Exception:
            pass
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": "Error interno al actualizar la imagen en la base de datos."})

    if not row:
        # Shouldn't happen but handle
        try:
            if new_path and os.path.exists(new_path):
                os.remove(new_path)
        except Exception:
            pass
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"status": "error", "message": "Imagen no encontrada."})

    # 6. Remove old file if a new one was saved
    if new_path and old_path and old_path != new_path:
        try:
            if os.path.exists(old_path):
                os.remove(old_path)
        except Exception:
            logger.exception("Failed to remove old image file: %s", old_path)

    # 7. Publish productos.imagen.actualizar message (non-blocking)
    message = {"producto_id": producto_id, "imagen_id": imagen_id, "ruta_imagen": row.ruta_imagen, "es_principal": bool(row.es_principal), "orden": int(row.orden)}
    published = publish_message_safe("productos.imagen.actualizar", message, retry=True)
    if not published:
        logger.warning(f"Failed to publish productos.imagen.actualizar message for product {producto_id}, image {imagen_id}")

    result = {
        "id": int(row.id),
        "producto_id": int(row.producto_id),
        "ruta_imagen": row.ruta_imagen,
        "es_principal": bool(row.es_principal),
        "orden": int(row.orden)
    }

    return result


@router.delete("/{producto_id}/images/{imagen_id}")
async def delete_product_image(
    producto_id: int,
    imagen_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete product image
    
    Requirements (HU_CREATE_PRODUCT):
    - Delete image file and database record
    - Publishes productos.imagen.eliminar queue message
    """
    # 1. Verify product exists and is active
    try:
        prod = db.execute(text("SELECT id FROM Productos WHERE id = :id AND activo = 1"), {"id": producto_id}).first()
    except Exception as e:
        logger.exception("Error checking product existence for image delete: %s", e)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": "Error interno al verificar producto."})

    if not prod:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"status": "error", "message": "Producto no encontrado."})

    # 2. Fetch image record and ensure it belongs to product
    try:
        q = text("SELECT id, producto_id, ruta_imagen FROM ProductoImagenes WHERE id = :imagen_id AND producto_id = :producto_id")
        img = db.execute(q, {"imagen_id": imagen_id, "producto_id": producto_id}).first()
    except Exception as e:
        logger.exception("Error querying image for delete: %s", e)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": "Error interno al obtener la imagen."})

    if not img:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"status": "error", "message": "Imagen no encontrada."})

    ruta = img.ruta_imagen if hasattr(img, 'ruta_imagen') else None

    # 3. Delete the DB record inside a transaction
    try:
        del_sql = text("DELETE FROM ProductoImagenes WHERE id = :imagen_id AND producto_id = :producto_id")
        res = db.execute(del_sql, {"imagen_id": imagen_id, "producto_id": producto_id})
        # Check rows affected when possible
        try:
            rowcount = res.rowcount
        except Exception:
            rowcount = None
        db.commit()
    except Exception as e:
        logger.exception("Error deleting ProductoImagenes record: %s", e)
        db.rollback()
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": "Error interno al eliminar la imagen."})

    if rowcount == 0:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"status": "error", "message": "Imagen no encontrada."})

    # 4. Attempt to remove physical file if it exists
    if ruta:
        try:
            if os.path.exists(ruta):
                os.remove(ruta)
        except Exception:
            logger.exception("Failed to remove image file: %s", ruta)

    # 5. Publish productos.imagen.eliminar message (non-blocking)
    message = {"producto_id": int(producto_id), "imagen_id": int(imagen_id), "ruta_imagen": ruta}
    published = publish_message_safe("productos.imagen.eliminar", message, retry=True)
    if not published:
        logger.warning(f"Failed to publish productos.imagen.eliminar message for product {producto_id}, image {imagen_id}")

    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "success", "message": "Imagen eliminada correctamente"})


@router.delete("/{producto_id}", tags=["Inventory","Products"])
async def delete_product(producto_id: int, db: Session = Depends(get_db)):
    """
    Soft delete product (mark as inactive)
    
    Requirements:
    - Set activo=False instead of deleting
    - Publishes productos.eliminar queue message
    """
    # 1. Verify product exists
    try:
        prod = db.execute(text("SELECT id FROM Productos WHERE id = :id"), {"id": producto_id}).first()
    except Exception as e:
        logger.exception("Error checking product for delete: %s", e)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": "Error interno al verificar producto."})

    if not prod or not getattr(prod, 'id', None):
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"status": "error", "message": "Producto no encontrado."})

    # 2. Check inventory history: if exists, do not allow deletion
    try:
        hist = db.execute(text("SELECT TOP 1 1 AS exists_flag FROM InventarioHistorial WHERE producto_id = :id"), {"id": producto_id}).first()
    except Exception as e:
        logger.exception("Error checking InventarioHistorial for product delete: %s", e)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": "Error interno al verificar historial de inventario."})

    if hist:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "error", "message": "No se puede eliminar el producto porque tiene movimientos registrados."})

    # 3. Publish productos.eliminar message to RabbitMQ (non-blocking)
    message = {"requestId": str(uuid.uuid4()), "productoId": int(producto_id)}
    published = publish_message_safe("productos.eliminar", message, retry=True)
    if not published:
        logger.warning(f"Failed to publish productos.eliminar message for product {producto_id}")
        # Not fatal for client response

    # 4. Also mark product as inactive in DB (soft delete) - within transaction
    try:
        upd = text("UPDATE Productos SET activo = 0, fecha_actualizacion = GETUTCDATE() WHERE id = :id")
        res = db.execute(upd, {"id": producto_id})
        db.commit()
    except SQLAlchemyError as e:
        logger.exception("Error marking product inactive: %s", e)
        db.rollback()
        # still return success to client but log

    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "success", "message": "Producto eliminado exitosamente"})
