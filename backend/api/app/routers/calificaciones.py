"""
Router para gestión de calificaciones de productos
Endpoints para crear, leer y obtener promedios de ratings
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.schemas import (
    CalificacionCreateRequest,
    CalificacionResponse,
    CalificacionesListResponse,
    PromedioCalificacionResponse,
    StandardResponse
)
from app.database import get_db
from app.utils.security import security_utils
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/calificaciones",
    tags=["calificaciones"]
)


@router.post("/productos/{producto_id}", response_model=StandardResponse, status_code=status.HTTP_201_CREATED)
async def crear_calificacion(
    producto_id: int,
    request: CalificacionCreateRequest,
    current_user: dict = Depends(security_utils.get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Crear una calificación para un producto
    - Puede ser anónima (sin usuario) o de usuario autenticado
    - Calificación de 1 a 5 estrellas
    - Comentario opcional
    """
    try:
        # Verificar que el producto existe
        producto_query = text("SELECT id FROM Productos WHERE id = :producto_id")
        producto = db.execute(producto_query, {"producto_id": producto_id}).fetchone()
        
        if not producto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Producto no encontrado"
            )
        
        # Obtener usuario_id si está autenticado
        usuario_id = current_user.get('user_id') if current_user else None
        
        # Insertar calificación
        insert_query = text("""
            INSERT INTO ProductoCalificaciones (producto_id, usuario_id, calificacion, comentario)
            VALUES (:producto_id, :usuario_id, :calificacion, :comentario)
        """)
        
        db.execute(insert_query, {
            "producto_id": producto_id,
            "usuario_id": usuario_id,
            "calificacion": request.calificacion,
            "comentario": request.comentario
        })
        db.commit()
        
        logger.info(f"Calificación creada para producto {producto_id}: {request.calificacion} estrellas")
        
        return StandardResponse(
            status="success",
            message="Calificación registrada exitosamente"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Error al crear calificación: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al registrar calificación"
        )


@router.get("/productos/{producto_id}", response_model=CalificacionesListResponse)
async def obtener_calificaciones_producto(
    producto_id: int,
    limit: int = 10,
    skip: int = 0,
    db: Session = Depends(get_db)
):
    """
    Obtener todas las calificaciones de un producto con su promedio
    - Incluye promedio general y distribución de estrellas
    - Paginación de comentarios
    """
    try:
        # Obtener promedio y distribución
        promedio_query = text("""
            SELECT 
                producto_id,
                COUNT(*) as total_calificaciones,
                AVG(CAST(calificacion AS FLOAT)) as promedio_calificacion,
                SUM(CASE WHEN calificacion = 5 THEN 1 ELSE 0 END) as estrellas_5,
                SUM(CASE WHEN calificacion = 4 THEN 1 ELSE 0 END) as estrellas_4,
                SUM(CASE WHEN calificacion = 3 THEN 1 ELSE 0 END) as estrellas_3,
                SUM(CASE WHEN calificacion = 2 THEN 1 ELSE 0 END) as estrellas_2,
                SUM(CASE WHEN calificacion = 1 THEN 1 ELSE 0 END) as estrellas_1
            FROM ProductoCalificaciones
            WHERE producto_id = :producto_id
            GROUP BY producto_id
        """)
        
        promedio_row = db.execute(promedio_query, {"producto_id": producto_id}).fetchone()
        
        promedio = None
        if promedio_row:
            promedio = PromedioCalificacionResponse(
                producto_id=promedio_row.producto_id,
                promedio_calificacion=round(promedio_row.promedio_calificacion, 1),
                total_calificaciones=promedio_row.total_calificaciones,
                estrellas_5=promedio_row.estrellas_5,
                estrellas_4=promedio_row.estrellas_4,
                estrellas_3=promedio_row.estrellas_3,
                estrellas_2=promedio_row.estrellas_2,
                estrellas_1=promedio_row.estrellas_1
            )
        
        # Obtener calificaciones individuales con paginación
        calificaciones_query = text("""
            SELECT id, producto_id, usuario_id, calificacion, comentario, fecha_creacion
            FROM ProductoCalificaciones
            WHERE producto_id = :producto_id
            ORDER BY fecha_creacion DESC
            OFFSET :skip ROWS FETCH NEXT :limit ROWS ONLY
        """)
        
        calificaciones_rows = db.execute(
            calificaciones_query,
            {"producto_id": producto_id, "skip": skip, "limit": limit}
        ).fetchall()
        
        calificaciones = [
            CalificacionResponse(
                id=row.id,
                producto_id=row.producto_id,
                usuario_id=row.usuario_id,
                calificacion=row.calificacion,
                comentario=row.comentario,
                fecha_creacion=row.fecha_creacion
            )
            for row in calificaciones_rows
        ]
        
        return CalificacionesListResponse(
            status="success",
            data=calificaciones,
            promedio=promedio
        )
        
    except Exception as e:
        logger.exception(f"Error al obtener calificaciones: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener calificaciones"
        )


