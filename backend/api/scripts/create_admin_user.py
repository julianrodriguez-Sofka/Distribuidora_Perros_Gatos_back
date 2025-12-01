"""
Script para crear un usuario administrador
Ejecutar: python -m app.scripts.create_admin_user
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.database import SessionLocal
from app.models import Usuario
from app.utils.security import SecurityUtils

def create_admin_user():
    db = SessionLocal()
    try:
        # Credenciales del administrador
        admin_email = "admin@distribuidora.com"
        admin_password = "Admin123!@#"
        admin_name = "Administrador Principal"
        admin_cedula = "1234567890"
        
        # Verificar si ya existe
        existing = db.query(Usuario).filter(Usuario.email == admin_email).first()
        if existing:
            if existing.es_admin:
                print(f"✅ Usuario administrador ya existe:")
                print(f"   Email: {admin_email}")
                print(f"   ID: {existing.id}")
                print(f"   Activo: {existing.is_active}")
                return
            else:
                # Actualizar usuario existente a admin
                existing.es_admin = True
                existing.is_active = True
                existing.password_hash = SecurityUtils.hash_password(admin_password)
                db.commit()
                print(f"✅ Usuario actualizado a administrador:")
                print(f"   Email: {admin_email}")
                print(f"   Contraseña: {admin_password}")
                return
        
        # Crear nuevo usuario administrador
        password_hash = SecurityUtils.hash_password(admin_password)
        
        admin_user = Usuario(
            email=admin_email,
            password_hash=password_hash,
            nombre_completo=admin_name,
            cedula=admin_cedula,
            es_admin=True,
            is_active=True,
            telefono="3001234567",
            direccion_envio="Oficina Principal - Distribuidora Perros y Gatos"
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        print("=" * 60)
        print("✅ USUARIO ADMINISTRADOR CREADO EXITOSAMENTE")
        print("=" * 60)
        print(f"Email: {admin_email}")
        print(f"Contraseña: {admin_password}")
        print(f"ID: {admin_user.id}")
        print(f"Nombre: {admin_name}")
        print("=" * 60)
        print("\n⚠️  IMPORTANTE: Cambia la contraseña después del primer inicio de sesión")
        print("=" * 60)
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error al crear usuario administrador: {str(e)}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    create_admin_user()

