"""
Configuration settings for FastAPI application
Using Pydantic Settings for environment variable management
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Server
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = False
    API_VERSION: str = "1.0.0"
    
    # Database (SQL Server)
    DB_SERVER: str = "localhost"
    DB_PORT: int = 1433
    DB_NAME: str = "distribuidora_db"
    DB_USER: str = "sa"
    DB_PASSWORD: str = "YourPassword123!"
    
    @property
    def DATABASE_URL(self) -> str:
        """Construct SQL Server connection string"""
        return f"mssql+pyodbc://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_SERVER}:{self.DB_PORT}/{self.DB_NAME}?driver=ODBC+Driver+17+for+SQL+Server"
    
    # RabbitMQ
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"
    RABBITMQ_VHOST: str = "/"
    
    @property
    def RABBITMQ_URL(self) -> str:
        """Construct RabbitMQ connection URL"""
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/{self.RABBITMQ_VHOST}"
    
    # Security & JWT
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001", 
        "http://localhost:3002",
        "http://localhost:8080",
        "http://localhost:5173"
    ]
    ALLOWED_HOSTS: List[str] = ["*"]  # Allow all hosts in development
    
    # Email Configuration
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = "your-email@gmail.com"
    SMTP_PASSWORD: str = "your-app-password"
    
    # File Upload
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 10485760  # 10 MB
    ALLOWED_IMAGE_EXTENSIONS: List[str] = [".jpg", ".jpeg", ".png", ".svg", ".webp"]
    
    # Rate Limiting
    MAX_LOGIN_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_DURATION_MINUTES: int = 15
    
    # Email Verification
    VERIFICATION_CODE_EXPIRE_MINUTES: int = 10
    MAX_VERIFICATION_ATTEMPTS: int = 5
    MAX_RESEND_CODE_ATTEMPTS: int = 3
    RESEND_CODE_WINDOW_MINUTES: int = 60
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Instancia global de settings
settings = Settings()
