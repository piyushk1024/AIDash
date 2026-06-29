from opentelemetry import trace
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter


def setup_telemetry() -> None:
    """Initialise the global TracerProvider with a stdout console exporter.

    Called once at application startup in main.py lifespan.
    All trace.get_tracer() calls made anywhere in the process resolve to
    this provider — including ones made before setup_telemetry() runs,
    because OTel returns a ProxyTracer that upgrades itself once a provider
    is registered.
    """
    resource = Resource(attributes={SERVICE_NAME: "dasher"})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)

def shutdown_telemetry() -> None:
    """Flush and shut down the global TracerProvider.

    Called in main.py lifespan teardown to ensure BatchSpanProcessor
    flushes any pending spans before the process exits.
    """
    trace.get_tracer_provider().shutdown()


def get_tracer(name: str) -> trace.Tracer:
    """Return a named tracer from the global provider."""
    return trace.get_tracer(name)