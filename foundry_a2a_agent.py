"""FOUNDRY DEMO 2 - a Foundry agent that calls OUR A2A agent (running in Azure) through Foundry's A2A tool.

The story from the morning, finished: a "CEO assistant" agent lives in Foundry. When asked about sales it
does not touch any data. It calls the FreshKart Sales Insights agent over the A2A protocol, and that agent
reads only the gold layer.

Setup (once):
    pip install -r requirements-extras.txt
    az login
    Deploy the A2A agent (see FOUNDRY_DEMO.md), then create an A2A connection in your Foundry project
    (Tools > Connect tool > Custom > Agent2Agent) pointing at https://<your-app>.azurecontainerapps.io
    .env needs:  FOUNDRY_PROJECT_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>
                 FOUNDRY_MODEL_DEPLOYMENT_NAME=<your deployment name>
                 A2A_CONNECTION_NAME=<the connection name you created>
Run:
    python foundry_a2a_agent.py "What was net revenue by month?"
    python foundry_a2a_agent.py --keep "Top 5 products?"     keeps the agent so you can show it in the portal
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv()
AGENT_NAME = "freshkart-ceo-assistant"
INSTRUCTIONS = ("You are the CEO's assistant at FreshKart. For ANY question about sales or revenue, ask the Sales "
                "Insights agent through the A2A tool and report its numbers. Do not invent numbers. "
                "Say that revenue means net revenue after discounts and returns, with cancelled orders excluded.")


def main(question: str, keep: bool) -> None:
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import A2AProtocolVersion, A2ATool, PromptAgentDefinition
    from azure.identity import DefaultAzureCredential

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"], credential=credential) as project,
        project.get_openai_client() as openai_client,
    ):
        connection = project.connections.get(os.environ["A2A_CONNECTION_NAME"])
        tool = A2ATool(a2a_version=A2AProtocolVersion.V1_0, project_connection_id=connection.id)
        agent = project.agents.create_version(
            agent_name=AGENT_NAME,
            definition=PromptAgentDefinition(model=os.environ["FOUNDRY_MODEL_DEPLOYMENT_NAME"],
                                             instructions=INSTRUCTIONS, tools=[tool]),
        )
        print(f"Foundry agent created: {agent.name} (version {agent.version})")
        try:
            response = openai_client.responses.create(
                tool_choice="required", input=question,
                extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
            )
            print(response.output_text)
        finally:
            if keep:
                print(f"Kept agent {agent.name} so you can open it in the Foundry portal.")
            else:
                project.agents.delete_version(agent_name=agent.name, agent_version=agent.version)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--keep"]
    main(" ".join(args) or "What was net revenue by month?", keep="--keep" in sys.argv)
