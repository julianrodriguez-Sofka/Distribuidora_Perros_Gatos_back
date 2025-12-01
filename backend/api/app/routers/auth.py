"""
Authentication router: Register, Login, Logout, Token refresh
Handles HU_REGISTER_USER and HU_LOGIN_USER
"""
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid
import logging

import hashlib
from app.schemas import (
    RegisterRequest, 
    LoginRequest, 
    TokenResponse, 
    VerificationCodeRequest,
    ResendCodeRequest,
    StandardResponse,
    LoginSuccessResponse,
    CartMergeInfo,
    UsuarioPublicResponse
)
from app.database import get_db
from app.models import Usuario, VerificationCode, RefreshToken
from app.utils import security_utils
from app.utils.rabbitmq import publish_message_safe
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["auth"]
)


def _check_email_exists(db: Session, email: str, exclude_user_id: Optional[int] = None) -> bool:
    """Check if email exists (case-insensitive)"""
    query = db.query(Usuario).filter(func.lower(Usuario.email) == func.lower(email))
    if exclude_user_id:
        query = query.filter(Usuario.id != exclude_user_id)
    return query.first() is not None


def _check_cedula_exists(db: Session, cedula: str, exclude_user_id: Optional[int] = None) -> bool:
    """Check if cedula exists in usuarios table"""
    if not cedula:
        return False
    query = db.query(Usuario).filter(Usuario.cedula == cedula)
    if exclude_user_id:
        query = query.filter(Usuario.id != exclude_user_id)
    return query.first() is not None


