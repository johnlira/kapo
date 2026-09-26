"""Ponto de entrada simples para conversar com o agente."""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Agente básico com Agno")
    parser.add_argument("prompt", nargs="*", help="Mensagem enviada ao agente")
    args = parser.parse_args()

    from app.agent import create_agent

    prompt = " ".join(args.prompt).strip() or "Olá!"
    create_agent().print_response(prompt, stream=True)


if __name__ == "__main__":
    main()
