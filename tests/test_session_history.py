import os
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openai import OpenAIResponses
from agno.models.response import ModelResponse

from app.agent import create_agent


class InspectingModel(OpenAIResponses):
    """Deterministic model that records the exact context passed by Agno."""

    received_messages: ClassVar[list[list[dict]]] = []

    def response(self, messages, **kwargs):
        self.received_messages.append([message.to_dict() for message in messages])
        latest = next(
            message.content for message in reversed(messages) if message.role == "user"
        )
        return ModelResponse(content=f"Resposta a: {latest}")


def make_agent(db_path: Path, model: InspectingModel, limit: int = 3) -> Agent:
    return Agent(
        model=model,
        db=SqliteDb(db_file=str(db_path)),
        add_history_to_context=True,
        num_history_runs=limit,
        telemetry=False,
    )


def user_texts(model: InspectingModel) -> list[str]:
    return [
        str(message.get("content"))
        for message in model.received_messages[-1]
        if message.get("role") == "user"
    ]


class SessionHistoryTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "sessions.db"
        self.agents = []
        InspectingModel.received_messages.clear()

    def tearDown(self):
        for bot in self.agents:
            bot.db.db_engine.dispose()
        self.temp_dir.cleanup()

    def make_agent(self, model, limit=3):
        bot = make_agent(self.db_path, model, limit)
        self.agents.append(bot)
        return bot

    def test_session_persists_after_agent_recreation(self):
        first_model = InspectingModel()
        self.make_agent(first_model).run(
            "Estou configurando o saldo pré-pago do paciente.",
            session_id="continuity",
            user_id="person-1",
        )

        second_model = InspectingModel()
        self.make_agent(second_model).run(
            "Qual campo eu preencho agora?",
            session_id="continuity",
            user_id="person-1",
        )

        self.assertTrue(self.db_path.exists())
        self.assertIn(
            "Estou configurando o saldo pré-pago do paciente.",
            user_texts(second_model),
        )

    def test_same_session_history_resolves_followup(self):
        model = InspectingModel()
        bot = self.make_agent(model)
        bot.run(
            "Estou configurando o saldo pré-pago do paciente.",
            session_id="same-chat",
        )
        bot.run("Qual campo eu preencho agora?", session_id="same-chat")

        self.assertEqual(
            user_texts(model),
            [
                "Estou configurando o saldo pré-pago do paciente.",
                "Qual campo eu preencho agora?",
            ],
        )

    def test_history_is_isolated_between_sessions(self):
        model_a = InspectingModel()
        self.make_agent(model_a).run("segredo-A", session_id="session-A")
        model_b = InspectingModel()
        self.make_agent(model_b).run("pergunta", session_id="session-B")

        self.assertNotIn("segredo-A", user_texts(model_b))

    def test_new_chat_starts_with_separate_context(self):
        model_a = InspectingModel()
        self.make_agent(model_a).run(
            "contexto-chat-antigo", session_id="old-chat"
        )
        model_new = InspectingModel()
        self.make_agent(model_new).run(
            "primeira pergunta", session_id="new-chat"
        )

        self.assertNotIn("contexto-chat-antigo", user_texts(model_new))

    def test_history_run_limit(self):
        model = InspectingModel()
        bot = self.make_agent(model, limit=2)
        for index in range(4):
            bot.run(f"turno-{index}", session_id="limited")

        self.assertEqual(user_texts(model), ["turno-1", "turno-2", "turno-3"])

    def test_history_run_count_is_configurable_and_defaults_to_three(self):
        with patch.dict(os.environ, {"AGNO_QA_DB_FILE": str(self.db_path)}):
            os.environ.pop("AGNO_QA_NUM_HISTORY_RUNS", None)
            default_agent = create_agent()
            self.agents.append(default_agent)
            self.assertTrue(default_agent.add_history_to_context)
            self.assertEqual(default_agent.num_history_runs, 3)

            os.environ["AGNO_QA_NUM_HISTORY_RUNS"] = "6"
            configured_agent = create_agent()
            self.agents.append(configured_agent)
            self.assertEqual(configured_agent.num_history_runs, 6)


if __name__ == "__main__":
    unittest.main()
