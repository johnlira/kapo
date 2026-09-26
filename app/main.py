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
        host="0.0.0.0",
        port=int(os.getenv("AGNO_QA_PORT", "7777")),
        reload=True,
    )


def create_app():
    """Cria a aplicação ASGI do AgentOS."""
    load_env()

    from agno.os import AgentOS

    from app.agent import create_agent

    return AgentOS(agents=[create_agent()]).get_app()


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