@router.post("/register", response_model=StandardResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register new user with email verification
    
    Requirements (HU_REGISTER_USER):
    - Email must be unique and verified via 6-digit code
    - Password: 10+ chars, uppercase, digit, special char
    - Sends verification email with 6-digit code (10 min expiry)
    - Publishes to email.verification queue
    """
    try:
        # 1. Validate required fields - Pydantic handles validation, but check for empty
        if not request.email or not request.password or not request.nombre:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Por favor, completa todos los campos obligatorios."}
            )
        
        # 2. Check email uniqueness (case-insensitive)
        if _check_email_exists(db, request.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"status": "error", "message": "El correo ya está registrado. ¿Deseas iniciar sesión o recuperar tu contraseña?"}
            )

        # 2b. Check cedula uniqueness (if provided)
        if request.cedula and _check_cedula_exists(db, request.cedula):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"status": "error", "message": "La cédula ya está registrada."}
            )
        
        # 3. Password validation is handled by Pydantic field_validator
        # It will raise ValueError with the exact message if invalid
        
        # 4. Hash password using bcrypt
        password_hash = security_utils.hash_password(request.password)
        
        # 5. Create usuario entry (is_active=False)
        nuevo_usuario = Usuario(
            email=request.email,
            password_hash=password_hash,
            nombre_completo=request.nombre,  # Map 'nombre' from request to 'nombre_completo' in DB
            cedula=request.cedula,
            telefono=request.telefono,
            direccion_envio=request.direccion_envio,
            preferencia_mascotas=request.preferencia_mascotas,
            is_active=False
        )
        db.add(nuevo_usuario)
        try:
            db.flush()  # Get the ID without committing
        except IntegrityError as ie:
            db.rollback()
            # Handle unique constraint violations that slipped past pre-checks
            msg = str(ie.orig) if hasattr(ie, 'orig') else str(ie)
            # If cedula duplicate key reported, return cedula message
            if 'duplicate' in msg.lower() or 'violation' in msg.lower() or 'unique' in msg.lower():
                # Generic message to avoid leaking DB constraint names
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"status": "error", "message": "El correo o la cédula ya están registrados."}
                )
            raise
        
        # 6. Generate verification code (6 digits)
        verification_code = security_utils.generate_verification_code()
        code_hash = security_utils.hash_verification_code(verification_code)
        
        # Log verification code in development mode for testing
        # Always log for now to help with debugging
        logger.info(f"[DEV MODE] Verification code for {request.email}: {verification_code}")
        logger.info(f"[DEV MODE] User can verify email at: POST /api/auth/verify-email with code: {verification_code}")
        if settings.DEBUG:
            logger.info(f"🔐 [DEV MODE] Verification code for {request.email}: {verification_code}")
            logger.info(f"📧 [DEV MODE] User can verify email at: POST /api/auth/verify-email with code: {verification_code}")
        
        # 7. Create/update VerificationCodes with expires_at = now + 10 minutes
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.VERIFICATION_CODE_EXPIRE_MINUTES)
        
        # Check if there's an existing verification code for this user
        existing_code = db.query(VerificationCode).filter(
            and_(
                VerificationCode.usuario_id == nuevo_usuario.id,
                VerificationCode.is_used == False,
                VerificationCode.expires_at > datetime.now(timezone.utc)
            )
        ).first()
        
        if existing_code:
            # Update existing code
            existing_code.code_hash = code_hash
            existing_code.expires_at = expires_at
            existing_code.sent_count += 1
            existing_code.attempts = 0
            verification_record = existing_code
        else:
            # Create new verification code
            verification_record = VerificationCode(
                usuario_id=nuevo_usuario.id,
                code_hash=code_hash,
                expires_at=expires_at,
                sent_count=1,
                attempts=0,
                is_used=False
            )
            db.add(verification_record)
        
        db.flush()
        
        # 8. Publish message to RabbitMQ queue expected by the worker: email.notifications
        request_id = str(uuid.uuid4())
        subject = "Verifica tu correo electrónico - Distribuidora Perros y Gatos"
        message = {
            "requestId": request_id,
            "to": request.email,
            "subject": subject,
            "template": "verification",
            "context": {
                "name": request.nombre,
                "code": verification_code,
                "year": datetime.now().year,
                "subject": subject
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Publish email notification (non-blocking, won't fail registration)
        published = publish_message_safe("email.notifications", message, retry=True)
        if published:
            logger.info(f"Published verification email message for user {nuevo_usuario.id}, requestId: {request_id}")
        else:
            logger.warning(f"Failed to publish verification email for user {nuevo_usuario.id}, requestId: {request_id}")
            # Don't fail the registration if RabbitMQ is down; registration still succeeds
        
        # 9. Commit transaction
        db.commit()
        
        # 10. Return success response with exact message from HU
        return {
            "status": "success",
            "message": "Por favor, Revisa tu bandeja de entrada para verificar tu cuenta e ingresa el código enviado"
        }
        
    except HTTPException:
        db.rollback()
        raise
    except ValueError as e:
        db.rollback()
        # Handle password validation errors from Pydantic
        error_msg = str(e)
        # Ensure we return the exact message from HU specifications
        if "contraseña" in error_msg.lower() or "password" in error_msg.lower():
            error_msg = "La contraseña debe tener al menos 10 caracteres, incluir una mayúscula, un número y un carácter especial."
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": error_msg}
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error during registration: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Error interno del servidor. Por favor, intenta más tarde."}
        )


@router.post("/verify-email", response_model=StandardResponse, status_code=status.HTTP_200_OK)
async def verify_email(request: VerificationCodeRequest, db: Session = Depends(get_db)):
    """
    Verify user email with 6-digit code
    
    Requirements:
    - Code must match stored verification code
    - Code expires after 10 minutes
    - Mark usuario as is_active=True after verification
    """
    try:
        # 1. Validate required fields
        if not request.email or not request.code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Por favor, completa todos los campos obligatorios."}
            )
        
        # 2. Find usuario by email (case-insensitive)
        usuario = db.query(Usuario).filter(func.lower(Usuario.email) == func.lower(request.email)).first()
        if not usuario:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Código inválido."}
            )
        
        # 3. Check if user is already active
        if usuario.is_active:
            return {
                "status": "success",
                "message": "Cuenta verificada exitosamente. Ya puedes iniciar sesión."
            }
        
        # 4. Find active verification code
        verification_code = db.query(VerificationCode).filter(
            and_(
                VerificationCode.usuario_id == usuario.id,
                VerificationCode.is_used == False,
                VerificationCode.expires_at > datetime.now(timezone.utc)
            )
        ).order_by(VerificationCode.created_at.desc()).first()
        
        if not verification_code:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail={"status": "error", "message": "El código ha expirado. Solicita un reenvío."}
            )
        
        # 5. Check verification attempts
        if verification_code.attempts >= settings.MAX_VERIFICATION_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"status": "error", "message": "Has excedido el número máximo de intentos. Solicita un nuevo código."}
            )
        
        # 6. Verify code hash (constant-time comparison)
        is_valid = security_utils.verify_verification_code(request.code, verification_code.code_hash)
        
        if not is_valid:
            # Increment attempts
            verification_code.attempts += 1
            db.commit()
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Código inválido."}
            )
        
        # 7. Code is valid - activate user
        usuario.is_active = True
        usuario.updated_at = datetime.now(timezone.utc)
        
        # Mark verification code as used
        verification_code.is_used = True
        
        db.commit()
        
        logger.info(f"User {usuario.id} ({usuario.email}) verified successfully")
        
        return {
            "status": "success",
            "message": "Cuenta verificada exitosamente. Ya puedes iniciar sesión."
        }
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error during email verification: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Error interno del servidor. Por favor, intenta más tarde."}
        )


@router.post("/resend-code", response_model=StandardResponse, status_code=status.HTTP_200_OK)
async def resend_code(request: ResendCodeRequest, db: Session = Depends(get_db)):
    """
    Resend verification code
    
    Requirements:
    - Email exists and user is not already active
    - Respect rate-limit: max 3 reenvíos in 60 minutes
    """
    try:
        # 1. Validate required fields
        if not request.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Por favor, completa todos los campos obligatorios."}
            )
        
        # 2. Find usuario by email (case-insensitive)
        usuario = db.query(Usuario).filter(func.lower(Usuario.email) == func.lower(request.email)).first()
        if not usuario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Usuario no encontrado."}
            )
        
        # 3. Check if user is already active
        if usuario.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "El usuario ya está verificado."}
            )
        
        # 4. Check rate limiting - max 3 reenvíos in RESEND_CODE_WINDOW_MINUTES
        window_start = datetime.now(timezone.utc) - timedelta(minutes=settings.RESEND_CODE_WINDOW_MINUTES)
        
        recent_codes = db.query(VerificationCode).filter(
            and_(
                VerificationCode.usuario_id == usuario.id,
                VerificationCode.created_at >= window_start
            )
        ).all()
        
        total_sent = sum(code.sent_count for code in recent_codes)
        
        if total_sent >= settings.MAX_RESEND_CODE_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"status": "error", "message": "Has alcanzado el número máximo de reenvíos. Intenta más tarde."}
            )
        
        # 5. Generate new verification code
        verification_code = security_utils.generate_verification_code()
        code_hash = security_utils.hash_verification_code(verification_code)
        
        # Log verification code in development mode for testing
        # Always log for now to help with debugging - use ERROR level to ensure it shows
        import sys
        msg = f"========================================\n[DEV MODE] Resent verification code for {request.email}: {verification_code}\n[DEV MODE] User can verify email at: POST /api/auth/verify-email with code: {verification_code}\n========================================"
        print(msg, flush=True)
        sys.stdout.flush()
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()
        logger.error(f"[DEV MODE] Resent verification code for {request.email}: {verification_code}")
        logger.error(f"[DEV MODE] User can verify email at: POST /api/auth/verify-email with code: {verification_code}")
        logger.info(f"[DEV MODE] Resent verification code for {request.email}: {verification_code}")
        logger.info(f"[DEV MODE] User can verify email at: POST /api/auth/verify-email with code: {verification_code}")
        
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.VERIFICATION_CODE_EXPIRE_MINUTES)
        
        # 6. Find existing unused code or create new one
        existing_code = db.query(VerificationCode).filter(
            and_(
                VerificationCode.usuario_id == usuario.id,
                VerificationCode.is_used == False,
                VerificationCode.expires_at > datetime.now(timezone.utc)
            )
        ).first()
        
        if existing_code:
            # Update existing code
            existing_code.code_hash = code_hash
            existing_code.expires_at = expires_at
            existing_code.sent_count += 1
            existing_code.attempts = 0
            verification_record = existing_code
        else:
            # Create new verification code
            verification_record = VerificationCode(
                usuario_id=usuario.id,
                code_hash=code_hash,
                expires_at=expires_at,
                sent_count=1,
                attempts=0,
                is_used=False
            )
            db.add(verification_record)
        
        db.flush()
        
        # 7. Publish message to RabbitMQ queue expected by the worker: email.notifications
        request_id = str(uuid.uuid4())
        subject = "Verifica tu correo electrónico - Distribuidora Perros y Gatos"
        message = {
            "requestId": request_id,
            "to": usuario.email,
            "subject": subject,
            "template": "verification",
            "context": {
                "name": usuario.nombre_completo,
                "code": verification_code,
                "year": datetime.now().year,
                "subject": subject
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Publish email notification (non-blocking)
        published = publish_message_safe("email.notifications", message, retry=True)
        if published:
            logger.info(f"Published resend verification email for user {usuario.id}, requestId: {request_id}")
        else:
            logger.warning(f"Failed to publish resend verification email for user {usuario.id}, requestId: {request_id}")
            # Don't fail the resend if RabbitMQ is down
        
        db.commit()
        
        return {
            "status": "success",
            "message": "Código reenviado. Revisa tu correo."
        }
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error during resend code: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Error interno del servidor. Por favor, intenta más tarde."}
        )


@router.post("/login", response_model=LoginSuccessResponse, status_code=status.HTTP_200_OK)
async def login(request: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """
    User login with credentials, handling account lockout and token generation.
    """
    try:
        # 1. Validate required fields
        if not request.email or not request.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Por favor, completa todos los campos obligatorios."}
            )

        # 2. Find user by email (case-insensitive)
        usuario = db.query(Usuario).filter(func.lower(Usuario.email) == func.lower(request.email)).first()

        # Generic error for user not found or password incorrect to prevent user enumeration
        generic_error = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "message": "Correo o contraseña incorrectos"}
        )

        if not usuario:
            raise generic_error

        # 3. Check if account is locked
        if usuario.locked_until and usuario.locked_until > datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail={"status": "error", "message": "Cuenta bloqueada temporalmente por múltiples intentos fallidos. Intenta más tarde."}
            )

        # 4. Verify password
        if not security_utils.verify_password(request.password, usuario.password_hash):
            # Increment failed attempts and potentially lock account
            usuario.failed_login_attempts = (usuario.failed_login_attempts or 0) + 1
            if usuario.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
                usuario.locked_until = datetime.now(timezone.utc) + timedelta(minutes=settings.LOGIN_LOCKOUT_DURATION_MINUTES)
            db.commit()
            raise generic_error

        # 5. Check if account is active
        if not usuario.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"status": "error", "message": "Cuenta no verificada. Revisa tu correo."}
            )

        # 6. On successful login, reset failed attempts and update last login time
        usuario.failed_login_attempts = 0
        usuario.locked_until = None
        usuario.ultimo_login = datetime.now(timezone.utc)
        
        # 7. Create tokens
        rol = "admin" if usuario.es_admin else "cliente"
        access_token = security_utils.create_access_token(data={"sub": str(usuario.id), "rol": rol})
        refresh_token, refresh_token_hash, refresh_token_expires = security_utils.create_refresh_token()
        
        # 8. Store refresh token in DB
        new_refresh_token = RefreshToken(
            usuario_id=usuario.id,
            token_hash=refresh_token_hash,
            expires_at=refresh_token_expires,
            # ip=request.client.host, # This needs ForwardedHeaderMiddleware
            # user_agent=request.headers.get("user-agent")
        )
        db.add(new_refresh_token)
        db.commit()
        
        # 9. Set refresh token in secure HttpOnly cookie
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=not settings.DEBUG,  # True in production
            samesite="lax", # or "strict"
            expires=refresh_token_expires,
            path="/api/auth" # Path where refresh endpoint lives
        )
        
        # 10. Handle cart merging (placeholder)
        cart_merge_info = CartMergeInfo(merged=False, items_adjusted=[])
        if request.session_id:
            # TODO: Implement cart merging logic here
            logger.info(f"Cart merge requested for session_id: {request.session_id}")
            # For now, we just acknowledge it
            cart_merge_info.merged = True # Simulate merge
            
        return LoginSuccessResponse(
            status="success",
            message="Inicio de sesión exitoso",
            access_token=access_token,
            cart_merge=cart_merge_info
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error during login: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Error interno del servidor."}
        )

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: Request, db: Session = Depends(get_db)):
    """
    Refresh access token using refresh token from HttpOnly cookie.
    """
    refresh_token_value = request.cookies.get("refresh_token")
    if not refresh_token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found"
        )

    try:
        token_hash = hashlib.sha256(refresh_token_value.encode('utf-8')).hexdigest()
        
        # Find the refresh token in the database
        db_token = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

        if not db_token:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        if db_token.revoked:
            raise HTTPException(status_code=401, detail="Refresh token has been revoked")

        if db_token.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Refresh token has expired")

        # Create a new access token
        access_token = security_utils.create_access_token(data={"sub": str(db_token.usuario_id)})
        
        return TokenResponse(
            access_token=access_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error refreshing token: {e}")
        raise HTTPException(status_code=500, detail="Could not refresh token")


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(response: Response, request: Request, db: Session = Depends(get_db)):
    """
    User logout by revoking the refresh token.
    """
    refresh_token_value = request.cookies.get("refresh_token")
    if refresh_token_value:
        try:
            token_hash = hashlib.sha256(refresh_token_value.encode('utf-8')).hexdigest()
            db_token = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
            if db_token:
                db_token.revoked = True
                db.commit()
        except Exception as e:
            logger.error(f"Error revoking token during logout: {e}")
            # Do not prevent logout if DB operation fails
    
    # Clear the cookie on the client side
    response.delete_cookie(key="refresh_token", path="/api/auth")
    
    return {"status": "success", "message": "Cierre de sesión exitoso"}

def get_current_user(request: Request, db: Session = Depends(get_db)) -> UsuarioPublicResponse:
    """Extrae el usuario autenticado del JWT Bearer token"""
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="No autenticado")
    token = auth_header.split(" ", 1)[1]
    payload = security_utils.verify_jwt_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token inválido")
    usuario = db.query(Usuario).filter(Usuario.id == int(user_id)).first()
    if not usuario or not usuario.is_active:
        raise HTTPException(status_code=403, detail="Cuenta no activa")
    rol = "admin" if usuario.es_admin else "cliente"
    return UsuarioPublicResponse(
        id=usuario.id,
        nombre_completo=usuario.nombre_completo,
        email=usuario.email,
        rol=rol
    )


def require_admin(current_user: UsuarioPublicResponse = Depends(get_current_user)) -> UsuarioPublicResponse:
    """Dependency to require that the current user is an admin.

    Use in endpoints as:
        @router.get(...)
        def admin_only_endpoint(current_user: UsuarioPublicResponse = Depends(require_admin)):
            # current_user is guaranteed to be admin
            ...
    Or as a dependency in the router declaration: `dependencies=[Depends(require_admin)]`.
    """
    if current_user.rol != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"status": "error", "message": "Privilegios insuficientes."})
    return current_user

@router.get("/me", response_model=UsuarioPublicResponse)
async def get_me(current_user: UsuarioPublicResponse = Depends(get_current_user)):
    return current_user


@router.get("/dev/verification-code/{email}", status_code=status.HTTP_200_OK)
async def get_verification_code_dev(email: str, db: Session = Depends(get_db)):
    """
    DEVELOPMENT ONLY: Get the latest verification code for an email
    This endpoint is only available when DEBUG=True
    WARNING: This should NEVER be enabled in production!
    """
    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"status": "error", "message": "This endpoint is only available in development mode."}
        )
    
    try:
        # Find usuario by email (case-insensitive)
        usuario = db.query(Usuario).filter(func.lower(Usuario.email) == func.lower(email)).first()
        if not usuario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Usuario no encontrado."}
            )
        
        # Find the most recent verification code (even if expired, for dev purposes)
        verification_code_record = db.query(VerificationCode).filter(
            VerificationCode.usuario_id == usuario.id
        ).order_by(VerificationCode.created_at.desc()).first()
        
        if not verification_code_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "No se encontró código de verificación para este usuario."}
            )
        
        # Check if code is still valid
        is_expired = verification_code_record.expires_at < datetime.now(timezone.utc)
        is_used = verification_code_record.is_used
        
        # Note: We cannot retrieve the actual code from the hash (it's one-way)
        # But we can provide information about the code status
        return {
            "status": "success",
            "message": "⚠️ IMPORTANTE: El código está hasheado en la BD y no se puede recuperar.",
            "info": {
                "email": email,
                "usuario_id": usuario.id,
                "code_id": verification_code_record.id,
                "expires_at": verification_code_record.expires_at.isoformat(),
                "is_expired": is_expired,
                "is_used": is_used,
                "attempts": verification_code_record.attempts,
                "sent_count": verification_code_record.sent_count,
                "created_at": verification_code_record.created_at.isoformat() if verification_code_record.created_at else None
            },
            "note": "Revisa los logs del servidor cuando se generó el código. En modo DEBUG, el código se imprime en los logs."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting verification code for dev: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Error interno del servidor."}
        )
