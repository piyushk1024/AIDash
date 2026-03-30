from typing import List, Optional
from pydantic import BaseModel, Field


class SemanticColumn(BaseModel):
    column: str
    semantic_role: str
    confidence: float = Field(ge=0.0, le=1.0)


class InferSemanticsRequest(BaseModel):
    business_hint: Optional[str] = None


class InferSemanticsResponse(BaseModel):
    dataset_id: str
    business_hint: Optional[str] = None
    dataset_grain: str
    date_columns: List[SemanticColumn]
    dimensions: List[SemanticColumn]
    measures: List[SemanticColumn]
    flags: List[SemanticColumn]
    identifiers: List[SemanticColumn]
    unknown: List[SemanticColumn]
    notes: List[str]
