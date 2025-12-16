"""
JWT Authentication Service for S11.
Implements JWKS-based JWT verification according to VERIFY.md specification.
"""

import os
import time
import threading
import logging
from functools import wraps
from typing import Optional
import jwt
import requests
from flask import request, g
from flask_restx import abort

logger = logging.getLogger(__name__)


class JWTAuthService:
    """
    Service to handle JWT verification using JWKS from Identity Service.
    Implements caching with TTL-based refresh.
    """

    def __init__(self):
        self.identity_service_url = os.getenv("IDENTITY_SERVICE_URL", "http://localhost:8000")
        self.jwks_ttl_minutes = int(os.getenv("JWKS_TTL_IN_MINUTES", "10"))
        self.jwks_cache: dict = {}
        self.jwks_last_fetch: float = 0
        self.jwks_lock = threading.Lock()
        
        # Fetch JWKS at startup
        self._fetch_jwks()
        
        # Start background refresh thread
        self._start_refresh_thread()

    def _get_jwks_url(self) -> str:
        return f"{self.identity_service_url}/.well-known/jwks.json"

    def _fetch_jwks(self) -> bool:
        """
        Fetch JWKS from Identity Service.
        Returns True if successful, False otherwise.
        """
        try:
            response = requests.get(self._get_jwks_url(), timeout=10)
            response.raise_for_status()
            jwks_data = response.json()
            
            with self.jwks_lock:
                # Support multiple keys - store by kid
                if isinstance(jwks_data, list):
                    self.jwks_cache = {key["kid"]: key for key in jwks_data}
                elif isinstance(jwks_data, dict):
                    if "keys" in jwks_data:
                        self.jwks_cache = {key["kid"]: key for key in jwks_data["keys"]}
                    else:
                        # Single key format
                        self.jwks_cache = {jwks_data["kid"]: jwks_data}
                self.jwks_last_fetch = time.time()
            
            logger.info(f"Successfully fetched JWKS with {len(self.jwks_cache)} key(s)")
            return True
        except Exception as e:
            logger.warning(f"Failed to fetch JWKS: {e}")
            return False

    def _start_refresh_thread(self):
        """Start background thread for TTL-based JWKS refresh."""
        def refresh_loop():
            while True:
                time.sleep(self.jwks_ttl_minutes * 60)
                self._fetch_jwks()

        thread = threading.Thread(target=refresh_loop, daemon=True)
        thread.start()

    def _get_public_key(self, kid: str) -> Optional[str]:
        """
        Get public key by kid from cache.
        DO NOT refresh on unknown kid (DoS prevention).
        """
        with self.jwks_lock:
            key_data = self.jwks_cache.get(kid)
            if key_data:
                return key_data.get("public_key")
        return None

    def verify_token(self, token: str) -> dict:
        """
        Verify JWT token and return decoded payload.
        Raises exceptions on verification failure.
        """
        # Step 1: Parse JWT Header
        try:
            unverified_header = jwt.get_unverified_header(token)
        except jwt.exceptions.DecodeError as e:
            raise ValueError(f"Invalid JWT format: {e}")

        alg = unverified_header.get("alg")
        kid = unverified_header.get("kid")

        # Verify algorithm is RS256 only
        if alg != "RS256":
            raise ValueError(f"Unsupported algorithm: {alg}. Only RS256 is allowed.")

        if not kid:
            raise ValueError("Missing 'kid' in JWT header")

        # Step 2: Resolve Public Key (DO NOT refresh on unknown kid)
        public_key_pem = self._get_public_key(kid)
        if not public_key_pem:
            raise ValueError(f"Unknown key id: {kid}")

        # Step 3: Verify Signature
        try:
            payload = jwt.decode(
                token,
                public_key_pem,
                algorithms=["RS256"],
                options={
                    "require": ["exp", "iat", "sub"],
                    "verify_exp": True,
                    "verify_iat": True,
                }
            )
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidSignatureError:
            raise ValueError("Invalid token signature")
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid token: {e}")

        # Step 4: Validate Claims
        required_claims = ["sub", "full_name", "email"]
        for claim in required_claims:
            if claim not in payload:
                raise ValueError(f"Missing required claim: {claim}")

        # Ensure permissions is an array (default to empty)
        if "permissions" not in payload:
            payload["permissions"] = []
        elif not isinstance(payload["permissions"], list):
            raise ValueError("'permissions' claim must be an array")

        return payload


# Global instance
_jwt_auth_service: Optional[JWTAuthService] = None


def get_jwt_auth_service() -> JWTAuthService:
    """Get or create the global JWTAuthService instance."""
    global _jwt_auth_service
    if _jwt_auth_service is None:
        _jwt_auth_service = JWTAuthService()
    return _jwt_auth_service


def require_auth(f):
    """
    Decorator to require JWT authentication on a Flask route.
    Stores decoded payload in flask.g.current_user.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            logger.warning("Missing or invalid Authorization header")
            abort(401, "Missing or invalid Authorization header")

        token = auth_header[7:]  # Remove "Bearer " prefix
        
        try:
            jwt_service = get_jwt_auth_service()
            payload = jwt_service.verify_token(token)
            g.current_user = payload
        except ValueError as e:
            logger.warning(f"JWT verification failed: {e}")
            abort(401, str(e))

        return f(*args, **kwargs)
    
    return decorated


def require_permission(permission: str):
    """
    Decorator to require a specific permission.
    Must be used after @require_auth.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = getattr(g, "current_user", None)
            if not user:
                abort(401, "Authentication required")
            
            permissions = user.get("permissions", [])
            if permission not in permissions:
                abort(403, f"Missing required permission: {permission}")
            
            return f(*args, **kwargs)
        return decorated
    return decorator
