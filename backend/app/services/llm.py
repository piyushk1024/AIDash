import litellm
from app.config import settings

async def generate(prompt: str) -> str:
    response = await litellm.acompletion(
        model=settings.LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        api_key=settings.LLM_API_KEY,
    )
    return response.choices[0].message.content.strip()

async def generate_with_tools(messages: list[dict], tools: list[dict]):
    response = await litellm.acompletion(
        model=settings.LLM_MODEL,
        messages=messages,
        tools=tools,
        tool_choice="auto",
        api_key=settings.LLM_API_KEY,
    )
    return response.choices[0].message