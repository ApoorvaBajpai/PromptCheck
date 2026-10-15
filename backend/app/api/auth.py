import time
from collections import defaultdict
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.database import get_db
from app.models.user import User
from app.schemas.user import TokenResponse, UserCreate, UserOut

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class AuthRateLimiter:
    """
    In-process sliding window rate limiter for authentication endpoints.
    Protects login and registration against brute-force attacks and credential stuffing.
    Note: In a multi-worker production cluster with load balancing across hosts,
    this rate limiter operates per-worker; a distributed store (e.g. Redis)
    can be plugged in if horizontal cluster scaling is required.
    """

    def __init__(self, max_requests: int = 10, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.attempts: dict[str, list[float]] = defaultdict(list)
        self.lock = Lock()

    def check(self, key: str) -> None:
        now = time.time()
        with self.lock:
            # Clean expired timestamps
            cutoff = now - self.window_seconds
            valid = [t for t in self.attempts[key] if t > cutoff]
            if len(valid) >= self.max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many authentication attempts. Please wait {int(self.window_seconds)} seconds before retrying.",
                )
            valid.append(now)
            self.attempts[key] = valid

    def reset(self, key: str) -> None:
        with self.lock:
            self.attempts.pop(key, None)


auth_rate_limiter = AuthRateLimiter(max_requests=10, window_seconds=60.0)


def _set_auth_cookie(response: Response, token: str) -> None:
    """Set secure HttpOnly authentication cookie."""
    is_prod = settings.environment.lower() in ("production", "prod", "staging")
    response.set_cookie(
        key="promptcheck_access_token",
        value=token,
        httponly=True,
        max_age=3600,
        expires=3600,
        samesite="lax",
        secure=is_prod,
        path="/",
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    request: Request,
    response: Response,
    user_in: UserCreate,
    db: Session = Depends(get_db),
):
    """Register a new user account with brute-force rate limiting."""
    client_ip = request.client.host if request.client else "unknown"
    auth_rate_limiter.check(f"register:{client_ip}")

    existing_user = db.query(User).filter(User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists",
        )

    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    _set_auth_cookie(response, token)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: Request, response: Response, db: Session = Depends(get_db)):
    """Authenticate with email and password to receive a JWT access token."""
    client_ip = request.client.host if request.client else "unknown"

    email = None
    password = None

    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        raw_email = form.get("email") or form.get("username")
        raw_password = form.get("password")
        if isinstance(raw_email, str):
            email = raw_email
        elif raw_email is not None:
            email = str(raw_email)
        if isinstance(raw_password, str):
            password = raw_password
        elif raw_password is not None:
            password = str(raw_password)
    else:
        try:
            body = await request.json()
            if isinstance(body, dict):
                raw_email = body.get("email") or body.get("username")
                raw_password = body.get("password")
                if isinstance(raw_email, str):
                    email = raw_email
                elif raw_email is not None:
                    email = str(raw_email)
                if isinstance(raw_password, str):
                    password = raw_password
                elif raw_password is not None:
                    password = str(raw_password)
        except Exception:
            pass

    if not isinstance(email, str) or not isinstance(password, str) or not email or not password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Email and password are required.",
        )

    rate_key = f"login:{client_ip}:{email}"
    auth_rate_limiter.check(rate_key)

    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    # Successful login: reset attempts
    auth_rate_limiter.reset(rate_key)

    token = create_access_token(user.id)
    _set_auth_cookie(response, token)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserOut.model_validate(user),
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(response: Response):
    """Log out by clearing authentication cookies."""
    response.delete_cookie(
        key="promptcheck_access_token",
        path="/",
        httponly=True,
        samesite="lax",
    )
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserOut)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get profile of currently authenticated user."""
    return UserOut.model_validate(current_user)
