"""
Script para obtener el código de verificación de un usuario
Solo para desarrollo - hace brute force del código basado en el hash
"""
import sys
import os
import hmac
import hashlib

# Agregar el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import Usuario, VerificationCode
from app.config import settings
from sqlalchemy import func

def get_verification_code_for_email(email: str):
    """Obtiene el código de verificación haciendo brute force del hash"""
    db = SessionLocal()
    try:
        # Buscar usuario
        usuario = db.query(Usuario).filter(func.lower(Usuario.email) == func.lower(email)).first()
        if not usuario:
            print(f"Usuario {email} no encontrado")
            return None
        
        # Buscar el código más reciente
        verification_code_record = db.query(VerificationCode).filter(
            VerificationCode.usuario_id == usuario.id
        ).order_by(VerificationCode.created_at.desc()).first()
        
        if not verification_code_record:
            print(f"No se encontró código de verificación para {email}")
            return None
        
        code_hash = verification_code_record.code_hash
        print(f"Buscando código para hash: {code_hash[:20]}...")
        print(f"Intentos de verificación: {verification_code_record.attempts}")
        print(f"Expira en: {verification_code_record.expires_at}")
        print(f"Ya usado: {verification_code_record.is_used}")
        print("\nProbando códigos...")
        
        # Hacer brute force de todos los códigos posibles (100000-999999)
        hmac_key = settings.SECRET_KEY.encode('utf-8')
        
        for code in range(100000, 1000000):
            code_str = str(code)
            code_bytes = code_str.encode('utf-8')
            hash_obj = hmac.new(hmac_key, code_bytes, hashlib.sha256)
            computed_hash = hash_obj.hexdigest()
            
            if hmac.compare_digest(computed_hash, code_hash):
                print(f"\n{'='*50}")
                print(f"¡CÓDIGO ENCONTRADO!")
                print(f"Código de verificación: {code_str}")
                print(f"Para el usuario: {email}")
                print(f"{'='*50}")
                return code_str
            
            # Mostrar progreso cada 10000 intentos
            if code % 10000 == 0:
                print(f"Probando código {code}...", end='\r')
        
        print("\nNo se encontró el código (puede estar expirado o ser un código diferente)")
        return None
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        db.close()

if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "julian@mail.com"
    print(f"Buscando código de verificación para: {email}\n")
    get_verification_code_for_email(email)

