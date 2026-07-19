"""
agents/response_agent.py
--------------------------
The Response Generator Agent: turns (query, intent, retrieved_data)
into a natural-language, customer-facing reply.

Why this file exists:
- Third and final agent in the pipeline (Intent -> Database -> Response).
  It never talks to the database itself and never decides intent —
  it only writes prose from data it's handed.
- Uses a simple `prompt | llm | StrOutputParser` chain instead of
  structured output, since the desired output here IS free text.
- Runs at a higher temperature than the Intent Agent (0.4 vs 0) since
  natural variation in phrasing is desirable in customer-facing
  replies, unlike classification which should be deterministic.
"""

import json
import os

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI

from prompts.response_prompt import response_prompt_template

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash")


class ResponseAgentError(Exception):
    """Raised when the response agent fails to generate a reply."""


class ResponseAgent:
    """
    Thin wrapper around a LangChain chain that writes a customer-facing
    reply from a query, an intent, and previously retrieved data.
    """

    def __init__(self) -> None:
        if not GOOGLE_API_KEY:
            raise ResponseAgentError(
                "GOOGLE_API_KEY is not set. Add it to your .env file."
            )

        llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL_NAME,
            google_api_key=GOOGLE_API_KEY,
            temperature=0.4,
        )

        self._chain = response_prompt_template | llm | StrOutputParser()

    def generate_response(self, query: str, intent: str, retrieved_data) -> str:
        """
        Generate a customer-facing reply.

        Args:
            query: the customer's original message.
            intent: the intent label detected for this query.
            retrieved_data: a dict/list (already fetched from the
                Database Agent) or a JSON string. Will be serialized
                to a JSON string before being sent to the LLM.

        Raises:
            ResponseAgentError: if the LLM call fails.
        """
        if not isinstance(retrieved_data, str):
            retrieved_data = json.dumps(retrieved_data)

        try:
            result = self._chain.invoke(
                {
                    "query": query,
                    "intent": intent,
                    "retrieved_data": retrieved_data,
                }
            )
        except Exception as exc:  # noqa: BLE001 - surfaced as a domain error
            raise ResponseAgentError(f"Failed to generate response: {exc}") from exc

        return result.strip()


# Singleton instance reused across requests, mirroring the intent_agent pattern.
response_agent = ResponseAgent()