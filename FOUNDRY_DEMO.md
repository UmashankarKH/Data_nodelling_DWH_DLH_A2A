# Trainer runbook: the whole demo on Microsoft Foundry

Not for learners. Learners use SETUP.md with OpenRouter or NVIDIA. This is your cloud showcase.

## What the demo shows

| Piece | Runs in | Shown by |
| --- | --- | --- |
| The LLM | A model deployment in your Foundry project | Foundry portal, then every script |
| The Sales Insights A2A agent (the one from Lab 5) | Azure Container Apps | `curl` on its agent card, `a2a_client.py` |
| The CEO assistant agent | Foundry Agent Service | `foundry_a2a_agent.py` |
| The A2A link between them | Foundry's A2A tool and a project connection | Portal: Tools, then the connection |
| A second Foundry agent with a function tool | Foundry Agent Service | `foundry_function_agent.py` |

The story lands like this: the CEO assistant in Foundry knows nothing about sales data. It asks the FreshKart Sales Insights agent over A2A, and that agent can only see the gold layer. Same A2A protocol the learners just built, now deployed in the cloud.

## Do these tonight (about 60 to 90 minutes)

### A. Foundry project and model

1. In the Foundry portal, create a project and deploy a chat model. Microsoft's A2A docs use `gpt-4.1-mini` and `gpt-5-mini` as examples; use whichever your subscription offers. Note the **deployment name**.
2. Copy the **project endpoint**. It looks like `https://<resource>.services.ai.azure.com/api/projects/<project>`.
3. Roles: you need *Foundry User* on the project to create and test agents, and *Foundry Project Manager* to create the A2A connection.
4. On your laptop: `az login`, then `pip install -r requirements-extras.txt`.
5. Add to `.env`:

```
FOUNDRY_PROJECT_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>
FOUNDRY_MODEL_DEPLOYMENT_NAME=<deployment name>
```

### B. Deploy the A2A agent to Azure Container Apps

The `Dockerfile` builds the gold layer inside the image, so the container needs nothing from your laptop. Run from the `fde_lab` folder (bash shown; in PowerShell set `$FQDN` the same way):

```
az group create -n rg-fde-demo -l <region>

az containerapp up -n freshkart-insights -g rg-fde-demo --source . \
  --ingress external --target-port 9999 \
  --env-vars LLM_PROVIDER=azure \
             AZURE_OPENAI_BASE_URL=https://<resource>.openai.azure.com/openai/v1/ \
             AZURE_OPENAI_DEPLOYMENT=<deployment name>

az containerapp secret set -n freshkart-insights -g rg-fde-demo --secrets llm-key=<your key>

FQDN=$(az containerapp show -n freshkart-insights -g rg-fde-demo \
       --query properties.configuration.ingress.fqdn -o tsv)

az containerapp update -n freshkart-insights -g rg-fde-demo \
  --set-env-vars AZURE_OPENAI_API_KEY=secretref:llm-key PUBLIC_URL=https://$FQDN

curl https://$FQDN/.well-known/agent-card.json
```

The card must show your `https://...azurecontainerapps.io/` address as its URL. That is what `PUBLIC_URL` is for. Then try it from your laptop:

```
AGENT_URL=https://$FQDN python a2a_client.py "What was net revenue by month?"
```

If that works, the A2A agent is live in Azure. The Azure model URL uses the v1 route, needs no `api-version`, and the lab calls it through the Responses API, which Microsoft recommends for Azure OpenAI models.

### C. Connect the agent to Foundry

In the Foundry portal: **Tools**, **Connect tool**, **Custom** tab, **Agent2Agent (A2A)**, **Create**. Name it `freshkart-a2a`, endpoint `https://<your FQDN>`, authentication **None** (demo only: anyone with the URL can call the agent, so delete the app after class or add key authentication). Command line alternative:

```
azd ai connection create freshkart-a2a --kind remote-a2a --target https://$FQDN --auth-type none
```

Add `A2A_CONNECTION_NAME=freshkart-a2a` to `.env`.

### D. Rehearse both scripts

```
python foundry_a2a_agent.py "What was net revenue by month?"
python foundry_function_agent.py "Top 5 products by net revenue?"
```

Expected: the first prints the Foundry agent's answer using the monthly numbers from the Sales Insights agent (they add up to the 902,930 total from Lab 4). The second prints each `[tool] run_sql: ...` line, then the answer.

## In class (15 minutes)

| Min | Do | Say |
| --- | --- | --- |
| 0 to 3 | Foundry portal: the project, the model deployment, the Tools page with the A2A connection | "Model, agents, tools: all one place. This is what a client's team would use." |
| 3 to 6 | `curl` the Container App agent card in the terminal | "Same card you opened on your laptop. Now it is a public address in Azure." |
| 6 to 10 | `python foundry_a2a_agent.py --keep "What was net revenue by month?"`, then open the agent in the portal | "This agent has no data. It asks ours over A2A." |
| 10 to 13 | `python foundry_function_agent.py "Top 5 products?"` | "Different pattern: the agent asks my code to run a tool. Watch the SQL guard." |
| 13 to 15 | Recap on the board | "What changed from your laptop: model host, agent host, location. What stayed: gold layer, rules, guard, Agent Card." |

## After class

```
az group delete -n rg-fde-demo --yes --no-wait
```

Delete the A2A connection in the portal if you no longer need it, and remove the model deployment if it bills.

## What was tested and what was not

Tested here: the logic of both Foundry scripts against a fake Foundry client (the tool loop runs and returns results), that the SDK objects for the function tool and the A2A tool build correctly, the agent card with `PUBLIC_URL`, the Azure-style model call with a stand-in server, and every lab from a clean folder.

Not tested here, because the test workspace cannot reach Azure and has no Docker engine running: the Container Apps deployment, the Docker image build, the Foundry connection, and the two scripts against real Foundry. Expect small differences in portal wording. The A2A tool used (`A2ATool` with protocol 1.0) and the function tool follow Microsoft's current documentation, and our agent speaks A2A 1.0 over JSON-RPC, which the A2A tool expects.

If the Foundry A2A call fails in class, fall back in this order: run `a2a_client.py` against the Container App directly (still shows A2A running in Azure), then run `foundry_function_agent.py`, then the Foundry portal playground with the model.
