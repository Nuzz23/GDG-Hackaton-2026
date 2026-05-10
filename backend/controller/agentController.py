"""HTTP endpoints for the three AI agents (Learn Different track).

All routes are nested under `/v1/material/{material_id}/agent/...` to keep
them grouped with the source material they operate on. The shape mirrors
the existing `artifactController` style.

  POST   /v1/material/{material_id}/agent/index          → run processing_agent
  GET    /v1/material/{material_id}/agent/index          → latest INDEX artifact

  POST   /v1/material/{material_id}/agent/quiz           → run quiz_creation_agent
  GET    /v1/material/{material_id}/agent/quiz           → list QUIZ artifacts

  POST   /v1/material/{material_id}/agent/quiz/{quiz_id}/evaluate
                                                         → run eval_agent (text or audio)
  GET    /v1/material/{material_id}/agent/trace          → list TRACE artifacts
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel

from service.agentService import agent_service


agentController = APIRouter(
    prefix="/v1/material/{material_id}/agent",
    tags=["AI Agents"],
)


# ---------------------------------------------------------------------------
# Indexing (Part 2)
# ---------------------------------------------------------------------------


class IndexRequest(BaseModel):
    group_id: int


@agentController.post("/index")
def index_material(material_id: int, group_id: int):
    """Run processing_agent on the material's stored file.

    Heads-up: this is a synchronous call. PDFs index in seconds; audio/video
    can take 30s–3min depending on length. The browser will be waiting.
    For production, swap this to BackgroundTasks + a polled status endpoint.
    For the demo, synchronous is fine and lets the frontend show a spinner.
    """
    return agent_service.index_material(group_id, material_id)


@agentController.get("/index")
def get_latest_index(material_id: int):
    return agent_service.get_latest_index(material_id)


# ---------------------------------------------------------------------------
# Quiz generation (Part 3a)
# ---------------------------------------------------------------------------


class QuizRequest(BaseModel):
    # Either `node_id` (legacy single-node) or `node_ids` (multi-node).
    # The frontend always sends `node_ids` now; `node_id` is kept for
    # backwards compatibility with anything that still calls the old shape.
    node_id: Optional[str] = None
    node_ids: Optional[List[str]] = None
    item_type: str  # "f" | "mcq" | "qa"
    n: int
    difficulty: str = "medium"  # "easy" | "medium" | "hard"


@agentController.post("/quiz")
def generate_quiz(material_id: int, body: QuizRequest):
    return agent_service.generate_quiz(
        material_id=material_id,
        node_id=body.node_id,
        node_ids=body.node_ids,
        item_type=body.item_type,
        n=body.n,
        difficulty=body.difficulty,
    )


@agentController.get("/quiz")
def list_quizzes(material_id: int):
    return agent_service.list_quizzes(material_id)


# ---------------------------------------------------------------------------
# Evaluation (Part 3b)
# ---------------------------------------------------------------------------


@agentController.post("/quiz/{quiz_id}/evaluate")
def evaluate_response(
    material_id: int,
    quiz_id: int,
    item_index: int = Form(...),
    response_text: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
    response_audio: Optional[UploadFile] = File(None),
):
    """Evaluate a student response against item #item_index of a quiz.

    Multipart form so the same endpoint handles text and audio. Pass either:
      - response_text (string), OR
      - response_audio (file upload — m4a/mp3/wav)
    If both are sent, audio wins.
    """
    return agent_service.evaluate_response(
        material_id=material_id,
        quiz_artifact_id=quiz_id,
        item_index=item_index,
        response_text=response_text,
        response_audio=response_audio,
        session_id=session_id,
    )


@agentController.get("/trace")
def list_traces(material_id: int):
    return agent_service.list_traces(material_id)
