"""OPTIONAL: the same Sales Insights brain, written with LangChain.

    pip install langchain-openai
    python langchain_agent.py "What was net revenue by month?"

Same guard, same gold tables, same answer. Only the model call changes: LangChain's ChatOpenAI talks to
OpenRouter, NVIDIA, Ollama or Azure because they all speak the OpenAI API.
"""
import re
import sys

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

import agent_core
import llm


def make_chat():
    s = llm.settings()
    if s.provider == "mock":
        return llm.chat                                     # nothing to wrap in mock mode
    model = ChatOpenAI(model=s.model, base_url=s.base_url, api_key=s.api_key, max_retries=4,
                       use_responses_api=(s.api == "responses"))
    chain = ChatPromptTemplate.from_messages([("system", "{system}"), ("human", "{user}")]) | model | StrOutputParser()

    def chat(system: str, user: str, role: str = "sql") -> str:
        text = chain.invoke({"system": system, "user": user})
        return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    return chat


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "What was total net revenue?"
    print(agent_core.answer(question, chat=make_chat()))
