"""Verifica troca de identidade e regras de acesso ao AgentOS."""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth import router


class AuthBackendTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_key_file = Path(self.directory.name) / "local-private.pem"
        private_key_file.write_bytes(self.private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))
        self.environment = patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "client-id",
                "AGNO_QA_JWT_PRIVATE_KEY_FILE": str(private_key_file),
                "AGNO_QA_JWT_AUDIENCE": "kapo-agentos",
                "KAPO_WORKSPACE_DOMAIN": "example.com",
                "KAPO_ALLOWED_EMAILS": "person@gmail.com",
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.client = TestClient(FastAPI(routes=router().routes))
        self.addCleanup(self.client.close)

    def exchange(self, claims):
        with patch("google.oauth2.id_token.verify_oauth2_token", return_value=claims) as verify:
            response = self.client.post("/auth/google", json={"id_token": "signed-google-token"})
        verify.assert_called_once()
        self.assertEqual(verify.call_args.args[2], "client-id")
        return response

    def test_workspace_member_gets_scoped_jwt(self):
        response = self.exchange(
            {"sub": "123", "iss": "https://accounts.google.com", "email": "USER@example.com", "email_verified": True, "hd": "example.com"}
        )
        self.assertEqual(response.status_code, 200)
        claims = jwt.decode(
            response.json()["access_token"],
            self.private_key.public_key(),
            algorithms=["RS256"],
            audience="kapo-agentos",
        )
        self.assertEqual(claims["iss"], "kapo-google")
        self.assertEqual(claims["sub"], "google:123")
        self.assertLessEqual(claims["exp"] - int(time.time()), 900)
        self.assertIn("sessions:delete", claims["scopes"])
        self.assertIn("traces:read", claims["scopes"])
        self.assertNotIn("agent_os:admin", claims["scopes"])

    def test_allowlisted_verified_personal_email(self):
        response = self.exchange(
            {"sub": "personal", "iss": "accounts.google.com", "email": "PERSON@gmail.com", "email_verified": True}
        )
        self.assertEqual(response.status_code, 200)

    def test_rejects_unauthorized_claims(self):
        valid = {"sub": "123", "iss": "https://accounts.google.com", "email": "user@example.com", "email_verified": True, "hd": "example.com"}
        for changes in (
            {"iss": "fake"}, {"sub": ""}, {"email_verified": False},
            {"email_verified": "true"}, {"email": "user@other.com"},
            {"hd": "other.com"}, {"hd": None}, {"email": None},
        ):
            with self.subTest(changes=changes):
                self.assertEqual(self.exchange({**valid, **changes}).status_code, 401)

    def test_rejects_invalid_google_token(self):
        with patch("google.oauth2.id_token.verify_oauth2_token", side_effect=ValueError):
            self.assertEqual(self.client.post("/auth/google", json={"id_token": "bad"}).status_code, 401)


if __name__ == "__main__":
    unittest.main()
