"""Assistente de atendimento funcional construído com Agno."""

import os
from pathlib import Path

from agno.agent import Agent
from agno.models.openai import OpenAIResponses

from app.sources import (
    catalog_repositories,
    project_inventory,
    read_repository_paths,
    search_functionality_catalog,
    search_repository_files,
)


def create_agent() -> Agent:
    """Cria o assistente de atendimento funcional do projeto."""
    instructions = (Path(__file__).resolve().parent.parent / ".agents/AGENTS.md").read_text(
        encoding="utf-8"
    )
    return Agent(
        name="Atendimento Funcional QuarkClinic",
        model=OpenAIResponses(
            id=os.getenv("AGNO_QA_MODEL", "gpt-5.4-mini"),
            reasoning_effort=os.getenv("AGNO_QA_REASONING_EFFORT", "low"),
        ),
        tools=[
            catalog_repositories,
            project_inventory,
            read_repository_paths,
            search_functionality_catalog,
            search_repository_files,
        ],
        instructions=instructions,
        markdown=True,
    )
