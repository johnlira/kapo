"""Agente mínimo construído com Agno."""

from agno.agent import Agent
from agno.models.openai import OpenAIChat


def create_agent() -> Agent:
    """Cria um agente básico com o modelo padrão do projeto."""
    return Agent(
        name="Agno QA",
        model=OpenAIChat(id="gpt-4o-mini"),
        markdown=True,
    )
