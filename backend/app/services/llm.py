import litellm
from app.config import settings

def generate(prompt: str) -> str:
    response = litellm.completion(
        model=settings.LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        api_key=settings.LLM_API_KEY,
    )
    return response.choices[0].message.content.strip()