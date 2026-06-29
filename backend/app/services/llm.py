import time
import litellm
from opentelemetry.trace import StatusCode
from app.config import settings
from app.services.telemetry import get_tracer


class LLMUnavailableError(Exception):
    """Raised when the LLM provider returns a 503 service-unavailable response.

    Carry the provider name so route handlers can attribute the error clearly
    in the response body rather than returning a generic 500.
    """
    def __init__(self, provider: str):
        self.provider = provider
        super().__init__(f"LLM provider '{provider}' is currently unavailable.")


# Module-level tracer — resolved against the global provider registered by
# setup_telemetry(). Safe to create here even though setup_telemetry() hasn't
# run yet: OTel returns a ProxyTracer that upgrades itself once the provider
# is registered.
_tracer = get_tracer("dasher.llm")


async def generate(prompt: str, stage: str = "unknown") -> str:
    with _tracer.start_as_current_span("llm.generate") as span:
        span.set_attribute("stage", stage)
        # Set model from settings now; overwrite with response.model on success
        # so any LiteLLM routing fallback is reflected accurately.
        span.set_attribute("model", settings.LLM_MODEL)
        t0 = time.perf_counter()

        try:
            response = await litellm.acompletion(
                model=settings.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                api_key=settings.LLM_API_KEY,
            )
        except litellm.ServiceUnavailableError as e:
            # 503 from the provider — record on span and raise a typed error
            # so route handlers can surface a clear message to the frontend.
            span.set_status(StatusCode.ERROR, description=str(e))
            span.record_exception(e)
            raise LLMUnavailableError("gemini") from e
        except Exception as e:
            span.set_status(StatusCode.ERROR, description=str(e))
            span.record_exception(e)
            raise
        finally:
            # finally runs on both success and exception paths, so latency_ms
            # is recorded even for failed calls. Token/model attributes below
            # are only reached on the success path.
            span.set_attribute("latency_ms", round((time.perf_counter() - t0) * 1000, 2))

        usage = response.usage
        span.set_attribute("model", response.model or settings.LLM_MODEL)
        span.set_attribute("input_tokens", getattr(usage, "prompt_tokens", 0) or 0)
        span.set_attribute("output_tokens", getattr(usage, "completion_tokens", 0) or 0)

        return response.choices[0].message.content.strip()


async def generate_with_tools(messages: list[dict], tools: list[dict], stage: str = "unknown"):
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
        except litellm.ServiceUnavailableError as e:
            span.set_status(StatusCode.ERROR, description=str(e))
            span.record_exception(e)
            raise LLMUnavailableError("gemini") from e
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