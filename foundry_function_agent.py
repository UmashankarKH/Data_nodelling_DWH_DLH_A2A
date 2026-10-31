"""FOUNDRY DEMO 1 - a Microsoft Foundry agent that uses a FUNCTION TOOL to query the gold layer.

Everything "thinking" runs in Foundry (the model deployment and the agent). The one thing that stays in
your code is the tool itself, run_sql, because the agent asks YOUR app to run it and return the result.

Setup (once):
    pip install -r requirements-extras.txt
    az login
    .env needs:  FOUNDRY_PROJECT_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>
                 FOUNDRY_MODEL_DEPLOYMENT_NAME=<your deployment name>
Run:
    python foundry_function_agent.py "What was net revenue by month?"
"""
import json
import os
import sys

from dotenv import load_dotenv

import agent_core

load_dotenv()
AGENT_NAME = "freshkart-sales-insights"

INSTRUCTIONS = f"""You are the FreshKart Sales Insights agent.
Answer revenue questions by calling the run_sql tool. Never guess numbers: always call the tool first.
Write ONE read-only SELECT per call. {agent_core.DIALECTS[agent_core.BACKEND_NAME]}
{agent_core.SCHEMA_DOC}
{agent_core.RULES}
After you get the rows, answer in at most 3 short sentences and say that revenue means net revenue."""


def execute(call) -> str:
    """Runs when the Foundry agent asks us to call run_sql. Same guard as the A2A agent."""
    try:
        sql = agent_core.check_sql(json.loads(call.arguments)["sql"])
        print(f"  [tool] run_sql: {sql}")
        cols, rows = agent_core.backend().run(sql)
        return json.dumps({"columns": list(cols), "rows": [list(r) for r in rows[:50]]}, default=str)
    except Exception as e:                      # give the error back so the agent can fix its SQL
        return json.dumps({"error": str(e)})


def converse(openai_client, agent_ref: dict, question: str, max_rounds: int = 5) -> str:
    """The function-calling loop: ask, run any requested tools, hand results back, repeat."""
    response = openai_client.responses.create(input=question, extra_body=agent_ref)
    for _ in range(max_rounds):
        calls = [item for item in response.output if item.type == "function_call"]
        if not calls:
            break
        outputs = [{"type": "function_call_output", "call_id": c.call_id, "output": execute(c)} for c in calls]
        response = openai_client.responses.create(input=outputs, previous_response_id=response.id, extra_body=agent_ref)
    return response.output_text


def main(question: str) -> None:
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import FunctionTool, PromptAgentDefinition
    from azure.identity import DefaultAzureCredential

    run_sql = FunctionTool(
        name="run_sql",
        description="Run ONE read-only SQL SELECT on the FreshKart gold tables. Returns columns and rows.",
        parameters={"type": "object",
                    "properties": {"sql": {"type": "string", "description": "A single SELECT statement."}},
                    "required": ["sql"], "additionalProperties": False},
        strict=True,
    )
    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"], credential=credential) as project,
        project.get_openai_client() as openai_client,
    ):
        agent = project.agents.create_version(
            agent_name=AGENT_NAME,
            definition=PromptAgentDefinition(model=os.environ["FOUNDRY_MODEL_DEPLOYMENT_NAME"],
                                             instructions=INSTRUCTIONS, tools=[run_sql]),
        )
        print(f"Foundry agent created: {agent.name} (version {agent.version})")
        try:
            ref = {"agent_reference": {"name": agent.name, "type": "agent_reference"}}
            print(converse(openai_client, ref, question))
        finally:
            project.agents.delete_version(agent_name=agent.name, agent_version=agent.version)


if __name__ == "__main__":
    main(" ".join(sys.argv[1:]) or "What was net revenue by month?")
