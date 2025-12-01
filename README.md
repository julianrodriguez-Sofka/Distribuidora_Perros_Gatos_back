# Distribuidora Perros y Gatos - Backend

Backend API for Distribuidora Perros y Gatos e-commerce platform - a multi-vendor platform for pet supplies (dogs and cats).

## Project Structure

```
├── backend/
│   ├── api/                    # FastAPI Backend Service
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── config.py       # Pydantic settings
│   │   │   ├── database.py     # SQLAlchemy setup
│   │   │   ├── schemas.py      # Pydantic models
│   │   │   ├── routers/        # API endpoints
│   │   │   │   ├── auth.py
│   │   │   │   ├── categories.py
│   │   │   │   ├── products.py
│   │   │   │   ├── inventory.py
│   │   │   │   ├── carousel.py
│   │   │   │   ├── orders.py
│   │   │   │   ├── admin_users.py
│   │   │   │   └── home_products.py
│   │   │   ├── services/       # Business logic
│   │   │   ├── middleware/     # Custom middleware
│   │   │   └── utils/          # Utilities
│   │   │       ├── security.py
│   │   │       ├── validators.py
│   │   │       ├── rabbitmq.py
│   │   │       └── logger.py
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── .env.example
│   │
│   └── worker/                 # Node.js Consumer Service
│       ├── src/
│       │   ├── index.ts
│       │   ├── config.ts
│       │   ├── database.ts
│       │   ├── rabbitmq/
│       │   ├── services/
│       │   ├── jobs/
│       │   └── utils/
│       ├── package.json
│       ├── tsconfig.json
│       └── .env.example
│
├── sql/
│   ├── schema.sql              # Main database schema
│   ├── migrations/
│   │   └── 001_add_indexes.sql
│   └── seeders/
│       └── 001_initial_categories.sql
│
├── uploads/
│   ├── productos/
│   ├── carrusel/
│   └── temp/
│
├── Dockerfile.api
├── Dockerfile.worker
├── docker-compose.yml
├── .gitignore
├── .env.example
└── README.md
```

## Technology Stack

### Backend (FastAPI - Python)
- **Framework**: FastAPI with async/await
- **ORM**: SQLAlchemy 2.0
- **Database**: SQL Server
- **Message Queue**: RabbitMQ
- **Authentication**: JWT + Refresh Tokens with HttpOnly cookies
- **Password**: bcrypt hashing
- **File Upload**: Multer-like functionality (max 10MB)
- **Validation**: Pydantic v2

### Worker (Node.js - TypeScript)
- **Runtime**: Node.js 18+
- **Language**: TypeScript
- **Database**: mssql package with Tedious driver
- **Message Queue**: amqplib (RabbitMQ client)
- **Email**: Nodemailer
- **API**: Express.js (health checks only)

 🚀 Funcionalidades Implementadas

## HU_REGISTER_USER ✓
- Registro de usuarios con verificación por correo  
- Código de verificación de 6 dígitos (expira en 10 minutos)  
- Validación de contraseña fuerte (10+ caracteres, mayúscula, dígito, caracter especial)  
- Envío de correo por RabbitMQ  

## HU_LOGIN_USER ✓
- Autenticación email/contraseña con bcrypt  
- JWT (acceso 15 min, refresh 7 días)  
- Unificación del carrito entre dispositivos  
- Limitación de intentos fallidos (5 intentos → bloqueo 15 min)  

## HU_CREATE_PRODUCT ✓
- Creación de productos por administrador  
- Validación completa  
- Subida de imágenes (10MB máx, jpg/png/svg/webp)  
- Categoría / Subcategoría  
- Inventario + SKU  

## HU_MANAGE_CATEGORIES ✓
- CRUD de categorías y subcategorías  
- Unicidad sin distinguir mayúsculas  
- No permite eliminar categorías con productos  
- Procesamiento asíncrono con RabbitMQ  

## HU_MANAGE_INVENTORY ✓
- Reabastecimiento con auditoría  
- Historial de movimientos  
- Rate limiting  
- Tipos: reabastecimiento, venta, ajuste, devolución  

## HU_MANAGE_CAROUSEL ✓
- Gestión de imágenes del carrusel  
- Máx. 5 imágenes  
- Reordenamiento  
- URL opcional  

## HU_MANAGE_ORDERS ✓
- Vista admin de pedidos  
- Flujo de estados: Pendiente → Enviado → Entregado/Cancelado  
- Historial de cambios  
- Búsqueda para clientes  

## HU_MANAGE_USERS ✓
- Visualización de perfil del cliente  
- Búsqueda por nombre/email/cedula  
- Historial de pedidos  
- Estadísticas del usuario  

## HU_HOME_PRODUCTS ✓
- Listado por categoría/subcategoría  
- Carrito anónimo y autenticado  
- Validación de stock  
- Gestión de ítems en el carrito  

