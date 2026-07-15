import io
import base64
import logging
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image

logger = logging.getLogger(__name__)

CHART_IMAGE_WIDTH = 6.5 * inch
CHART_IMAGE_HEIGHT = 4 * inch


def generate_agent_report_pdf(dashboard_title: str, rationale: str, charts: list[dict]) -> bytes:
    """
    Builds a PDF report for an agent-mode dashboard: title, rationale as an
    executive-summary opener, then one section per chart (title + image).
    Agent-mode only — pipeline dashboards have no rationale.

    `charts` is a list of {"chart_title": str, "image_base64": str}, where
    image_base64 is a PNG rendered client-side by react-plotly.js's
    Plotly.toImage() and posted up by the frontend. No server-side chart
    rendering happens here.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle", parent=styles["Title"], alignment=TA_CENTER, spaceAfter=18,
    )
    heading_style = styles["Heading2"]
    body_style = styles["BodyText"]

    story = [Paragraph(dashboard_title or "Dashboard Report", title_style)]

    if rationale:
        story.append(Paragraph("Executive Summary", heading_style))
        story.append(Paragraph(rationale, body_style))
        story.append(Spacer(1, 0.3 * inch))

    for chart in charts:
        chart_title = chart.get("chart_title", "Untitled chart")
        image_base64 = chart.get("image_base64")

        story.append(Paragraph(chart_title, heading_style))

        if not image_base64:
            story.append(Paragraph("(No chart image provided)", body_style))
        else:
            try:
                png_bytes = base64.b64decode(image_base64)
                story.append(Image(io.BytesIO(png_bytes), width=CHART_IMAGE_WIDTH, height=CHART_IMAGE_HEIGHT))
            except Exception:
                logger.exception("Failed to decode chart image for '%s'", chart_title)
                story.append(Paragraph("(Chart image could not be decoded)", body_style))

        story.append(Spacer(1, 0.3 * inch))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()