from pathlib import Path
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# backend/app/services/ -> backend/app/ -> backend/ -> backend/logs/
LOG_DIR = Path(__file__).parent.parent.parent / "logs"
TELEMETRY_LOG_PATH = LOG_DIR / "telemetry.log"
MAX_SPAN_LINES = 500  # keep only the most recent N spans on disk


class _TrimmingFileWriter:
    """File-like object passed as ConsoleSpanExporter's `out`. Appends one
    compact JSON line per span, then trims the file to the most recent
    MAX_SPAN_LINES lines. Console export was flooding the dev CLI during
    normal use — this keeps spans available for inspection without
    external log-rotation tooling, appropriate for dev-only volume.
    """
    def __init__(self, path: Path, max_lines: int):
        self.path = path
        self.max_lines = max_lines
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def write(self, text: str) -> int:
        with open(self.path, "a") as f:
            f.write(text)
        self._trim()
        return len(text)

    def flush(self) -> None:
        pass

    def _trim(self) -> None:
        lines = self.path.read_text().splitlines(keepends=True)
        if len(lines) > self.max_lines:
            self.path.write_text("".join(lines[-self.max_lines:]))


def setup_telemetry() -> None:
    """Initialise the global TracerProvider, writing spans to a git-ignored
    log file instead of stdout.

    Called once at application startup in main.py lifespan.
    All trace.get_tracer() calls made anywhere in the process resolve to
    this provider — including ones made before setup_telemetry() runs,
    because OTel returns a ProxyTracer that upgrades itself once a provider
    is registered.
    """
    resource = Resource(attributes={SERVICE_NAME: "dasher"})
    provider = TracerProvider(resource=resource)

    writer = _TrimmingFileWriter(TELEMETRY_LOG_PATH, MAX_SPAN_LINES)
    exporter = ConsoleSpanExporter(
        out=writer,
        formatter=lambda span: span.to_json(indent=None) + "\n",
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
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
    