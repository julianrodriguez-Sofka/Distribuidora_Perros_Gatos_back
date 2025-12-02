"""
Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import datetime


# Auth Schemas
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    session_id: Optional[str] = None


class CartMergeInfo(BaseModel):
    merged: bool
    items_adjusted: List = []


class LoginSuccessResponse(BaseModel):
    status: str
    message: str
    access_token: str
    cart_merge: Optional[CartMergeInfo] = None



class RegisterRequest(BaseModel):
    """Request schema for user registration - matches HU specifications exactly"""
    email: EmailStr
    password: str = Field(..., min_length=10)
    nombre: str = Field(..., min_length=1, max_length=100)  # Maps to nombre_completo in DB
    cedula: Optional[str] = Field(None, pattern=r"^\d{6,12}$")
    telefono: Optional[str] = Field(None, max_length=20)
    direccion_envio: Optional[str] = Field(None, max_length=500)
    preferencia_mascotas: Optional[str] = Field(None, pattern="^(Perros|Gatos|Ambos|Ninguno)$")
    
    @field_validator('password')
    def password_strength(cls, v):
        """Validate password according to HU specifications - exact error message"""
        if len(v) < 10:
            raise ValueError('La contraseña debe tener al menos 10 caracteres, incluir una mayúscula, un número y un carácter especial.')
        if not any(c.isupper() for c in v):
            raise ValueError('La contraseña debe tener al menos 10 caracteres, incluir una mayúscula, un número y un carácter especial.')
        if not any(c.isdigit() for c in v):
            raise ValueError('La contraseña debe tener al menos 10 caracteres, incluir una mayúscula, un número y un carácter especial.')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            raise ValueError('La contraseña debe tener al menos 10 caracteres, incluir una mayúscula, un número y un carácter especial.')
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class VerificationCodeRequest(BaseModel):
    """Request schema for email verification"""
    email: EmailStr
    code: str = Field(..., pattern=r"^\d{6}$")


class ResendCodeRequest(BaseModel):
    """Request schema for resending verification code"""
    email: EmailStr


class StandardResponse(BaseModel):
    """Standard response schema matching HU specifications exactly"""
    status: str  # "success" or "error"
    message: str


# Category Schemas (HU_MANAGE_CATEGORIES)
class CategoriaCreateRequest(BaseModel):
    """Request schema for creating a category - EXACT as per HU specification"""
    nombre: str = Field(..., min_length=2, max_length=100)


class SubcategoriaCreateRequest(BaseModel):
    """Request schema for creating a subcategory - EXACT as per HU specification"""
    categoriaId: str = Field(..., description="Category ID (can be GUID or bigint as string)")
    nombre: str = Field(..., min_length=2, max_length=100)


class CategoriaUpdateRequest(BaseModel):
    """Request schema for updating a category - EXACT as per HU specification"""
    nombre: str = Field(..., min_length=2, max_length=100)


class SubcategoriaUpdateRequest(BaseModel):
    """Request schema for updating a subcategory - EXACT as per HU specification"""
    nombre: str = Field(..., min_length=2, max_length=100)


# Response schemas
class SubcategoriaResponse(BaseModel):
    id: int
    categoria_id: Optional[int] = None
    nombre: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class CategoriaResponse(BaseModel):
    id: int
    nombre: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    subcategorias: List[SubcategoriaResponse] = []
    
    class Config:
        from_attributes = True


# Standard response schemas (as per HU specification)
class SuccessResponse(BaseModel):
    """Standard success response - EXACT as per HU specification"""
    status: str = "success"
    message: str


class ErrorResponse(BaseModel):
    """Standard error response - EXACT as per HU specification"""
    status: str = "error"
    message: str


# Legacy schemas (keeping for backward compatibility)
class SubcategoriaCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100)


class CategoriaCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100)
    subcategorias: List[SubcategoriaCreate] = []


class CategoriaUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=2, max_length=100)


# Product Schemas
class ProductoCreate(BaseModel):
    nombre: str = Field(..., min_length=3, max_length=100)
    descripcion: Optional[str] = Field(None, max_length=500)
    precio: float = Field(..., gt=0)
    peso_gramos: int = Field(..., gt=0)
    categoria_id: int
    subcategoria_id: int
    cantidad_disponible: int = Field(default=0, ge=0)
    # sku removed from create payload per requirements


class ProductoUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=3, max_length=100)
    descripcion: Optional[str] = Field(None, max_length=500)
    precio: Optional[float] = Field(None, gt=0)
    peso_gramos: Optional[int] = Field(None, gt=0)
    categoria_id: Optional[int] = None
    subcategoria_id: Optional[int] = None
    cantidad_disponible: Optional[int] = Field(None, ge=0)
    activo: Optional[bool] = None
    imagenUrl: Optional[str] = None  # Support external image URL


class ProductoResponse(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str]
    precio: float
    peso_gramos: int
    cantidad_disponible: int
    # sku removed from response
    categoria_id: int
    subcategoria_id: int
    activo: bool
    categoria: Optional[CategoriaResponse] = None
    subcategoria: Optional[SubcategoriaResponse] = None
    imagenes: List[str] = []
    fecha_creacion: datetime
    promedio_calificacion: float = 0.0
    total_calificaciones: int = 0
    
    class Config:
        from_attributes = True


class ProductoImagenResponse(BaseModel):
    id: int
    producto_id: int
    ruta_imagen: str
    es_principal: bool
    orden: int

    class Config:
        from_attributes = True


# Inventory Schemas
class ReabastecimientoRequest(BaseModel):
    cantidad: int = Field(..., gt=0)
    referencia: Optional[str] = Field(None, max_length=200)


class InventarioHistorialResponse(BaseModel):
    id: int
    producto_id: int
    cantidad_anterior: int
    cantidad_nueva: int
    tipo_movimiento: str
    referencia: Optional[str]
    usuario_id: Optional[int]
    fecha: datetime
    
    class Config:
        from_attributes = True


# Stock update via Producer (manual adjustment)
class StockUpdateRequest(BaseModel):
    cantidad: int


# Cart Schemas
class CartItemCreate(BaseModel):
    producto_id: int
    cantidad: int = Field(..., gt=0)


class CartItemResponse(BaseModel):
    id: int
    producto_id: int
    cantidad: int
    precio_unitario: float
    
    class Config:
        from_attributes = True


class CartResponse(BaseModel):
    id: int
    usuario_id: Optional[int]
    session_id: Optional[str]
    items: List[CartItemResponse] = []
    total: float
    
    class Config:
        from_attributes = True


# Order Schemas
class PedidoCreate(BaseModel):
    direccion_entrega: str = Field(..., min_length=10)
    municipio: Optional[str] = Field(None, max_length=100)
    departamento: Optional[str] = Field(None, max_length=100)
    pais: Optional[str] = Field('Colombia', max_length=100)
    telefono_contacto: str = Field(..., pattern=r"^\d{7,15}$")
    metodo_pago: Optional[str] = Field('Efectivo', pattern=r"^(Tarjeta|Efectivo|Daviplata|Nequi|Addi|Sistecredito)$")
    nota_especial: Optional[str] = Field(None, max_length=500)
    usuario_id: int
    items: List[dict] = []


class PedidoEstadoUpdate(BaseModel):
    estado: str = Field(..., pattern="^(Pendiente|Enviado|Entregado|Cancelado)$")
    nota: Optional[str] = Field(None, max_length=300)


class PedidoItemResponse(BaseModel):
    id: int
    producto_id: int
    cantidad: int
    precio_unitario: float
    
    class Config:
        from_attributes = True


class PedidoResponse(BaseModel):
    id: int
    usuario_id: int
    clienteNombre: Optional[str] = None
    estado: str
    total: float
    metodo_pago: Optional[str] = 'Efectivo'
    direccion_entrega: str
    municipio: Optional[str] = None
    departamento: Optional[str] = None
    pais: Optional[str] = 'Colombia'
    telefono_contacto: str
    fecha_creacion: datetime
    items: List[PedidoItemResponse] = []
    
    class Config:
        from_attributes = True


# Carousel Schemas
class CarruselImagenCreate(BaseModel):
    orden: int = Field(..., ge=1, le=5)
    link_url: Optional[str] = Field(None, max_length=500)


class CarruselImagenUpdate(BaseModel):
    orden: Optional[int] = Field(None, ge=1, le=5)
    link_url: Optional[str] = Field(None, max_length=500)


class CarruselImagenResponse(BaseModel):
    id: int
    orden: int
    ruta_imagen: str = Field(..., alias="imagen_url")
    link_url: Optional[str]
    activo: bool
    fecha_creacion: datetime = Field(..., alias="created_at")

    class Config:
        # Allow reading from ORM attributes and populate by field name when needed
        from_attributes = True
        allow_population_by_field_name = True


# User Schemas
class UsuarioPublicResponse(BaseModel):
    id: int
    nombre_completo: str
    email: str
    rol: str
    class Config:
        from_attributes = True


class UsuarioDetailResponse(BaseModel):
    id: int
    nombreCompleto: str
    email: str
    cedula: str
    telefono: Optional[str] = None
    direccionEnvio: Optional[str] = None
    preferenciaMascotas: Optional[str] = None
    fechaRegistro: datetime
    ultimoLogin: Optional[datetime] = None
    rol: str
    pedidosResumen: Optional[dict] = None
    
    class Config:
        from_attributes = True


# Detailed error response (internal/legacy)
class ErrorDetailResponse(BaseModel):
    error: str
    detalle: Optional[str] = None
    codigo: str


# --- Responses for HU_MANAGE_USERS ---
class UsuarioListItem(BaseModel):
    id: int
    nombreCompleto: str
    cedula: Optional[str]
    email: str
    direccionEnvio: Optional[str]
    fechaRegistro: datetime

    class Config:
        from_attributes = True


class MetaPage(BaseModel):
    page: int
    pageSize: int
    total: int


class UsuariosListResponse(BaseModel):
    status: str = "success"
    data: List[UsuarioListItem] = []
    meta: MetaPage


class UsuarioDetailWrapper(BaseModel):
    status: str = "success"
    data: UsuarioDetailResponse


class PedidoSummaryItem(BaseModel):
    id: int
    fecha: datetime
    total: float
    estado: str


class PedidosListResponse(BaseModel):
    status: str = "success"
    data: List[PedidoResponse] = []
    meta: MetaPage


# --- Rating/Calificaciones Schemas ---
class CalificacionCreateRequest(BaseModel):
    """Request para crear una calificación de producto"""
    calificacion: int = Field(..., ge=1, le=5, description="Calificación de 1 a 5 estrellas")
    comentario: Optional[str] = Field(None, max_length=500, description="Comentario opcional")


class CalificacionResponse(BaseModel):
    """Response de una calificación individual"""
    id: int
    producto_id: int
    usuario_id: Optional[int]
    calificacion: int
    comentario: Optional[str]
    fecha_creacion: datetime
    
    class Config:
        from_attributes = True


class PromedioCalificacionResponse(BaseModel):
    """Response con el promedio de calificaciones de un producto"""
    producto_id: int
    promedio_calificacion: float
    total_calificaciones: int
    estrellas_5: int = 0
    estrellas_4: int = 0
    estrellas_3: int = 0
    estrellas_2: int = 0
    estrellas_1: int = 0


class CalificacionesListResponse(BaseModel):
    """Response con lista de calificaciones de un producto"""
    status: str = "success"
    data: List[CalificacionResponse] = []
    promedio: Optional[PromedioCalificacionResponse] = None

