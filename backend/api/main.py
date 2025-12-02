"""
FastAPI main entry point
Distribuidora Perros y Gatos Backend
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db, close_db
from app.middleware.error_handler import setup_error_handlers
from app.routers import (
    auth_router,
    categories_router,
    products_router,
    inventory_router,
    carousel_router,
    orders_router,
    orders_public_router,
    admin_users_router,
    home_products_router
)
from app.routers.calificaciones import router as calificaciones_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager para startup/shutdown events
    Handles database initialization and cleanup
    """
    # Startup
    print("Starting Distribuidora Perros y Gatos Backend API")
    
    # Inicializar schema de base de datos si es necesario
    try:
        from app.utils.db_init import initialize_database
        print("Inicializando base de datos...")
        initialize_database()
    except Exception as e:
        print(f"Warning: Could not initialize database schema: {str(e)}")
        print("The database may need manual initialization")
    
    # Inicializar conexión de SQLAlchemy
    try:
        init_db()
        print("Database connection pool initialized successfully")
    except Exception as e:
        print(f"Warning: Could not initialize database connection: {str(e)}")
        print("Application will continue without database connection")
        # Don't raise - allow app to start for development
    
    yield
    
    # Shutdown
    print("Shutting down API")
    try:
        close_db()
        print("Database connections closed")
    except Exception as e:
        print(f"Error closing database: {str(e)}")


# Crear aplicación FastAPI
app = FastAPI(
    title="Distribuidora Perros y Gatos API",
    description="Backend API para tienda de productos para mascotas",
    version="1.0.0",
    lifespan=lifespan
)

# Determine absolute uploads directory inside the running container or local environment
# Prefer '<base>/uploads' (e.g. '/app/uploads' when WORKDIR=/app), but fall back to '<base>/app/uploads'
BASE_DIR = Path(__file__).resolve().parent  # directory containing main.py (usually '/app')
candidate_a = BASE_DIR / "uploads"
candidate_b = BASE_DIR / "app" / "uploads"

if candidate_a.exists():
    UPLOADS_DIR = candidate_a
elif candidate_b.exists():
    UPLOADS_DIR = candidate_b
else:
    # Create the preferred location (candidate_a)
    UPLOADS_DIR = candidate_a
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Ensure carrusel subfolder exists
(UPLOADS_DIR / "carrusel").mkdir(parents=True, exist_ok=True)

# Synchronize settings.UPLOAD_DIR so other modules use the same absolute path
try:
    settings.UPLOAD_DIR = str(UPLOADS_DIR)
except Exception:
    pass

# Mount static files so requests to /app/uploads/... are served from the uploads folder
app.mount("/app/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

# Middleware CORS - Debe ir ANTES de los routers
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

# Middleware para hosts de confianza
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS
)

# Setup error handlers
setup_error_handlers(app)


# Health check endpoint





# Importar y incluir routers
app.include_router(auth_router, prefix="/api/auth", tags=["authentication"])
app.include_router(categories_router, tags=["categories"])
app.include_router(products_router, tags=["products"])
app.include_router(inventory_router, tags=["inventory"])
app.include_router(carousel_router, tags=["carousel"])
app.include_router(orders_router, tags=["orders"])
app.include_router(orders_public_router, tags=["pedidos-public"])
app.include_router(admin_users_router, tags=["admin-users"])
app.include_router(home_products_router, tags=["home-products"])
app.include_router(calificaciones_router, tags=["calificaciones"])

# Public routers (frontend)
from app.routers.carousel import public_router as carousel_public_router
app.include_router(carousel_public_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