@router.get("/productos/{producto_id}/promedio", response_model=PromedioCalificacionResponse)
async def obtener_promedio_producto(
    producto_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtener solo el promedio de calificaciones de un producto
    - Útil para mostrar rating rápido en listados
    """
    try:
        query = text("""
            SELECT 
                producto_id,
                COUNT(*) as total_calificaciones,
                AVG(CAST(calificacion AS FLOAT)) as promedio_calificacion,
                SUM(CASE WHEN calificacion = 5 THEN 1 ELSE 0 END) as estrellas_5,
                SUM(CASE WHEN calificacion = 4 THEN 1 ELSE 0 END) as estrellas_4,
                SUM(CASE WHEN calificacion = 3 THEN 1 ELSE 0 END) as estrellas_3,
                SUM(CASE WHEN calificacion = 2 THEN 1 ELSE 0 END) as estrellas_2,
                SUM(CASE WHEN calificacion = 1 THEN 1 ELSE 0 END) as estrellas_1
            FROM ProductoCalificaciones
            WHERE producto_id = :producto_id
            GROUP BY producto_id
        """)
        
        row = db.execute(query, {"producto_id": producto_id}).fetchone()
        
        if not row:
            return PromedioCalificacionResponse(
                producto_id=producto_id,
                promedio_calificacion=0.0,
                total_calificaciones=0
            )
        
        return PromedioCalificacionResponse(
            producto_id=row.producto_id,
            promedio_calificacion=round(row.promedio_calificacion, 1),
            total_calificaciones=row.total_calificaciones,
            estrellas_5=row.estrellas_5,
            estrellas_4=row.estrellas_4,
            estrellas_3=row.estrellas_3,
            estrellas_2=row.estrellas_2,
            estrellas_1=row.estrellas_1
        )
        
    except Exception as e:
        logger.exception(f"Error al obtener promedio: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener promedio de calificaciones"
        )


@router.get("/todas", response_model=List[CalificacionResponse])
async def obtener_todas_calificaciones(
    producto_id: Optional[int] = None,
    calificacion: Optional[int] = None,
    limit: int = 100,
    skip: int = 0,
    db: Session = Depends(get_db)
):
    """
    Obtener todas las calificaciones de todos los productos (para admin)
    - Filtros opcionales por producto_id y calificación
    - Paginación
    """
    try:
        # Construir query con filtros dinámicos
        where_clauses = []
        params = {"limit": limit, "skip": skip}
        
        if producto_id:
            where_clauses.append("c.producto_id = :producto_id")
            params["producto_id"] = producto_id
        
        if calificacion:
            where_clauses.append("c.calificacion = :calificacion")
            params["calificacion"] = calificacion
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        query = text(f"""
            SELECT 
                c.id,
                c.producto_id,
                c.usuario_id,
                c.calificacion,
                c.comentario,
                c.fecha_creacion,
                p.nombre as producto_nombre
            FROM ProductoCalificaciones c
            INNER JOIN Productos p ON c.producto_id = p.id
            WHERE {where_sql}
            ORDER BY c.fecha_creacion DESC
            OFFSET :skip ROWS FETCH NEXT :limit ROWS ONLY
        """)
        
        rows = db.execute(query, params).fetchall()
        
        calificaciones = []
        for row in rows:
            calificaciones.append(CalificacionResponse(
                id=row.id,
                producto_id=row.producto_id,
                usuario_id=row.usuario_id,
                calificacion=row.calificacion,
                comentario=row.comentario,
                fecha_creacion=row.fecha_creacion
            ))
        
        return calificaciones
        
    except Exception as e:
        logger.exception(f"Error al obtener todas las calificaciones: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener calificaciones"
        )
