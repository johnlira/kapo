"""Assistente de atendimento funcional construído com Agno."""

import os
from pathlib import Path

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
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
    instructions = (Path(__file__).resolve().parent / "agent_instructions.md").read_text(
        encoding="utf-8"
    )
    db_file = os.getenv("AGNO_QA_DB_FILE", ".agno/sessions.db")
    database = SqliteDb(db_file=db_file)

    return Agent(
        name="Kapo",
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
        tool_call_limit=int(os.getenv("AGNO_QA_TOOL_CALL_LIMIT", "8")),
        retries=0,
        instructions=instructions,
        db=database,
        add_history_to_context=True,
        num_history_runs=int(os.getenv("AGNO_QA_NUM_HISTORY_RUNS", "3")),
        markdown=True,
    )
