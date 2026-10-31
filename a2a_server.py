"""LAB 5 - Expose the Sales Insights agent over the A2A protocol.

Run:  python a2a_server.py          (agent card appears at http://127.0.0.1:9999/.well-known/agent-card.json)

Written for a2a-sdk 1.x (tested with 1.3.0). Pin it:  pip install "a2a-sdk[http-server]>=1.2,<2"
"""
import asyncio
import os

import uvicorn
from starlette.applications import Starlette

import agent_core
from a2a.helpers import new_text_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "9999"))
PUBLIC_URL = os.getenv("PUBLIC_URL", f"http://{HOST}:{PORT}").rstrip("/")   # the address OTHERS use (set it in the cloud)


class InsightsExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        question = context.get_user_input()
        text = await asyncio.to_thread(agent_core.answer, question)    # SQL + LLM calls are blocking
        await event_queue.enqueue_event(new_text_message(text))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("nothing to cancel")


skill = AgentSkill(
    id="sales_insights",
    name="Sales insights",
    description="Answers revenue questions (by month, product, city, channel) from the governed gold layer. "
                "Revenue means net revenue after discounts and returns, cancelled orders excluded.",
    tags=["sales", "revenue", "analytics"],
    examples=["What was net revenue by month?", "Top 5 products by revenue?", "Web vs store share of revenue?"],
)

agent_card = AgentCard(
    name="FreshKart Sales Insights Agent",
    description="Read-only analytics agent over the FreshKart gold star schema.",
    version="1.0.0",
    supported_interfaces=[AgentInterface(protocol_binding="JSONRPC", protocol_version="1.0",
                                         url=f"{PUBLIC_URL}/")],
    capabilities=AgentCapabilities(streaming=False, push_notifications=False),
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    skills=[skill],
)

handler = DefaultRequestHandler(agent_executor=InsightsExecutor(), task_store=InMemoryTaskStore(),
                                agent_card=agent_card)

app = Starlette(routes=[
    *create_agent_card_routes(agent_card),
    *create_jsonrpc_routes(handler, rpc_url="/"),
])

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
