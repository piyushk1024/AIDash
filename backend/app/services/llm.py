import re
import time
import litellm
from opentelemetry.trace import StatusCode
from app.config import settings
from app.services.telemetry import get_tracer


class LLMUnavailableError(Exception):
    """Raised when the LLM provider returns a 503 service-unavailable response,
    hits a rate limit, or when a prior rate limit is still in its cooldown window.

    Carry the provider name so route handlers can attribute the error clearly
    in the response body rather than returning a generic 500.
    """
    def __init__(self, provider: str):
        self.provider = provider
        super().__init__(f"LLM provider '{provider}' is currently unavailable.")


_tracer = get_tracer("dasher.llm")

_PROVIDER = settings.LLM_MODEL.split("/", 1)[0] if "/" in settings.LLM_MODEL else settings.LLM_MODEL

_RETRY_DELAY_PATTERN = re.compile(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"')

# Process-wide circuit breaker. Set on any rate-limit error; every call site
# (planner, semantics, healer, agent, NL builder, insights) goes through
# generate()/generate_with_tools(), so this protects all of them at once.
# Not a per-request or per-user cooldown — deliberately global, since a
# rate limit is on the whole API key, not scoped to whoever triggered it.
_rate_limit_cooldown_until: float = 0.0


def _check_cooldown() -> None:
    if time.monotonic() < _rate_limit_cooldown_until:
        raise LLMUnavailableError(_PROVIDER)


def _extract_retry_delay_seconds(e: Exception) -> float | None:
    # Provider error bodies (at least Gemini's) embed a retryDelay hint in
    # their JSON error text, e.g. "retryDelay": "2s". litellm surfaces the
    # raw body in str(e), so pull it out when present rather than always
    # falling back to our own fixed guess.
    match = _RETRY_DELAY_PATTERN.search(str(e))
    return float(match.group(1)) if match else None


def _start_cooldown(e: Exception) -> None:
    global _rate_limit_cooldown_until
    delay = _extract_retry_delay_seconds(e) or settings.LLM_RATE_LIMIT_COOLDOWN_SECONDS
    _rate_limit_cooldown_until = time.monotonic() + delay

def is_llm_in_cooldown() -> bool:
    return time.monotonic() < _rate_limit_cooldown_until


async def generate(prompt: str, stage: str = "unknown") -> str:
    _check_cooldown()

    with _tracer.start_as_current_span("llm.generate") as span:
        span.set_attribute("stage", stage)
        span.set_attribute("model", settings.LLM_MODEL)
        t0 = time.perf_counter()

        try:
            response = await litellm.acompletion(
                model=settings.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                api_key=settings.LLM_API_KEY,
            )
        except litellm.RateLimitError as e:
            _start_cooldown(e)
            span.set_status(StatusCode.ERROR, description=str(e))
            span.record_exception(e)
            raise LLMUnavailableError(_PROVIDER) from e
        except litellm.ServiceUnavailableError as e:
            span.set_status(StatusCode.ERROR, description=str(e))
            span.record_exception(e)
            raise LLMUnavailableError(_PROVIDER) from e
        except Exception as e:
            span.set_status(StatusCode.ERROR, description=str(e))
            span.record_exception(e)
            raise
        finally:
            span.set_attribute("latency_ms", round((time.perf_counter() - t0) * 1000, 2))

        usage = response.usage
        span.set_attribute("model", response.model or settings.LLM_MODEL)
        span.set_attribute("input_tokens", getattr(usage, "prompt_tokens", 0) or 0)
        span.set_attribute("output_tokens", getattr(usage, "completion_tokens", 0) or 0)
        # if stage == "planner":
            # print(f"[PLANNER PROMPT]\n{prompt}\n")
            # print(f"[PLANNER RESPONSE]\n{response.choices[0].message.content.strip()}\n")

        return response.choices[0].message.content.strip()


async def generate_with_tools(messages: list[dict], tools: list[dict], stage: str = "unknown"):
    _check_cooldown()

    with _tracer.start_as_current_span("llm.generate_with_tools") as span:
        span.set_attribute("stage", stage)
        span.set_attribute("model", settings.LLM_MODEL)
        t0 = time.perf_counter()

        try:
            response = await litellm.acompletion(
                model=settings.LLM_MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                api_key=settings.LLM_API_KEY,
            )
        except litellm.RateLimitError as e:
            _start_cooldown(e)
            span.set_status(StatusCode.ERROR, description=str(e))
            span.record_exception(e)
            raise LLMUnavailableError(_PROVIDER) from e
        except litellm.ServiceUnavailableError as e:
            span.set_status(StatusCode.ERROR, description=str(e))
            span.record_exception(e)
            raise LLMUnavailableError(_PROVIDER) from e
        except Exception as e:
            span.set_status(StatusCode.ERROR, description=str(e))
            span.record_exception(e)
            raise
        finally:
            span.set_attribute("latency_ms", round((time.perf_counter() - t0) * 1000, 2))

        usage = response.usage
        span.set_attribute("model", response.model or settings.LLM_MODEL)
        span.set_attribute("input_tokens", getattr(usage, "prompt_tokens", 0) or 0)
        span.set_attribute("output_tokens", getattr(usage, "completion_tokens", 0) or 0)

        return response.choices[0].message