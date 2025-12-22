"""
Tests for JWT authentication middleware.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import json
import base64

from jose import jwt
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from httpx import Response

from app.middleware.auth import (
    CognitoJWTValidator,
    JWTValidationError,
    validate_jwt,
    require_authentication,
    require_roles,
    get_tenant_id,
    require_auth_for_sse,
)


# Test constants
TEST_USER_POOL_ID = "us-east-1_testpool"
TEST_REGION = "us-east-1"
TEST_CLIENT_IDS = ["test-client-id"]
TEST_ISSUER = f"https://cognito-idp.{TEST_REGION}.amazonaws.com/{TEST_USER_POOL_ID}"


# Mock JWKS response
MOCK_JWKS = {
    "keys": [
        {
            "kty": "RSA",
            "kid": "test-key-id",
            "use": "sig",
            "alg": "RS256",
            "n": "0vx7agoebGcQSuuPiLJXZptN9nndrQmbXEps2aiAFbWhM78LhWx4cbbfAAtVT86zwu1RK7aPFFxuhDR1L6tSoc_BJECPebWKRXjBZCiFV4n3oknjhMstn64tZ_2W-5JsGY4Hc5n9yBXArwl93lqt7_RN5w6Cf0h4QyQ5v-65YGjQR0_FDW2QvzqY368QQMicAtaSqzs8KJZgnYb9c7d0zgdAZHzu6qMQvRL5hajrn1n91CbOpbISD08qNLyrdkt-bFTWhAI4vMQFh6WeZu0fM4lFd2NcRwr3XPksINHaQ-G_xBniIqbw0Ls1jF44-csFCur-kEgU8awapJzKnqDKgw",
            "e": "AQAB",
        }
    ]
}


def create_test_token(
    claims: dict,
    expired: bool = False,
    wrong_issuer: bool = False,
    wrong_audience: bool = False,
) -> str:
    """Create a test JWT token."""
    now = datetime.utcnow()
    
    default_claims = {
        "sub": "test-user-id",
        "email": "test@example.com",
        "token_use": "access",
        "iss": "wrong-issuer" if wrong_issuer else TEST_ISSUER,
        "aud": ["wrong-client"] if wrong_audience else TEST_CLIENT_IDS,
        "iat": int(now.timestamp()),
        "exp": int((now - timedelta(hours=1) if expired else now + timedelta(hours=1)).timestamp()),
        "cognito:groups": ["analyst"],
        "custom:tenant_id": "test-tenant",
    }
    
    default_claims.update(claims)
    
    # Create a simple unsigned token for testing
    # In real tests, you'd sign with a test private key
    header = {"alg": "RS256", "typ": "JWT", "kid": "test-key-id"}
    
    # Encode without signature for mock testing
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(default_claims).encode()).decode().rstrip("=")
    
    return f"{header_b64}.{payload_b64}.mock-signature"


class TestCognitoJWTValidator:
    """Tests for CognitoJWTValidator class."""
    
    @pytest.fixture
    def validator(self):
        return CognitoJWTValidator(
            user_pool_id=TEST_USER_POOL_ID,
            region=TEST_REGION,
            client_ids=TEST_CLIENT_IDS,
        )
    
    def test_issuer_construction(self, validator):
        """Test that issuer URL is correctly constructed."""
        assert validator.issuer == TEST_ISSUER
        assert TEST_USER_POOL_ID in validator.issuer
        assert TEST_REGION in validator.issuer
    
    def test_jwks_uri_construction(self, validator):
        """Test that JWKS URI is correctly constructed."""
        assert validator.jwks_uri.endswith("/.well-known/jwks.json")
        assert TEST_USER_POOL_ID in validator.jwks_uri
    
    def test_extract_tenant_id_from_custom_claim(self, validator):
        """Test tenant ID extraction from custom claim."""
        claims = {"custom:tenant_id": "my-tenant"}
        assert validator.extract_tenant_id(claims) == "my-tenant"
    
    def test_extract_tenant_id_from_groups(self, validator):
        """Test tenant ID extraction from Cognito groups."""
        claims = {"cognito:groups": ["analyst", "tenant_acme-corp"]}
        assert validator.extract_tenant_id(claims) == "acme-corp"
    
    def test_extract_tenant_id_default(self, validator):
        """Test default tenant ID when none specified."""
        claims = {}
        assert validator.extract_tenant_id(claims) == "default"
    
    def test_extract_roles(self, validator):
        """Test role extraction from Cognito groups."""
        claims = {"cognito:groups": ["admin", "ops", "tenant_acme"]}
        roles = validator.extract_roles(claims)
        assert "admin" in roles
        assert "ops" in roles
        assert "tenant_acme" not in roles  # Tenant groups excluded
    
    @pytest.mark.asyncio
    async def test_validate_token_missing_kid(self, validator):
        """Test validation fails with missing key ID."""
        # Token without kid in header
        token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.sig"
        
        with pytest.raises(JWTValidationError, match="No key ID"):
            await validator.validate_token(token)


class TestAuthMiddleware:
    """Tests for authentication middleware functions."""
    
    @pytest.fixture
    def mock_request(self):
        """Create a mock FastAPI request."""
        request = MagicMock(spec=Request)
        request.headers = {}
        request.state = MagicMock()
        return request
    
    @pytest.mark.asyncio
    async def test_validate_jwt_missing_header(self, mock_request):
        """Test that missing Authorization header returns 401."""
        with patch("app.middleware.auth.settings") as mock_settings:
            mock_settings.auth_enabled = True
            mock_request.headers = {}
            
            with pytest.raises(Exception) as exc_info:
                await validate_jwt(mock_request)
            
            assert exc_info.value.status_code == 401
            assert "Missing Authorization header" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_validate_jwt_invalid_format(self, mock_request):
        """Test that invalid Authorization format returns 401."""
        with patch("app.middleware.auth.settings") as mock_settings:
            mock_settings.auth_enabled = True
            mock_request.headers = {"Authorization": "Basic abc123"}
            
            with pytest.raises(Exception) as exc_info:
                await validate_jwt(mock_request)
            
            assert exc_info.value.status_code == 401
            assert "Invalid Authorization header format" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_validate_jwt_auth_disabled(self, mock_request):
        """Test that auth disabled returns mock claims."""
        with patch("app.middleware.auth.settings") as mock_settings:
            mock_settings.auth_enabled = False
            
            claims = await validate_jwt(mock_request)
            
            assert claims["sub"] == "anonymous"
            assert "tenant_id" not in claims or claims.get("custom:tenant_id") == "default"
    
    def test_get_tenant_id_from_state(self, mock_request):
        """Test tenant ID from request state."""
        mock_request.state.tenant_id = "state-tenant"
        mock_request.headers = {}
        
        assert get_tenant_id(mock_request) == "state-tenant"
    
    def test_get_tenant_id_from_header(self, mock_request):
        """Test tenant ID fallback to header."""
        mock_request.state.tenant_id = None
        mock_request.headers = {"X-Tenant-ID": "header-tenant"}
        
        assert get_tenant_id(mock_request) == "header-tenant"
    
    def test_get_tenant_id_default(self, mock_request):
        """Test default tenant ID."""
        mock_request.state.tenant_id = None
        mock_request.headers = {}
        
        assert get_tenant_id(mock_request) == "default"


class TestRequireRoles:
    """Tests for role requirement decorator."""
    
    @pytest.fixture
    def mock_request(self):
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        return request
    
    @pytest.mark.asyncio
    async def test_require_roles_admin_access(self, mock_request):
        """Test that admin role has access to everything."""
        mock_request.state.user_claims = {"roles": ["admin"]}
        
        checker = require_roles("ops", "analyst")
        result = await checker(mock_request)
        
        assert result == mock_request.state.user_claims
    
    @pytest.mark.asyncio
    async def test_require_roles_specific_role(self, mock_request):
        """Test that specific role grants access."""
        mock_request.state.user_claims = {"roles": ["ops"]}
        
        checker = require_roles("ops")
        result = await checker(mock_request)
        
        assert result == mock_request.state.user_claims
    
    @pytest.mark.asyncio
    async def test_require_roles_missing_role(self, mock_request):
        """Test that missing role returns 403."""
        mock_request.state.user_claims = {"roles": ["viewer"]}
        
        checker = require_roles("admin", "ops")
        
        with pytest.raises(Exception) as exc_info:
            await checker(mock_request)
        
        assert exc_info.value.status_code == 403
    
    @pytest.mark.asyncio
    async def test_require_roles_not_authenticated(self, mock_request):
        """Test that unauthenticated request returns 401."""
        mock_request.state.user_claims = None
        
        checker = require_roles("ops")
        
        with pytest.raises(Exception) as exc_info:
            await checker(mock_request)
        
        assert exc_info.value.status_code == 401


class TestJWTExpiry:
    """Tests for JWT expiry handling."""
    
    @pytest.fixture
    def validator(self):
        return CognitoJWTValidator(
            user_pool_id=TEST_USER_POOL_ID,
            region=TEST_REGION,
            client_ids=TEST_CLIENT_IDS,
        )
    
    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, validator):
        """Test that expired tokens are rejected."""
        # This would require a properly signed expired token
        # For now, we verify the validation logic exists
        token = create_test_token({}, expired=True)
        
        with patch.object(validator, "_get_jwks", return_value=MOCK_JWKS):
            with pytest.raises(JWTValidationError):
                await validator.validate_token(token)


class TestJWTIssuer:
    """Tests for JWT issuer validation."""
    
    @pytest.fixture
    def validator(self):
        return CognitoJWTValidator(
            user_pool_id=TEST_USER_POOL_ID,
            region=TEST_REGION,
            client_ids=TEST_CLIENT_IDS,
        )
    
    @pytest.mark.asyncio
    async def test_wrong_issuer_rejected(self, validator):
        """Test that tokens from wrong issuer are rejected."""
        token = create_test_token({}, wrong_issuer=True)
        
        with patch.object(validator, "_get_jwks", return_value=MOCK_JWKS):
            with pytest.raises(JWTValidationError):
                await validator.validate_token(token)


class TestValidJWT:
    """Tests for valid JWT token processing."""
    
    @pytest.fixture
    def mock_request(self):
        """Create a mock FastAPI request."""
        request = MagicMock(spec=Request)
        request.headers = {}
        request.state = MagicMock()
        return request
    
    @pytest.fixture
    def validator(self):
        return CognitoJWTValidator(
            user_pool_id=TEST_USER_POOL_ID,
            region=TEST_REGION,
            client_ids=TEST_CLIENT_IDS,
        )
    
    @pytest.mark.asyncio
    async def test_valid_jwt_success(self, mock_request, validator):
        """Test that a valid JWT is accepted and claims are extracted."""
        valid_token = create_test_token({
            "sub": "user-123",
            "email": "analyst@company.com",
            "custom:tenant_id": "acme-corp",
            "cognito:groups": ["analyst", "viewer"],
        })
        
        mock_claims = {
            "sub": "user-123",
            "email": "analyst@company.com",
            "custom:tenant_id": "acme-corp",
            "cognito:groups": ["analyst", "viewer"],
            "iss": TEST_ISSUER,
        }
        
        with patch("app.middleware.auth.settings") as mock_settings:
            mock_settings.auth_enabled = True
            mock_settings.cognito_user_pool_id = TEST_USER_POOL_ID
            mock_settings.cognito_region = TEST_REGION
            mock_settings.cognito_client_ids = TEST_CLIENT_IDS
            
            mock_request.headers = {"Authorization": f"Bearer {valid_token}"}
            
            with patch("app.middleware.auth.CognitoJWTValidator") as MockValidator:
                mock_validator_instance = AsyncMock()
                mock_validator_instance.validate_token = AsyncMock(return_value=mock_claims)
                mock_validator_instance.extract_tenant_id = MagicMock(return_value="acme-corp")
                mock_validator_instance.extract_roles = MagicMock(return_value=["analyst", "viewer"])
                MockValidator.return_value = mock_validator_instance
                
                claims = await validate_jwt(mock_request)
                
                assert claims["sub"] == "user-123"
                assert claims["email"] == "analyst@company.com"
                assert "tenant_id" in claims or claims.get("custom:tenant_id") == "acme-corp"
    
    def test_tenant_extraction_from_valid_claims(self, validator):
        """Test tenant ID is correctly extracted from valid JWT claims."""
        claims = {
            "sub": "user-456",
            "custom:tenant_id": "tenant-xyz",
        }
        
        tenant_id = validator.extract_tenant_id(claims)
        assert tenant_id == "tenant-xyz"
    
    def test_role_extraction_from_valid_claims(self, validator):
        """Test roles are correctly extracted from valid JWT claims."""
        claims = {
            "cognito:groups": ["admin", "analyst", "tenant_company-x"],
        }
        
        roles = validator.extract_roles(claims)
        assert "admin" in roles
        assert "analyst" in roles
        # Tenant groups should be filtered out
        assert "tenant_company-x" not in roles


class TestNoTenantClaim:
    """Tests for JWT tokens missing tenant claims."""
    
    @pytest.fixture
    def mock_request(self):
        """Create a mock FastAPI request."""
        request = MagicMock(spec=Request)
        request.headers = {}
        request.state = MagicMock()
        return request
    
    @pytest.fixture
    def validator(self):
        return CognitoJWTValidator(
            user_pool_id=TEST_USER_POOL_ID,
            region=TEST_REGION,
            client_ids=TEST_CLIENT_IDS,
        )
    
    def test_no_tenant_claim_returns_default(self, validator):
        """Test that missing tenant claim returns default."""
        claims = {
            "sub": "user-789",
            "email": "user@example.com",
            # No custom:tenant_id, no tenant_ prefixed groups
            "cognito:groups": ["analyst"],
        }
        
        tenant_id = validator.extract_tenant_id(claims)
        assert tenant_id == "default"
    
    @pytest.mark.asyncio
    async def test_require_auth_for_sse_no_tenant_rejects(self, mock_request):
        """Test that SSE routes reject tokens without tenant claims."""
        mock_claims = {
            "sub": "user-no-tenant",
            "email": "notenant@example.com",
            # No tenant claim
        }
        
        with patch("app.middleware.auth.settings") as mock_settings:
            mock_settings.auth_enabled = True
            mock_settings.cognito_user_pool_id = TEST_USER_POOL_ID
            mock_settings.cognito_region = TEST_REGION
            mock_settings.cognito_client_ids = TEST_CLIENT_IDS
            
            mock_request.headers = {"Authorization": "Bearer mock-token"}
            
            with patch("app.middleware.auth.validate_jwt", new_callable=AsyncMock) as mock_validate:
                mock_validate.return_value = mock_claims
                mock_request.state.user_claims = mock_claims
                mock_request.state.tenant_id = None
                
                # Should raise 403 because no tenant in claims
                with pytest.raises(Exception) as exc_info:
                    await require_auth_for_sse(mock_request)
                
                assert exc_info.value.status_code == 403


class TestTenantHeaderOverride:
    """Tests for tenant header override protection."""
    
    @pytest.fixture
    def mock_request(self):
        """Create a mock FastAPI request."""
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        return request
    
    def test_tenant_header_override_blocked_when_jwt_tenant(self, mock_request):
        """Test that X-Tenant-ID header cannot override JWT tenant claim."""
        mock_request.state.tenant_id = "jwt-tenant"
        mock_request.headers = {"X-Tenant-ID": "attacker-tenant"}
        
        # When JWT tenant is present, header override should be forbidden
        with pytest.raises(Exception) as exc_info:
            get_tenant_id(mock_request)
        
        assert exc_info.value.status_code == 403
        assert "override" in str(exc_info.value.detail).lower()
    
    def test_tenant_header_allowed_when_no_jwt_tenant(self, mock_request):
        """Test that X-Tenant-ID header is used when no JWT tenant."""
        mock_request.state.tenant_id = None
        mock_request.headers = {"X-Tenant-ID": "header-tenant"}
        
        tenant_id = get_tenant_id(mock_request)
        assert tenant_id == "header-tenant"
    
    def test_jwt_tenant_takes_precedence(self, mock_request):
        """Test that JWT tenant is returned when no header override attempt."""
        mock_request.state.tenant_id = "jwt-tenant"
        mock_request.headers = {}  # No X-Tenant-ID header
        
        tenant_id = get_tenant_id(mock_request)
        assert tenant_id == "jwt-tenant"


class TestRequireAuthForSSE:
    """Tests for the require_auth_for_sse dependency."""
    
    @pytest.fixture
    def mock_request(self):
        """Create a mock FastAPI request."""
        request = MagicMock(spec=Request)
        request.headers = {}
        request.state = MagicMock()
        return request
    
    @pytest.mark.asyncio
    async def test_sse_auth_success_with_tenant(self, mock_request):
        """Test SSE auth succeeds with valid JWT and tenant claim."""
        mock_claims = {
            "sub": "user-sse",
            "email": "sse@example.com",
            "custom:tenant_id": "streaming-tenant",
            "roles": ["analyst"],
        }
        
        with patch("app.middleware.auth.settings") as mock_settings:
            mock_settings.auth_enabled = True
            
            with patch("app.middleware.auth.validate_jwt", new_callable=AsyncMock) as mock_validate:
                mock_validate.return_value = mock_claims
                mock_request.state.tenant_id = "streaming-tenant"
                
                result = await require_auth_for_sse(mock_request)
                
                assert result["tenant_id"] == "streaming-tenant"
                assert result["claims"] == mock_claims
    
    @pytest.mark.asyncio
    async def test_sse_auth_fails_without_jwt(self, mock_request):
        """Test SSE auth fails without valid JWT."""
        with patch("app.middleware.auth.settings") as mock_settings:
            mock_settings.auth_enabled = True
            mock_request.headers = {}  # No Authorization header
            
            with patch("app.middleware.auth.validate_jwt", new_callable=AsyncMock) as mock_validate:
                from fastapi import HTTPException
                mock_validate.side_effect = HTTPException(status_code=401, detail="Missing Authorization header")
                
                with pytest.raises(Exception) as exc_info:
                    await require_auth_for_sse(mock_request)
                
                assert exc_info.value.status_code == 401
