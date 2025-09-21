from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from src.config import settings

llm = ChatOpenAI(
    model_name="gpt-4o-mini",   # or "gpt-4-turbo" | "gpt-4o-latest"
    temperature=0,               # deterministic code output
    api_key=settings.OPENAI_API_KEY 
)

def generate_response(text, coherence, trend=None):
    prompt = f"""
You are a supportive breath-aware assistant.

Coherence score: {coherence}
{f"Trend: {trend}" if trend else ""}

Generate an emotionally-aware, lightweight response as if you're a gentle coach. 
If the user's breath rate has been rising for 3 check-ins, suggest a more proactive step like a guided reset or more frequent check-ins.
"""

    messages = [
        SystemMessage(content=prompt.strip()),
        HumanMessage(content=text.strip())
    ]
    response = llm.invoke(messages)
    # print(response.content)
    return response.content
