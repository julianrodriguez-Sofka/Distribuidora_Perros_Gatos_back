#!/usr/bin/env python
"""Test script to verify all imports work correctly"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

print("Testing imports...")
print("-" * 50)

try:
    from app.config import settings
    print("[OK] Config loaded")
    print(f"  API Host: {settings.API_HOST}")
    print(f"  API Port: {settings.API_PORT}")
    print(f"  Debug: {settings.DEBUG}")
except Exception as e:
    print(f"[ERROR] Config failed: {e}")
    sys.exit(1)

try:
    from app.utils.constants import MIN_PRODUCT_NAME_LENGTH, MIN_PRODUCT_DESCRIPTION_LENGTH
    print(f"[OK] Constants loaded: MIN_NAME={MIN_PRODUCT_NAME_LENGTH}, MIN_DESC={MIN_PRODUCT_DESCRIPTION_LENGTH}")
except Exception as e:
    print(f"[ERROR] Constants failed: {e}")
    sys.exit(1)

try:
    from app.utils.rabbitmq import publish_message_safe, rabbitmq_producer
    print(f"[OK] RabbitMQ utilities loaded: {type(rabbitmq_producer).__name__}")
except Exception as e:
    print(f"[ERROR] RabbitMQ failed: {e}")
    sys.exit(1)

try:
    from app.models import Usuario
    print(f"[OK] Models loaded: {Usuario.__tablename__}")
except Exception as e:
    print(f"[ERROR] Models failed: {e}")
    sys.exit(1)

try:
    from app.routers import auth_router, products_router
    print("[OK] Routers loaded")
except Exception as e:
    print(f"[ERROR] Routers failed: {e}")
    sys.exit(1)

try:
    from app.database import get_db, init_db
    print("[OK] Database utilities loaded")
except Exception as e:
    print(f"[ERROR] Database failed: {e}")
    sys.exit(1)

print("-" * 50)
print("[OK] All imports successful!")
print("\nReady to start server...")

