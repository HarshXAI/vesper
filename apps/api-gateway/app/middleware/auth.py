"""
JWT Authentication Middleware for VESPER API Gateway.

Validates JWT tokens from AWS Cognito and injects tenant information
from claims into the request context.
"""

import time
from typing import Optional, Dict, Any, Callable
from functools import lru_cache

import httpx
import structlog
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, jwk, JWTError
from jose.exceptions import JWKError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from starlette.responses import Response

from app.core.config import settings

logger = structlog.get_logger(__name__)

# HTTP Bearer security scheme
security = HTTPBearer(auto_error=False)


class JWTValidationError(Exception):
    """Raised when JWT validation fails."""
    pass


class CognitoJWTValidator:
    """
    Validates JWTs issued by AWS Cognito.
    
    Features:
    - JWKS caching with automatic refresh
    - Token expiry validation
    - Issuer and audience verification
    - Tenant ID extraction from claims
    """
    
    def __init__(
        self,
        user_pool_id: str,
        region: str,
        client_ids: list[str],
        cache_ttl_seconds: int = 3600,
    ):
        self.user_pool_id = user_pool_id
        self.region = region
        self.client_ids = client_ids
        self.cache_ttl = cache_ttl_seconds
        
        self.issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
        self.jwks_uri = f"{self.issuer}/.well-known/jwks.json"
        
        self._jwks_cache: Optional[Dict[str, Any]] = None
        self._jwks_cache_time: float = 0
        
        logger.info(
            "cognito_jwt_validator_initialized",
            user_pool_id=user_pool_id,
            region=region,
            issuer=self.issuer,
        )
    
    async def _get_jwks(self) -> Dict[str, Any]:
        """Fetch and cache JWKS from Cognito."""
        now = time.time()
        
        # Return cached JWKS if still valid
        if self._jwks_cache and (now - self._jwks_cache_time) < self.cache_ttl:
            return self._jwks_cache
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.jwks_uri, timeout=10.0)
                response.raise_for_status()
                self._jwks_cache = response.json()
                self._jwks_cache_time = now
                
                logger.info("jwks_refreshed", uri=self.jwks_uri)
                return self._jwks_cache
        except Exception as e:
            logger.error("jwks_fetch_failed", error=str(e))
            
            # Return stale cache if available
            if self._jwks_cache:
                logger.warning("using_stale_jwks_cache")
                return self._jwks_cache
            
            raise JWTValidationError(f"Failed to fetch JWKS: {e}")
    
    def _get_signing_key(self, jwks: Dict[str, Any], kid: str) -> Any:
        """Get the signing key for the given key ID."""
        for key_data in jwks.get("keys", []):
            if key_data.get("kid") == kid:
                try:
                    return jwk.construct(key_data)
                except JWKError as e:
                    raise JWTValidationError(f"Invalid JWK: {e}")
        
        raise JWTValidationError(f"Key ID {kid} not found in JWKS")
    
    async def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate a JWT token and return the claims.
        
        Args:
            token: The JWT token string
            
        Returns:
            Dictionary of validated claims
            
        Raises:
            JWTValidationError: If validation fails
        """
        try:
            # Decode header to get key ID
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            
            if not kid:
                raise JWTValidationError("No key ID in token header")
            
            # Get JWKS and signing key
            jwks = await self._get_jwks()
            signing_key = self._get_signing_key(jwks, kid)
            
            # Verify and decode token
            claims = jwt.decode(
                token,
                signing_key.to_pem().decode("utf-8"),
                algorithms=["RS256"],
                audience=self.client_ids,
                issuer=self.issuer,
                options={
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )
            
            # Validate token use (must be access or id token)
            token_use = claims.get("token_use")
            if token_use not in ["access", "id"]:
                raise JWTValidationError(f"Invalid token use: {token_use}")
            
            logger.debug(
                "jwt_validated",
                sub=claims.get("sub"),
                token_use=token_use,
            )
            
            return claims
            
        except JWTError as e:
            logger.warning("jwt_validation_failed", error=str(e))
            raise JWTValidationError(f"JWT validation failed: {e}")
    
    def extract_tenant_id(self, claims: Dict[str, Any]) -> str:
        """Extract tenant ID from claims, with fallback to 'default'."""
        # Try custom claim first
        tenant_id = claims.get("custom:tenant_id")
        
        if not tenant_id:
            # Try cognito:groups for tenant-based routing
            groups = claims.get("cognito:groups", [])
            for group in groups:
                if group.startswith("tenant_"):
                    tenant_id = group[7:]  # Remove "tenant_" prefix
                    break
        
        return tenant_id or "default"
    
    def extract_roles(self, claims: Dict[str, Any]) -> list[str]:
        """Extract user roles from Cognito groups."""
        groups = claims.get("cognito:groups", [])
        # Filter out tenant groups
        return [g for g in groups if not g.startswith("tenant_")]


# Global validator instance
_validator: Optional[CognitoJWTValidator] = None


def get_jwt_validator() -> CognitoJWTValidator:
    """Get or create the global JWT validator."""
    global _validator
    
    if _validator is None:
        _validator = CognitoJWTValidator(
            user_pool_id=settings.cognito_user_pool_id,
            region=settings.cognito_region,
            client_ids=[
                settings.cognito_analyst_client_id,
                settings.cognito_ops_client_id,
                settings.cognito_api_client_id,
            ],
        )
    
    return _validator


async def validate_jwt(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = None,
) -> Dict[str, Any]:
    """
    Validate JWT from Authorization header and inject claims into request state.
    
    Returns:
        Validated claims dictionary
        
    Raises:
        HTTPException: 401 if authentication fails
    """
    if not settings.auth_enabled:
        # Auth disabled - return mock claims
        return {
            "sub": "anonymous",
            "email": "anonymous@localhost",
            "custom:tenant_id": "default",
            "cognito:groups": ["analyst"],
        }
    
    # Get token from Authorization header
    auth_header = request.headers.get("Authorization")
    
    if not auth_header:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = auth_header[7:]  # Remove "Bearer " prefix
    
    try:
        validator = get_jwt_validator()
        claims = await validator.validate_token(token)
        
        # Extract and inject tenant ID
        tenant_id = validator.extract_tenant_id(claims)
        claims["tenant_id"] = tenant_id
        
        # Extract and inject roles
        roles = validator.extract_roles(claims)
        claims["roles"] = roles
        
        # Store in request state for downstream use
        request.state.user_claims = claims
        request.state.tenant_id = tenant_id
        request.state.user_roles = roles
        request.state.user_id = claims.get("sub")
        request.state.user_email = claims.get("email")
        
        return claims
        
    except JWTValidationError as e:
        logger.warning("authentication_failed", error=str(e))
        raise HTTPException(
            status_code=401,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_roles(*required_roles: str):
    """
    Dependency to require specific roles for an endpoint.
    
    Usage:
        @app.get("/admin", dependencies=[Depends(require_roles("admin"))])
    """
    async def role_checker(request: Request):
        claims = getattr(request.state, "user_claims", None)
        
        if not claims:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        user_roles = set(claims.get("roles", []))
        required = set(required_roles)
        
        # Admin role has access to everything
        if "admin" in user_roles:
            return claims
        
        if not user_roles.intersection(required):
            raise HTTPException(
                status_code=403,
                detail=f"Requires one of roles: {', '.join(required_roles)}",
            )
        
        return claims
    
    return role_checker


def get_tenant_id(request: Request) -> str:
    """
    Get tenant ID from request state (JWT claim).
    
    Security: JWT tenant claim is authoritative - header override is forbidden
    to prevent tenant impersonation attacks.
    """
    # JWT tenant claim is authoritative - no header fallback for security
    tenant_id = getattr(request.state, "tenant_id", None)
    
    if tenant_id:
        # Log if header differs (potential attack attempt)
        header_tenant = request.headers.get("X-Tenant-ID")
        if header_tenant and header_tenant != tenant_id:
            logger.warning(
                "tenant_header_mismatch_blocked",
                jwt_tenant=tenant_id,
                header_tenant=header_tenant,
                user_id=getattr(request.state, "user_id", "unknown"),
            )
        return tenant_id
    
    # Only allow header fallback if auth is disabled (dev mode)
    if not settings.auth_enabled:
        return request.headers.get("X-Tenant-ID", "default")
    
    # Auth enabled but no JWT tenant - should not happen if middleware ran
    raise HTTPException(
        status_code=401,
        detail="Missing tenant claim in token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(request: Request) -> Dict[str, Any]:
    """Get current user claims from request state."""
    claims = getattr(request.state, "user_claims", None)
    
    if not claims:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return claims


async def require_authentication(request: Request) -> Dict[str, Any]:
    """
    Dependency that enforces JWT authentication on a route.
    
    Usage:
        @app.post("/v1/ask", dependencies=[Depends(require_authentication)])
    
    Returns validated claims or raises 401.
    """
    if not settings.auth_enabled:
        # Auth disabled - return mock claims for dev mode
        logger.debug("auth_disabled_dev_mode")
        request.state.tenant_id = request.headers.get("X-Tenant-ID", "default")
        request.state.user_id = "dev-user"
        request.state.user_claims = {
            "sub": "dev-user",
            "email": "dev@localhost",
            "custom:tenant_id": request.state.tenant_id,
            "cognito:groups": ["analyst"],
        }
        return request.state.user_claims
    
    # Auth enabled - require valid JWT
    claims = await validate_jwt(request)
    
    # Verify tenant claim exists
    tenant_id = claims.get("tenant_id")
    if not tenant_id or tenant_id == "default":
        # Check if custom claim was present
        if not claims.get("custom:tenant_id"):
            logger.warning(
                "missing_tenant_claim",
                sub=claims.get("sub"),
                email=claims.get("email"),
            )
            raise HTTPException(
                status_code=403,
                detail="Token missing required tenant_id claim",
            )
    
    return claims


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware for JWT validation.
    
    Validates JWT tokens and injects user/tenant information into request state.
    Can be disabled via settings.auth_enabled for development.
    """
    
    def __init__(self, app: ASGIApp, settings=None):
        super().__init__(app)
        self.settings = settings or globals()['settings']
        self.validator = get_jwt_validator() if self.settings.auth_enabled else None
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and validate authentication."""
        # Skip auth for public endpoints (health, metrics, docs)
        public_paths = ["/health", "/metrics", "/docs", "/openapi.json", "/redoc"]
        if request.url.path in public_paths:
            return await call_next(request)
        
        # Skip auth if disabled (dev mode)
        if not self.settings.auth_enabled:
            # Inject mock claims for dev mode
            request.state.tenant_id = request.headers.get("X-Tenant-ID", "default")
            request.state.user_id = "dev-user"
            request.state.user_email = "dev@localhost"
            request.state.user_roles = ["analyst"]
            request.state.user_claims = {
                "sub": "dev-user",
                "email": "dev@localhost",
                "custom:tenant_id": request.state.tenant_id,
                "cognito:groups": ["analyst"],
            }
            return await call_next(request)
        
        # Validate JWT token
        try:
            auth_header = request.headers.get("Authorization")
            
            if not auth_header or not auth_header.startswith("Bearer "):
                raise HTTPException(
                    status_code=401,
                    detail="Missing or invalid Authorization header",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            token = auth_header[7:]  # Remove "Bearer " prefix
            claims = await self.validator.validate_token(token)
            
            # Extract and inject tenant ID
            tenant_id = self.validator.extract_tenant_id(claims)
            roles = self.validator.extract_roles(claims)
            
            # Store in request state
            request.state.user_claims = claims
            request.state.tenant_id = tenant_id
            request.state.user_roles = roles
            request.state.user_id = claims.get("sub")
            request.state.user_email = claims.get("email")
            
            return await call_next(request)
            
        except JWTValidationError as e:
            logger.warning("jwt_validation_failed", error=str(e), path=request.url.path)
            raise HTTPException(
                status_code=401,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception as e:
            logger.error("auth_middleware_error", error=str(e), path=request.url.path)
            raise HTTPException(
                status_code=500,
                detail="Internal authentication error"
            )
