"""MCP server: lets an AI assistant (Claude Code, Claude Desktop, ...) use the study assistant as tools.

MCP (Model Context Protocol) is a standard way to give an AI app new tools: the app starts this
server, reads the tool list (names, descriptions, parameters) and calls a tool when it fits.

Like the UI, this is a thin client of the FastAPI backend - it only talks HTTP to API_URL.
The guardrails, metrics and the model calls all stay in the API, and the same server works
against uvicorn on your machine or the Kubernetes deployment. All tools only read.

Run (the AI app normally starts it itself; it talks MCP over stdin/stdout):
    python mcp_server/server.py
Register with Claude Code:
    claude mcp add study-rag -e API_URL=http://localhost:8000 -- "$PWD/.venv/bin/python" "$PWD/mcp_server/server.py"
"""

import os

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

API_URL = os.getenv("API_URL", "http://localhost:8000")

# Overviews and quizzes can take minutes the first time, so the timeout is generous.
api = httpx.Client(base_url=API_URL, timeout=600)

server = MCPServer(
    "study-rag",
    instructions=(
        "Tools for the user's university lecture slides. Answers come only from the slides and cite "
        "slide IDs like [L05-s12]. If a tool says 'Not covered in the slides.', tell the user that "
        "instead of answering from your own knowledge."
    ),
)

# Hints for the AI app: these tools change nothing and only reach the study assistant.
READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)


def call_api(method: str, path: str, **kwargs) -> dict | list:
    """Call the API; turn failures into a ToolError, which the AI app shows as a readable tool error."""
    try:
        response = api.request(method, path, **kwargs)
    except httpx.HTTPError as error:
        raise ToolError(f"The study assistant API at {API_URL} is not reachable ({error}). Is it running?")
    if response.is_error:
        detail = (
            response.json().get("detail", response.text)
            if "json" in response.headers.get("content-type", "")
            else response.text
        )
        raise ToolError(f"API error {response.status_code}: {detail}")
    return response.json()


@server.tool(annotations=READ_ONLY)
def list_lectures() -> str:
    """List the lectures that are indexed, with their number of slides. Use it to find valid lecture numbers."""
    lectures = call_api("GET", "/lectures")
    if not lectures:
        return "No lectures indexed yet."
    return "\n".join(
        f"- {lecture['lecture']} (number {lecture['number']}): {lecture['slides']} slides" for lecture in lectures
    )


@server.tool(annotations=READ_ONLY)
def ask_lectures(question: str) -> str:
    """Answer a question from the lecture slides only, with slide citations like [L05-s12].

    Returns 'Not covered in the slides.' when the slides don't contain the answer.
    """
    result = call_api("POST", "/ask", json={"question": question})
    sources = [f"- [{c['slide_id']}] {c['lecture']}, slide {c['slide']}" for c in result["citations"]]
    return result["answer"] + ("\n\nSources:\n" + "\n".join(sources) if sources else "")


@server.tool(annotations=READ_ONLY)
def lecture_overview(lecture: int) -> str:
    """The main topics of one lecture, each with a short summary and its slides. Can take minutes the first time."""
    overview = call_api("GET", f"/lectures/{lecture}/overview")
    lines = [f"{overview['lecture']} ({overview['slides']} slides)"]
    for topic in overview["topics"]:
        lines.append(f"\n## {topic['title']} [{', '.join(topic['slides'])}]\n{topic['summary']}")
    return "\n".join(lines)


@server.tool(annotations=READ_ONLY)
def quiz_questions(lecture: int, count: int = 3, topic: str | None = None) -> str:
    """Multiple-choice questions from a lecture's slides, optionally only about a topic (count 1-10).

    The result includes the correct answers. When quizzing the user, show only the question and
    options, wait for their answer, and reveal the solution afterwards.
    """
    body = call_api("POST", "/quiz", json={"lecture": lecture, "count": count, "topic": topic})
    blocks = []
    for i, q in enumerate(body["questions"], 1):
        options = "\n".join(f"  {letter}) {option}" for letter, option in zip("ABCD", q["options"]))
        solution = f"  Solution: {'ABCD'[q['answer']]} - {q['explanation']} [{q['slide_id']}]"
        blocks.append(f"{i}. {q['question']}\n{options}\n{solution}")
    return "\n\n".join(blocks)


if __name__ == "__main__":
    server.run()  # stdio: never print() here, stdout is the MCP channel
