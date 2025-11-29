"""
Script para generar el hash de contraseña del usuario administrador
"""
import sys
sys.path.append('/app')

from app.utils import security_utils

password = "Admin@2024"
hashed = security_utils.hash_password(password)
print(f"Password: {password}")
print(f"Hash: {hashed}")
