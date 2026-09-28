"""Ponto de entrada da API do agente e modo CLI simples."""

import argparse
import os
from pathlib import Path


def load_env() -> None:
    """Carrega variáveis do arquivo .env sem sobrescrever o ambiente atual."""
    env_file = Path(".env")
    if not env_file.is_file():
        return

    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        name, value = line.split("=", maxsplit=1)
        os.environ.setdefault(name.strip(), value.strip().strip("'\""))


def serve() -> None:
    """Inicia o AgentOS para conexão com o Agno Control Plane."""
    import uvicorn

    load_env()
    uvicorn.run(
        "app.main:app",
        host=os.getenv("AGNO_QA_HOST", "0.0.0.0"),
        port=int(os.getenv("AGNO_QA_PORT", "7777")),
        reload=os.getenv("AGNO_QA_RELOAD", "false").lower() == "true",
    )


def create_app():
    """Cria a aplicação ASGI do AgentOS."""
    load_env()

    from agno.os import AgentOS
    from agno.os.config import AuthorizationConfig
    from fastapi import FastAPI
    import jwt

    from app.agent import create_agent
    from app.auth import router, verification_keys

    base_app = FastAPI()
    base_app.include_router(router())
    agent = create_agent()
    os_app = AgentOS(
        agents=[agent],
        db=agent.db,
        tracing=True,
        base_app=base_app,
        authorization=True,
        authorization_config=AuthorizationConfig(
            verification_keys=verification_keys(),
            algorithm="RS256",
            # Control Plane tokens use the AgentOS ID as audience; the local
            # Google exchange uses its own audience. Signature keys are issuer-specific.
            verify_audience=False,
            user_isolation=True,
            excluded_route_paths=["/auth/google"],
        ),
    ).get_app()
    # O mapeamento RBAC nativo permite rotas sem escopo; apenas a superfície
    # consumida pelo chat fica acessível para tokens Google.
    from fastapi.responses import JSONResponse
    from starlette.middleware.base import BaseHTTPMiddleware

    class ChatSurface(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            path = request.url.path.rstrip("/") or "/"
            parts = path.split("/")
            # Let AgentOS's native CORS middleware answer browser preflight requests.
            if request.method == "OPTIONS":
                return await call_next(request)
            if len(request.headers.getlist("authorization")) > 1:
                return JSONResponse({"detail": "Ambiguous authorization"}, status_code=401)
            if path not in ("/auth/google", "/health"):
                authorization = request.headers.get("authorization", "")
                if not authorization.startswith("Bearer "):
                    return JSONResponse({"detail": "Bearer token required"}, status_code=401)
                token = authorization[7:]
                # Keep dashboard metrics behind Agno's native JWT/PAT verifier;
                # local Google tokens do not get access to observability.
                metrics_route = (
                    (request.method == "GET" and path in ("/metrics", "/metrics/refresh/status"))
                    or (request.method == "POST" and path == "/metrics/refresh")
                )
                if token.startswith("agno_pat_"):
                    # Allow the native AgentOS service-account verifier and RBAC to
                    # authorize read-only Control Plane discovery and observability.
                    platform_get = request.method == "GET" and (
                        path in ("/info", "/openapi.json", "/config", "/models", "/registry",
                                 "/agents", "/metrics", "/traces", "/trace_session_stats")
                        or (len(parts) == 3 and parts[1] in ("agents", "metrics", "traces"))
                    )
                    if not (platform_get or metrics_route):
                        return JSONResponse({"detail": "Not available"}, status_code=404)
                    return await call_next(request)
                try:
                    unverified_claims = jwt.decode(
                        token,
                        options={"verify_signature": False, "verify_aud": False},
                    )
                except jwt.PyJWTError:
                    unverified_claims = None
                if unverified_claims is not None and unverified_claims.get("iss") != "kapo-google":
                    platform_get = request.method == "GET" and (
                        path in ("/info", "/openapi.json", "/config", "/models", "/registry",
                                 "/agents", "/metrics", "/traces", "/trace_session_stats")
                        or (len(parts) == 3 and parts[1] in ("agents", "metrics", "traces"))
                    )
                    if not (platform_get or metrics_route):
                        return JSONResponse({"detail": "Not available"}, status_code=404)
                    return await call_next(request)
                if not token:
                    return JSONResponse({"detail": "Bearer token required"}, status_code=401)
            allowed = (
                (request.method == "POST" and path == "/auth/google")
                or (request.method == "GET" and path == "/health")
                or (request.method == "GET" and path in ("/agents", "/sessions", "/traces"))
                or (request.method == "GET" and len(parts) == 3 and parts[1] in ("agents", "sessions", "traces"))
                or (request.method == "GET" and len(parts) == 4 and parts[1] == "sessions" and parts[3] == "runs")
                or (request.method == "POST" and len(parts) == 4 and parts[1] == "agents" and parts[3] == "runs")
                or (request.method == "DELETE" and len(parts) == 3 and parts[1] == "sessions")
            )
            if not allowed:
                return JSONResponse({"detail": "Not available"}, status_code=404)
            return await call_next(request)

    os_app.add_middleware(ChatSurface)
    # CORS must wrap our route filter as well, so browser clients can read its
    # 401/404 responses instead of reporting an opaque "Failed to fetch".
    from starlette.middleware.cors import CORSMiddleware

    cors = [middleware for middleware in os_app.user_middleware if middleware.cls is CORSMiddleware]
    os_app.user_middleware[:] = cors + [
        middleware for middleware in os_app.user_middleware if middleware.cls is not CORSMiddleware
    ]
    return os_app


app = create_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="Agente básico com Agno")
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Inicia a API para conexão com o Agno Control Plane",
    )
    parser.add_argument("prompt", nargs="*", help="Mensagem enviada ao agente")
    args = parser.parse_args()

    if args.serve:
        serve()
        return

    from app.agent import create_agent

    prompt = " ".join(args.prompt).strip() or "Olá!"
    create_agent().print_response(prompt, stream=True)


if __name__ == "__main__":
    main()
