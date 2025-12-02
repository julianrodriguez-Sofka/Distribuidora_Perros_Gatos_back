"""
Security utilities for password hashing, JWT token generation, and validation
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
import logging
import hashlib
import hmac
import random
import os
import base64

from app.config import settings

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class SecurityUtils:
    """Security utilities for authentication and authorization"""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt"""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify plain password against hashed password"""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def create_access_token(data: dict) -> str:
        """
        Create short-lived JWT access token
        """
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "token_type": "access"
        })
        
        try:
            encoded_jwt = jwt.encode(
                to_encode,
                settings.SECRET_KEY,
                algorithm=settings.ALGORITHM
            )
            return encoded_jwt
        except Exception as e:
            logger.error(f"Error creating access token: {str(e)}")
            raise

    @staticmethod
    def create_refresh_token() -> (str, str, datetime):
        """
        Create long-lived opaque refresh token, its hash, and expiry.
        This token is NOT a JWT.
        """
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        # The refresh token is an opaque, URL-safe random string.
        # It doesn't contain data itself but is a key to a DB record.
        random_bytes = os.urandom(32)
        token = base64.urlsafe_b64encode(random_bytes).decode('utf-8')
        
        # We store the hash of the token in the DB
        token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        
        return token, token_hash, expire
        
    @staticmethod
    def verify_jwt_token(token: str) -> dict:
        """Verify JWT token and extract payload"""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            return payload
        except JWTError as e:
            logger.warning(f"Invalid JWT token: {str(e)}")
            # This is a generic error to avoid leaking details
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

    @staticmethod
    def generate_verification_code() -> str:
        """
        Generate a 6-digit verification code
        """
        return f"{random.randint(100000, 999999)}"

    @staticmethod
    def hash_verification_code(code: str) -> str:
        """
        Hash verification code using HMAC-SHA256 with secret key.
        """
        hmac_key = settings.SECRET_KEY.encode('utf-8')
        code_bytes = code.encode('utf-8')
        hash_obj = hmac.new(hmac_key, code_bytes, hashlib.sha256)
        return hash_obj.hexdigest()

    @staticmethod
    def verify_verification_code(code: str, code_hash: str) -> bool:
        """
        Verify verification code against stored hash using constant-time comparison.
        """
        expected_hash = SecurityUtils.hash_verification_code(code)
        return hmac.compare_digest(expected_hash, code_hash)
    
    @staticmethod
    def get_current_user_optional(authorization: Optional[str] = None) -> Optional[dict]:
        """
        Get current user from JWT token if present, return None if not authenticated
        Useful for endpoints that work both authenticated and anonymous
        """
        if not authorization:
            return None
        
        try:
            # Extract token from "Bearer <token>"
            token = authorization.split(" ")[-1] if " " in authorization else authorization
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            return payload
        except Exception:
            # Silently return None if token is invalid
            return None

security_utils = SecurityUtils()
