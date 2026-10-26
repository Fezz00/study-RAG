"""Tests for the MCP server: real MCP calls over an in-memory connection, with a fake API behind it."""

import anyio
import httpx
import pytest
from mcp import Client

from mcp_server import server

QUIZ = {
    "lecture": "Lecture 5",
    "questions": [
        {
            "question": "How many parameters does a pooling layer have?",
            "options": ["2", "0", "F * F", "One per channel"],
            "answer": 1,
            "explanation": "The slide says: Number of parameters: 0.",
            "slide_id": "L05-s124",
        }
    ],
}


def fake_api(request: httpx.Request) -> httpx.Response:
    """Stands in for the FastAPI backend and answers like it would."""
    path = request.url.path
    if path == "/lectures":
        return httpx.Response(200, json=[{"number": 5, "lecture": "Lecture 5", "slides": 101}])
    if path == "/ask":
        citation = {"slide_id": "L05-s102", "lecture": "Lecture 5", "slide": 102, "text": "..."}
        return httpx.Response(
            200, json={"answer": "Max pooling keeps the maximum [L05-s102].", "citations": [citation], "sources": []}
        )
    if path == "/quiz":
        return httpx.Response(200, json=QUIZ)
    return httpx.Response(404, json={"detail": "Lecture 9 is not indexed."})


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(server, "api", httpx.Client(base_url="http://api", transport=httpx.MockTransport(fake_api)))


def call(tool: str, arguments: dict | None = None):
    """Call one tool through the MCP protocol, like Claude would."""

    async def run():
        async with Client(server.server) as client:
            return await client.call_tool(tool, arguments or {})

    return anyio.run(run)


def test_tools_are_listed_with_descriptions_and_read_only():
    async def run():
        async with Client(server.server) as client:
            return (await client.list_tools()).tools

    tools = {tool.name: tool for tool in anyio.run(run)}
    assert set(tools) == {"list_lectures", "ask_lectures", "lecture_overview", "quiz_questions"}
    assert all(tool.description and tool.annotations.read_only_hint for tool in tools.values())
    assert tools["quiz_questions"].input_schema["required"] == ["lecture"]  # count and topic are optional


def test_ask_returns_answer_with_sources(api):
    result = call("ask_lectures", {"question": "What is max pooling?"})
    assert not result.is_error
    assert (
        result.content[0].text
        == "Max pooling keeps the maximum [L05-s102].\n\nSources:\n- [L05-s102] Lecture 5, slide 102"
    )


def test_quiz_shows_options_and_solution(api):
    text = call("quiz_questions", {"lecture": 5, "topic": "pooling"}).content[0].text
    assert "  B) 0" in text
    assert "Solution: B - The slide says: Number of parameters: 0. [L05-s124]" in text


def test_api_errors_become_readable_tool_errors(api):
    result = call("lecture_overview", {"lecture": 9})
    assert result.is_error
    assert "Lecture 9 is not indexed." in result.content[0].text


def test_unreachable_api_is_reported(monkeypatch):
    def down(request):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(server, "api", httpx.Client(base_url="http://api", transport=httpx.MockTransport(down)))
    result = call("list_lectures")
    assert result.is_error
    assert "not reachable" in result.content[0].text
