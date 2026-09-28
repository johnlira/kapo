"""Exercita o isolamento do AgentOS pela API ASGI com sessões persistidas."""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.run.agent import RunOutput
from agno.session import AgentSession
from fastapi.testclient import TestClient

from app.auth import SCOPES


class AuthIsolationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.local_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.platform_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_key_file = Path(self.directory.name) / "local-private.pem"
        private_key_file.write_bytes(self.local_private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))
        platform_key_file = Path(self.directory.name) / "agno-os-public.pem"
        platform_key_file.write_bytes(self.platform_private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ))
        environment = patch.dict(os.environ, {
            "GOOGLE_CLIENT_ID": "client-id",
            "AGNO_QA_JWT_PRIVATE_KEY_FILE": str(private_key_file),
            "AGNO_OS_JWT_PUBLIC_KEY_FILE": str(platform_key_file),
            "AGNO_QA_JWT_AUDIENCE": "kapo-agentos",
            "AGNO_QA_DB_FILE": str(Path(self.directory.name) / "sessions.db"),
        })
        environment.start()
        self.addCleanup(environment.stop)

        from app.main import create_app

        self.app = create_app()
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        self.db = SqliteDb(db_file=os.environ["AGNO_QA_DB_FILE"])
        self.agent_id = "kapo"

    def headers(self, user, scopes=SCOPES):
        now = int(time.time())
        token = jwt.encode({
            "iss": "kapo-google", "sub": f"google:{user}", "aud": "kapo-agentos",
            "iat": now, "exp": now + 900, "scopes": scopes,
        }, self.local_private_key, algorithm="RS256")
        return {"Authorization": f"Bearer {token}"}

    def test_sessions_runs_and_delete_are_scoped_to_jwt(self):
        for user in ("alice", "bob"):
            self.db.upsert_session(AgentSession(
                session_id=f"session-{user}", user_id=f"google:{user}",
                agent_id=self.agent_id,
            ))

        alice = self.headers("alice")
        bob = self.headers("bob")
        for headers, own, other in ((alice, "alice", "bob"), (bob, "bob", "alice")):
            for params in ({}, {"user_id": f"google:{other}"}):
                response = self.client.get("/sessions", headers=headers, params=params)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual([row["session_id"] for row in response.json()["data"]], [f"session-{own}"])

            self.assertEqual(self.client.get(f"/sessions/session-{own}", headers=headers).status_code, 200)
            self.assertEqual(self.client.get(f"/sessions/session-{other}", headers=headers,
                                             params={"user_id": f"google:{other}"}).status_code, 404)
            self.assertEqual(self.client.get(f"/sessions/session-{other}/runs", headers=headers,
                                             params={"user_id": f"google:{other}"}).status_code, 404)
            response = self.client.delete(f"/sessions/session-{other}", headers=headers,
                                          params={"user_id": f"google:{other}"})
            self.assertEqual(response.status_code, 204, response.text)
            self.assertIsNotNone(self.db.get_session(session_id=f"session-{other}", user_id=f"google:{other}"))

        self.assertEqual(self.client.delete("/sessions/session-alice", headers=alice,
                                            params={"user_id": "google:bob"}).status_code, 204)
        self.assertIsNone(self.db.get_session(session_id="session-alice"))
        self.assertIsNotNone(self.db.get_session(session_id="session-bob"))

    def test_scopes_and_exclusions(self):
        from agno.os.scopes import get_default_scope_mappings, get_required_scopes_for_route

        mappings = get_default_scope_mappings()
        for method, path, scope in (
            ("GET", "/sessions", "sessions:read"),
            ("GET", "/sessions/example/runs", "sessions:read"),
            ("DELETE", "/sessions/example", "sessions:delete"),
            ("POST", "/agents/example/runs", "agents:run"),
            ("GET", "/traces", "traces:read"),
        ):
            self.assertIn(scope, SCOPES)
            self.assertIn(scope, get_required_scopes_for_route(mappings, method, path))

        self.assertEqual(self.client.get("/sessions").status_code, 401)
        self.assertEqual(self.client.get("/sessions", headers=self.headers("alice", ["agents:read"])).status_code, 403)
        self.assertEqual(self.client.get("/sessions", headers={"Authorization": "Bearer invalid"}).status_code, 401)
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/metrics", headers=self.headers("alice")).status_code, 404)
        self.assertNotEqual(self.client.post("/auth/google", json={"id_token": "invalid"}).status_code, 403)
        for path in ("/info", "/docs", "/openapi.json"):
            self.assertIn(self.client.get(path).status_code, (401, 404))
            self.assertEqual(self.client.get(path, headers=self.headers("alice")).status_code, 404)

    def test_platform_pat_reaches_native_agentos_authorization(self):
        response = self.client.get("/metrics", headers={"Authorization": "Bearer agno_pat_unregistered"})
        # The app's chat-surface filter must not reject platform credentials; the
        # native AgentOS verifier rejects this unregistered PAT with 401.
        self.assertEqual(response.status_code, 401)
        self.assertNotEqual(response.json().get("detail"), "Not available")
        self.assertEqual(
            self.client.post("/metrics/refresh", headers={"Authorization": "Bearer agno_pat_unregistered"}).status_code,
            401,
        )

    def test_agno_os_browser_preflight_uses_native_cors(self):
        response = self.client.options(
            "/health",
            headers={
                "Origin": "https://os.agno.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "https://os.agno.com")

    def test_metrics_access_failures_are_readable_from_agno_os(self):
        origin = {"Origin": "https://os.agno.com"}
        for headers, status in (
            (origin, 401),
            ({**origin, **self.headers("alice")}, 404),
            ({**origin, "Authorization": "Bearer agno_pat_unregistered"}, 401),
        ):
            with self.subTest(status=status, credential=headers.get("Authorization")):
                response = self.client.get("/metrics", headers=headers)
                self.assertEqual(response.status_code, status, response.text)
                self.assertEqual(response.headers.get("access-control-allow-origin"), origin["Origin"])

    def test_control_plane_rsa_jwt_can_read_metrics(self):
        now = int(time.time())
        token = jwt.encode(
            {
                "iss": "https://os.agno.com",
                "sub": "control-plane",
                "aud": "this-agentos-id",
                "iat": now,
                "exp": now + 300,
                "scopes": ["metrics:read", "agents:read", "traces:read"],
            },
            self.platform_private_key,
            algorithm="RS256",
        )
        response = self.client.get(
            "/metrics",
            headers={"Authorization": f"Bearer {token}", "Origin": "https://os.agno.com"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "https://os.agno.com")

        status = self.client.get(
            "/metrics/refresh/status",
            headers={"Authorization": f"Bearer {token}", "Origin": "https://os.agno.com"},
        )
        self.assertEqual(status.status_code, 200, status.text)
        self.assertEqual(status.headers.get("access-control-allow-origin"), "https://os.agno.com")
        self.assertEqual(status.json()["status"], "idle")

        denied = self.client.post("/metrics/refresh", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(denied.status_code, 403, denied.text)

        writer = jwt.encode(
            {
                "iss": "https://os.agno.com", "sub": "control-plane", "aud": "this-agentos-id",
                "iat": now, "exp": now + 300, "scopes": ["metrics:write"],
            },
            self.platform_private_key,
            algorithm="RS256",
        )
        refresh = self.client.post(
            "/metrics/refresh?background=true",
            headers={"Authorization": f"Bearer {writer}", "Origin": "https://os.agno.com"},
        )
        self.assertEqual(refresh.status_code, 202, refresh.text)
        self.assertEqual(refresh.headers.get("access-control-allow-origin"), "https://os.agno.com")
        self.assertIn(refresh.json()["status"], ("started", "already_running"))

    def test_run_rejects_foreign_session_and_pins_spoofed_user_id(self):
        agent_id = self.agent_id
        self.db.upsert_session(AgentSession(
            session_id="owned-by-bob", user_id="google:bob", agent_id=agent_id,
        ))
        alice = self.headers("alice")
        with patch.object(Agent, "arun", new_callable=AsyncMock, return_value=RunOutput(content="mock")) as run:
            response = self.client.post(f"/agents/{agent_id}/runs", headers=alice,
                                        data={"message": "oi", "stream": "false", "session_id": "owned-by-bob",
                                              "user_id": "google:bob"})
            self.assertEqual(response.status_code, 404, response.text)
            run.assert_not_called()

            response = self.client.post(f"/agents/{agent_id}/runs", headers=alice,
                                        data={"message": "oi", "stream": "false", "user_id": "google:bob"})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(run.call_args.kwargs["user_id"], "google:alice")
