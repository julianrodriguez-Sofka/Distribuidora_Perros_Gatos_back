"""
FastAPI main entry point
Distribuidora Perros y Gatos Backend
"""
import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db, close_db
from app.middleware.error_handler import setup_error_handlers
from app.utils.rabbitmq import rabbitmq_producer

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
from app.routers import (
    auth_router,
    categories_router,
    products_router,
    inventory_router,
    carousel_router,
    orders_router,
    admin_users_router,
    home_products_router
)
from app.routers import public_orders


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager para startup/shutdown events
    Handles database initialization and cleanup
    """
    # Startup
    logger.info("Starting Distribuidora Perros y Gatos Backend API")
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.warning(f"Could not initialize database: {str(e)}")
        logger.warning("Application will continue without database connection")
        # Don't raise - allow app to start for development
    
    yield
    
    # Shutdown
    logger.info("Shutting down API")
    try:
        close_db()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database: {str(e)}")
    
    # Close RabbitMQ connection
    try:
        rabbitmq_producer.close()
        logger.info("RabbitMQ connection closed")
    except Exception as e:
        logger.error(f"Error closing RabbitMQ connection: {str(e)}")


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

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
app.include_router(admin_users_router, tags=["admin-users"])
app.include_router(home_products_router, tags=["home-products"])
# Public orders router for authenticated users
app.include_router(public_orders.router, tags=["public-orders"])

# Public carousel router (frontend)
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
