"""Troca um Google ID token verificado por JWT de curta duração do AgentOS."""

import os
import time
from pathlib import Path

import jwt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


SCOPES = ["agents:read", "agents:run", "sessions:read", "sessions:delete", "traces:read"]


class GoogleToken(BaseModel):
    id_token: str


def settings() -> tuple[str, str, str]:
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    private_key_file = os.getenv("AGNO_QA_JWT_PRIVATE_KEY_FILE", ".secrets/kapo-jwt-private.pem")
    audience = os.getenv("AGNO_QA_JWT_AUDIENCE", "kapo-agentos")
    try:
        private_key = Path(private_key_file).read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Unable to read AGNO_QA_JWT_PRIVATE_KEY_FILE: {private_key_file}") from exc
    if not client_id or not private_key or not audience:
        raise ValueError("GOOGLE_CLIENT_ID, AGNO_QA_JWT_PRIVATE_KEY_FILE, and AGNO_QA_JWT_AUDIENCE are required")
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

        loaded_key = serialization.load_pem_private_key(private_key.encode(), password=None)
        if not isinstance(loaded_key, RSAPrivateKey):
            raise ValueError("Not an RSA private key")
    except (ValueError, TypeError) as exc:
        raise ValueError("AGNO_QA_JWT_PRIVATE_KEY_FILE must contain an unencrypted RSA private key") from exc
    return client_id, private_key, audience


def verification_keys() -> list[str]:
    """Return the local signing key's public half and the optional Agno OS key."""
    _, private_key, _ = settings()
    from cryptography.hazmat.primitives import serialization

    local_public_key = (
        serialization.load_pem_private_key(private_key.encode("utf-8"), password=None)
        .public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode("utf-8")
    )
    keys = [local_public_key]
    os_public_key_file = os.getenv("AGNO_OS_JWT_PUBLIC_KEY_FILE", ".secrets/agno-os-public.pem")
    try:
        os_public_key = Path(os_public_key_file).read_text(encoding="utf-8")
    except FileNotFoundError:
        return keys
    if not os_public_key.strip():
        raise ValueError(f"AGNO_OS_JWT_PUBLIC_KEY_FILE is empty: {os_public_key_file}")
    keys.append(os_public_key)
    return keys


def router() -> APIRouter:
    from google.auth.transport import requests
    from google.oauth2 import id_token

    client_id, private_key, audience = settings()
    workspace_domain = os.getenv("KAPO_WORKSPACE_DOMAIN", "").strip().lower()
    allowed_emails = {
        email.strip().lower()
        for email in os.getenv("KAPO_ALLOWED_EMAILS", "").split(",")
        if email.strip()
    }
    api = APIRouter()

    @api.post("/auth/google")
    def exchange(body: GoogleToken):
        try:
            claims = id_token.verify_oauth2_token(body.id_token, requests.Request(), client_id)
            if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
                raise ValueError("Invalid issuer")
            sub = claims.get("sub")
            if not isinstance(sub, str) or not sub or len(sub) > 255:
                raise ValueError("Invalid subject")
            email = claims.get("email")
            hd = claims.get("hd")
            if not isinstance(email, str) or not email or claims.get("email_verified") is not True:
                raise ValueError("Unverified email")
            email = email.lower()
            if not (
                (workspace_domain and hd == workspace_domain and email.endswith(f"@{workspace_domain}"))
                or email in allowed_emails
            ):
                raise ValueError("Email not allowed")
        except (ValueError, jwt.PyJWTError):
            raise HTTPException(status_code=401, detail="Invalid Google ID token") from None

        now = int(time.time())
        token = jwt.encode(
            {
                "iss": "kapo-google",
                "sub": f"google:{sub}",
                "aud": audience,
                "iat": now,
                "exp": now + 900,
                "scopes": SCOPES,
            },
            private_key,
            algorithm="RS256",
        )
        return {"access_token": token, "token_type": "bearer", "expires_in": 900}

    return api
