"""A second agent (the 'caller') asking the Sales Insights agent a question over A2A.

Run:  python a2a_client.py "What was net revenue by month?"
"""
import asyncio
import os
import sys
import uuid

import httpx

from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import get_message_text
from a2a.types import Message, Part, Role, SendMessageRequest

BASE_URL = os.getenv("AGENT_URL", "http://127.0.0.1:9999")


async def ask(question: str) -> None:
    async with httpx.AsyncClient() as http:
        card = await A2ACardResolver(http, BASE_URL).get_agent_card()      # discovery
    print(f"Found agent: {card.name}  (skills: {[s.id for s in card.skills]})\n")

    # the agent makes 1-2 model calls per question, so allow far more than httpx's 5 s default
    async with httpx.AsyncClient(timeout=180) as http:
        client = await create_client(card, client_config=ClientConfig(streaming=False, httpx_client=http))
        try:
            msg = Message(role=Role.ROLE_USER, message_id=str(uuid.uuid4()), parts=[Part(text=question)])
            async for event in client.send_message(SendMessageRequest(message=msg)):
                if event.HasField("message"):
                    print(get_message_text(event.message))
        finally:
            await client.close()


if __name__ == "__main__":
    asyncio.run(ask(" ".join(sys.argv[1:]) or "What was net revenue by month?"))
