"""
agents/intent_agent.py
------------------------
All LangChain logic for the Intent Detection Agent lives here.

Why this file exists:
- Isolates the LLM client setup + invocation logic from the FastAPI
  layer (app.py) so the API layer stays thin and the agent logic is
  independently testable/reusable.
- Uses `with_structured_output()` so Gemini's response is forced into
  our `IntentResult` Pydantic schema — no manual JSON parsing, no
  regex, no risk of the model returning free-form text.
"""

import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from prompts.intent_prompt import intent_prompt_template
from schemas import IntentResult

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash")


class IntentAgentError(Exception):
    """Raised when the intent agent fails to produce a classification."""


class IntentAgent:
    """
    Thin wrapper around a LangChain chain that classifies a customer
    query into one of the predefined IntentLabel values.
    """

    def __init__(self) -> None:
        if not GOOGLE_API_KEY:
            raise IntentAgentError(
                "GOOGLE_API_KEY is not set. Add it to your .env file."
            )

        llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL_NAME,
            google_api_key=GOOGLE_API_KEY,
            temperature=0,
        )

        # Force the LLM's output to conform to the IntentResult schema.
        structured_llm = llm.with_structured_output(IntentResult)

        # Prompt -> structured LLM call, chained with LCEL's `|` operator.
        self._chain = intent_prompt_template | structured_llm

    def detect_intent(self, query: str) -> IntentResult:
        """
        Classify a single customer query.

        Raises:
            IntentAgentError: if the LLM call fails or returns an
                unparseable/unexpected result.
        """
        try:
            result = self._chain.invoke({"query": query})
        except Exception as exc:  # noqa: BLE001 - surfaced as a domain error
            raise IntentAgentError(f"Failed to classify query: {exc}") from exc

        if not isinstance(result, IntentResult):
            raise IntentAgentError(
                f"Unexpected response type from LLM: {type(result)}"
            )

        return result


# Singleton instance reused across requests so the LLM client and chain
# are built once at startup, not on every API call.
intent_agent = IntentAgent()
