"""Garante que pedidos alheios ao produto não cheguem ao agente principal."""

import unittest
from unittest.mock import AsyncMock, patch

from agno.exceptions import CheckTrigger, InputCheckError
from agno.agent import Agent
from agno.models.response import ModelResponse
from agno.run.agent import RunInput

from app.scope import OUT_OF_SCOPE_REPLY, enforce_functional_scope


class FunctionalScopeTests(unittest.IsolatedAsyncioTestCase):
    async def test_sports_request_is_rejected_before_main_agent(self):
        with patch("app.scope.OpenAIResponses.ainvoke", new_callable=AsyncMock,
                   return_value=ModelResponse(content="OUT")) as classify:
            with self.assertRaises(InputCheckError) as caught:
                await enforce_functional_scope(RunInput("escolhe ai entre flamengo e vasco por favor"))
        self.assertEqual(caught.exception.check_trigger, CheckTrigger.OFF_TOPIC)
        self.assertEqual(str(caught.exception), OUT_OF_SCOPE_REPLY)
        self.assertIn("flamengo e vasco", classify.call_args.kwargs["messages"][1].content)

    async def test_followup_about_product_is_allowed(self):
        with patch("app.scope.OpenAIResponses.ainvoke", new_callable=AsyncMock,
                   return_value=ModelResponse(content="IN")):
            await enforce_functional_scope(RunInput("e se esse campo não for salvo?"))

    async def test_unknown_classifier_output_fails_closed(self):
        with patch("app.scope.OpenAIResponses.ainvoke", new_callable=AsyncMock,
                   return_value=ModelResponse(content="Talvez")):
            with self.assertRaises(InputCheckError):
                await enforce_functional_scope(RunInput("uma dúvida qualquer"))

    async def test_agent_stream_blocks_before_main_model_and_shows_scope_reply(self):
        import tempfile

        from agno.db.sqlite import SqliteDb
        from agno.models.openai import OpenAIResponses
        from agno.run.agent import RunErrorEvent

        with tempfile.TemporaryDirectory() as directory:
            agent = Agent(
                model=OpenAIResponses(), db=SqliteDb(db_file=f"{directory}/sessions.db"),
                pre_hooks=[enforce_functional_scope],
            )
            with patch("app.scope.OpenAIResponses.ainvoke", new_callable=AsyncMock,
                       return_value=ModelResponse(content="OUT")) as invoke:
                events = [event async for event in agent.arun(
                    "escolhe entre Flamengo e Vasco", stream=True, stream_events=True,
                )]
        self.assertEqual(invoke.await_count, 1)
        errors = [event for event in events if isinstance(event, RunErrorEvent)]
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].content, OUT_OF_SCOPE_REPLY)
        self.assertEqual(errors[0].error_id, CheckTrigger.OFF_TOPIC.value)


if __name__ == "__main__":
    unittest.main()
