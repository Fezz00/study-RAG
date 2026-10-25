"""Request and response shapes of the API.

Pydantic models describe the JSON. FastAPI uses them to validate requests
and to generate the /docs page.
"""

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1, examples=["What is max pooling?"])


class Citation(BaseModel):
    slide_id: str
    lecture: str
    slide: int
    text: str


class Source(BaseModel):
    slide_id: str
    score: float


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    sources: list[Source]


class DocumentResponse(BaseModel):
    filename: str
    slides_indexed: int


class Lecture(BaseModel):
    number: int
    lecture: str
    slides: int


class Topic(BaseModel):
    title: str
    summary: str
    slides: list[str]


class OverviewResponse(BaseModel):
    lecture: str
    slides: int
    topics: list[Topic]