---

# 📩 Colas RabbitMQ

14 colas configuradas:

1. `email.verification`  
2. `email.password-reset`  
3. `email.order-confirmation`  
4. `email.order-status-update`  
5. `productos.crear`  
6. `productos.actualizar`  
7. `productos.imagen.crear`  
8. `productos.imagen.eliminar`  
9. `categorias.crear`  
10. `categorias.actualizar`  
11. `carrusel.imagen.crear`  
12. `carrusel.imagen.eliminar`  
13. `carrusel.imagen.reordenar`  
14. `pedido.estado.cambiar`  

---

# 🗄️ Esquema de Base de Datos (14 tablas)

- `Usuarios`  
- `Categorias`  
- `Subcategorias`  
- `Productos`  
- `ProductoImagenes`  
- `CarruselImagenes`  
- `Carts`  
- `CartItems`  
- `Pedidos`  
- `PedidoItems`  
- `PedidosHistorialEstado`  
- `InventarioHistorial`  
- `VerificationCodes`  
- `RefreshTokens`  

---

# 🏁 Getting Started

## Requisitos
- Docker y Docker Compose  
- O: Python 3.11+, Node.js 18+, SQL Server, RabbitMQ  

---

# 🐳 Setup con Docker

```bash
docker-compose up -d

# Database will initialize automatically
# API will be available at http://localhost:8000
# RabbitMQ UI at http://localhost:15672 (guest/guest)
```

### Local Development Setup

#### Backend (FastAPI)
```bash
cd backend/api

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Copy and configure .env
cp .env.example .env
# Edit .env with your settings

# Run migrations
# (Schema will auto-create via SQLAlchemy)

# Start server
uvicorn main:app --reload --port 8000
```

#### Worker (Node.js)
```bash
cd backend/worker

# Install dependencies
npm install

# Copy and configure .env
cp .env.example .env
# Edit .env with your settings

# Development with ts-node
npm run dev

# Production build
npm run build
npm start
```

## API Documentation

### OpenAPI/Swagger
```
http://localhost:8000/docs
```

### Authentication
All protected endpoints require Bearer token in Authorization header:
```
Authorization: Bearer <access_token>
```

Refresh token is sent in HttpOnly cookie for security.

### Error Responses
Standard error format:
```json
{
  "error": "VALIDATION_ERROR",
  "detalle": "Product name must be 3-100 characters",
  "codigo": "ERR_PRODUCT_NAME_INVALID"
}
```

## Security Features

- ✓ Password hashing with bcrypt
- ✓ JWT tokens with expiration
- ✓ HttpOnly cookies for refresh tokens
- ✓ CORS configuration
- ✓ Rate limiting on auth endpoints
- ✓ Input validation with Pydantic
- ✓ SQL injection prevention (SQLAlchemy ORM)
- ✓ Email verification for registration
- ✓ Login attempt lockout (5 attempts/15 min)

## Configuration

See `.env.example` files in `backend/api` and `backend/worker` for all configuration options.

Key variables:
- `DB_SERVER`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` - SQL Server
- `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD` - RabbitMQ
- `SECRET_KEY`, `ALGORITHM` - JWT configuration
- `SMTP_SERVER`, `SMTP_USER`, `SMTP_PASSWORD` - Email configuration
- `CORS_ORIGINS` - Allowed frontend origins

## Development Workflow

1. **Create new route** in `backend/api/app/routers/`
2. **Implement business logic** in `backend/api/app/services/`
3. **Define schemas** in `backend/api/app/schemas.py`
4. **Publish RabbitMQ message** for async processing
5. **Implement consumer** in `backend/worker/src/services/`
6. **Test endpoints** using Swagger at `/docs`

## Testing

```bash
# Backend
cd backend/api
pytest tests/

# Worker
cd backend/worker
npm run test
```

## Deployment

### Docker Compose (Development)
```bash
docker-compose up -d
```

### Production Considerations
1. Set `DEBUG=False` in production
2. Use strong `SECRET_KEY` values
3. Configure SMTP credentials for real email service
4. Use managed database services (Azure SQL, AWS RDS)
5. Use managed message queues (Azure Service Bus, AWS SQS)
6. Enable HTTPS/TLS
7. Set up proper logging and monitoring

## Troubleshooting

### Database Connection Error
- Verify SQL Server is running
- Check connection string in `.env`
- Run migrations: `python scripts/init_db.py`

### RabbitMQ Connection Error
- Verify RabbitMQ service is running
- Check credentials in `.env`
- Default: guest/guest on localhost:5672

### Email Not Sending
- Verify SMTP credentials in `.env`
- Check Gmail: Enable "Less secure apps" or use app password
- Check worker logs for error messages

## License

MIT License

## Support

For issues or questions, please refer to the HU instruction files in `/HU` directory.
