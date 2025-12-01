"""
SQLAlchemy models for database tables
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid


class Usuario(Base):
    """
    Modelo para la tabla Usuarios
    Almacena información de los usuarios/clientes
    """
    __tablename__ = "usuarios"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nombre_completo = Column(String(200), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    cedula = Column(String(50), nullable=False)
    password_hash = Column(String(255), nullable=False)
    fecha_registro = Column(DateTime, server_default=func.getdate(), nullable=True)
    ultimo_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)

    # Additional fields added to match database schema
    telefono = Column(String(20), nullable=True)
    direccion_envio = Column(String(500), nullable=True)
    preferencia_mascotas = Column(String(20), nullable=True)  # Perros, Gatos, Ambos, Ninguno
    
    # Campos para bloqueo de cuenta
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)

    # Relationships (other tables may still reference usuarios.id)
    verification_codes = relationship("VerificationCode", back_populates="usuario", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="usuario", cascade="all, delete-orphan")
    
    # Note: Email uniqueness is enforced at application level with case-insensitive comparison
    # SQL Server collation can be set to case-insensitive, or we use LOWER() in queries
    
    def __repr__(self):
        return f"<Usuario(id={self.id}, email={self.email}, is_active={self.is_active})>"


class VerificationCode(Base):
    """
    Modelo para la tabla VerificationCodes
    Almacena códigos de verificación de email (solo hash, nunca texto plano)
    """
    __tablename__ = "verification_codes"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    code_hash = Column(String(255), nullable=False)  # Hash del código, nunca texto plano
    expires_at = Column(DateTime, nullable=False, index=True)
    attempts = Column(Integer, default=0, nullable=False)  # Intentos de verificación
    sent_count = Column(Integer, default=0, nullable=False)  # Cantidad de reenvíos
    created_at = Column(DateTime, server_default=func.getdate(), nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)  # Si ya fue usado para verificar
    
    # Relationships
    usuario = relationship("Usuario", back_populates="verification_codes")
    
    def __repr__(self):
        return f"<VerificationCode(id={self.id}, usuario_id={self.usuario_id}, expires_at={self.expires_at})>"


class RefreshToken(Base):
    """
    Modelo para la tabla RefreshTokens
    Almacena los refresh tokens de los usuarios para la persistencia de sesión
    """
    __tablename__ = "refresh_tokens"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.getdate(), nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    ip = Column(String(50), nullable=True)
    user_agent = Column(String(255), nullable=True)
    
    # Relationships
    usuario = relationship("Usuario", back_populates="refresh_tokens")
    
    def __repr__(self):
        return f"<RefreshToken(id={self.id}, usuario_id={self.usuario_id}, revoked={self.revoked})>"


class CarruselImagen(Base):
    __tablename__ = 'carrusel_imagenes'

    id = Column(Integer, primary_key=True, index=True)
    imagen_url = Column(String(1024), nullable=False)
    thumbnail_url = Column(String(1024), nullable=True)
    orden = Column(Integer, nullable=False, index=True)
    link_url = Column(String(2048), nullable=True)
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    activo = Column(Boolean, nullable=False, default=True)


# Orders models
class Pedido(Base):
    __tablename__ = 'Pedidos'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    usuario_id = Column(Integer, nullable=False, index=True)
    estado = Column(String(50), nullable=False, default='Pendiente')
    total = Column(Numeric(10, 2), nullable=False, default=0)
    subtotal = Column(Numeric(10, 2), nullable=False, default=0)
    costo_envio = Column(Numeric(10, 2), nullable=False, default=0)
    metodo_pago = Column(String(50), nullable=True)
    direccion_entrega = Column(String(500), nullable=False)
    telefono_contacto = Column(String(20), nullable=False)
    nota_especial = Column(String(500), nullable=True)
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())


class PedidoItem(Base):
    __tablename__ = 'PedidoItems'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    pedido_id = Column(Integer, ForeignKey('Pedidos.id', ondelete='CASCADE'), nullable=False, index=True)
    producto_id = Column(Integer, nullable=False)
    cantidad = Column(Integer, nullable=False)
    precio_unitario = Column(Numeric(10, 2), nullable=False)


class PedidosHistorialEstado(Base):
    __tablename__ = 'PedidosHistorialEstado'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    pedido_id = Column(Integer, ForeignKey('Pedidos.id', ondelete='CASCADE'), nullable=False, index=True)
    estado_anterior = Column(String(50), nullable=True)
    estado_nuevo = Column(String(50), nullable=False)
    usuario_id = Column(Integer, nullable=True)
    nota = Column(String(300), nullable=True)
    fecha = Column(DateTime(timezone=True), server_default=func.now())
