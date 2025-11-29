"""
Script para crear el usuario administrador directamente en la base de datos
usando SQLAlchemy y el código de la aplicación
"""
import sys
sys.path.append('/app')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Usuario
from app.utils import security_utils
from datetime import datetime, timezone

# Configuración de la base de datos
DB_SERVER = "sqlserver"
DB_PORT = "1433"
DB_NAME = "distribuidora_db"
DB_USER = "SA"
DB_PASSWORD = "yourStrongPassword123#"

# Crear engine de SQLAlchemy
connection_string = (
    f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}@{DB_SERVER}:{DB_PORT}/{DB_NAME}"
    f"?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes"
)

engine = create_engine(connection_string)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Crear sesión
db = SessionLocal()

try:
    # Verificar si el usuario admin ya existe
    existing_admin = db.query(Usuario).filter(Usuario.email == "admin@distribuidora.com").first()
    
    if existing_admin:
        print(f"Usuario admin existe con ID: {existing_admin.id}")
        print("Actualizando contraseña...")
        
        # Actualizar contraseña
        existing_admin.password_hash = security_utils.hash_password("Admin@2024")
        existing_admin.es_admin = True
        existing_admin.is_active = True
        existing_admin.failed_login_attempts = 0
        existing_admin.locked_until = None
        existing_admin.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        print("✅ Usuario admin actualizado exitosamente")
    else:
        print("Creando nuevo usuario admin...")
        
        # Crear nuevo usuario admin
        admin_user = Usuario(
            nombre_completo="Administrador",
            email="admin@distribuidora.com",
            cedula="1234567890",
            password_hash=security_utils.hash_password("Admin@2024"),
            es_admin=True,
            is_active=True,
            failed_login_attempts=0,
            telefono="+593999999999",
            direccion_envio="Oficina Central",
            preferencia_mascotas="Ambos",
            fecha_registro=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        print(f"✅ Usuario admin creado exitosamente con ID: {admin_user.id}")
    
    # Verificar el usuario creado
    admin = db.query(Usuario).filter(Usuario.email == "admin@distribuidora.com").first()
    print("\nDatos del usuario admin:")
    print(f"  ID: {admin.id}")
    print(f"  Nombre: {admin.nombre_completo}")
    print(f"  Email: {admin.email}")
    print(f"  Es Admin: {admin.es_admin}")
    print(f"  Activo: {admin.is_active}")
    print(f"  Hash length: {len(admin.password_hash)}")
    print(f"  Hash preview: {admin.password_hash[:20]}...")
    
    # Verificar que la contraseña es correcta
    is_valid = security_utils.verify_password("Admin@2024", admin.password_hash)
    print(f"\n✅ Verificación de contraseña: {'CORRECTA' if is_valid else 'INCORRECTA'}")
    
    if is_valid:
        print("\n🎉 El usuario administrador está listo para usar!")
        print("\nCredenciales:")
        print("  Email: admin@distribuidora.com")
        print("  Password: Admin@2024")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()
