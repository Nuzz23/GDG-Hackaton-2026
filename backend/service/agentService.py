"""Orchestration service that bridges the FastAPI backend with the three
LangGraph/LangChain agents living as sibling Python packages:

  - processing_agent   (Part 2: indexing)
  - quiz_creation_agent (Part 3a: assessment generation)
  - eval_agent         (Part 3b: response evaluation)

The agents are imported in-process (the team's chosen integration mode for
the hackathon — see REPORT.md §1). To make this importable from inside the
backend folder, we add the project root to sys.path at module load time.

All three agents produce JSON-serializable dicts that we persist as
`MaterialArtifact` rows with appropriate `artifact_type`:

  - INDEX : processing_agent.IndexOutput
  - QUIZ  : quiz_creation_agent.QuizOutput
  - TRACE : eval_agent.TraceEvent

This service is the only place that knows about the agent packages. All
controllers go through it.
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException, UploadFile, status

# --- Path bootstrap -------------------------------------------------------
# Add the project root (parent of backend/) to sys.path so the agent packages
# (processing_agent, quiz_creation_agent, eval_agent) are importable.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from database import SessionLocal
from model.material_artifact import ArtifactType
from repository.artifactRepository import ArtifactRepository
from repository.materialRepository import MaterialRepository

logger = logging.getLogger(__name__)


# Minimum text length (in chars) we'll accept before sending a node to the
# quiz generator. Below this the LLM tends to return an empty array — the
# correct behavior, but a confusing UX. Fail fast instead.
_MIN_NODE_TEXT_CHARS = 100


# ---------------------------------------------------------------------------
# Lazy imports of the agents — keeps startup cheap if a deployment doesn't
# need them, and isolates failure modes when an agent dependency is missing.
# ---------------------------------------------------------------------------


def _processing_agent():
    from processing_agent.orchestrator import index_document
    return index_document


def _quiz_agent():
    from quiz_creation_agent.orchestrator import generate_quiz
    from quiz_creation_agent.models import Difficulty, ItemType
    return generate_quiz, Difficulty, ItemType


def _eval_agent():
    from eval_agent.orchestrator import evaluate
    from eval_agent.bridge import from_quiz_item
    from eval_agent.models import ResponseModality
    return evaluate, from_quiz_item, ResponseModality


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AgentService:
    """Glue between FastAPI controllers and the three agents."""

    # ----- Indexing (Part 2) ------------------------------------------------

    def index_material(self, group_id: int, material_id: int) -> dict[str, Any]:
        """Run processing_agent on the material's stored file. Persist the
        IndexOutput as an INDEX artifact and return the payload + artifact id.

        Logs progress to stdout so the user can see what's happening. The
        first call on a cold process pays the cost of importing langgraph,
        building the lingua language-detection models, and compiling the
        graph — typically 30-60 seconds on a laptop. Subsequent calls reuse
        the cached graph and complete in seconds for PDFs.
        """
        import time
        t0 = time.perf_counter()

        with SessionLocal() as db:
            material = MaterialRepository.get_material_by_id(db, group_id, material_id)
            if not material:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Material not found or not accessible for this group",
                )
            file_path = material.path
            if not file_path or not os.path.isfile(file_path):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Material file is missing on disk at {file_path}",
                )

        logger.info(
            "[indexing] START material_id=%s file=%s size=%s bytes",
            material_id, file_path,
            os.path.getsize(file_path) if os.path.isfile(file_path) else "?",
        )

        # Out-of-DB heavy work (no DB session held while the agent runs)
        index_document = _processing_agent()
        logger.info("[indexing] processing_agent imported (t+%.1fs)", time.perf_counter() - t0)

        try:
            payload = index_document(file_path)
        except Exception as e:
            logger.exception("[indexing] FAILED material_id=%s after %.1fs",
                             material_id, time.perf_counter() - t0)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Indexing failed: {str(e)[:300]}",
            )

        logger.info(
            "[indexing] DONE material_id=%s in %.1fs — language=%s, leaves=%s",
            material_id, time.perf_counter() - t0,
            payload.get("source", {}).get("language"),
            self._count_leaves(payload.get("tree", {})),
        )

        with SessionLocal() as db:
            artifact = ArtifactRepository.create_artifact(
                db=db,
                material_id=material_id,
                artifact_type=ArtifactType.INDEX,
                content=payload,
            )
            return {
                "artifact_id": artifact.id,
                "material_id": material_id,
                "index": payload,
            }

    @staticmethod
    def _count_leaves(node: dict) -> int:
        if not isinstance(node, dict):
            return 0
        children = node.get("children") or []
        if not children:
            return 1 if node.get("kind") == "paragraph" else 0
        return sum(AgentService._count_leaves(c) for c in children)

    def get_latest_index(self, material_id: int) -> dict[str, Any]:
        """Return the most recent INDEX artifact for a material, if any."""
        with SessionLocal() as db:
            artifacts = ArtifactRepository.get_artifacts_by_material(
                db, material_id, ArtifactType.INDEX.value
            )
            if not artifacts:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No index has been generated yet for this material",
                )
            artifacts.sort(key=lambda a: a.created_at, reverse=True)
            latest = artifacts[0]
            return {
                "artifact_id": latest.id,
                "material_id": material_id,
                "created_at": latest.created_at.isoformat() if latest.created_at else None,
                "index": latest.content,
            }

    # ----- Quiz generation (Part 3a) ----------------------------------------

    def generate_quiz(
        self,
        material_id: int,
        node_id: str,
        item_type: str,
        n: int,
        difficulty: str = "medium",
    ) -> dict[str, Any]:
        """Generate quiz items for a node of the latest INDEX artifact.

        We materialise the index to a temp file because the quiz_creation_agent
        CLI/orchestrator takes a path. Cheaper than refactoring its API surface
        for in-memory input on a hackathon timeline.
        """
        index_payload = self._latest_index_payload(material_id)
        node = self._find_node(index_payload.get("tree", {}), node_id)
        if node is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"node_id {node_id!r} not found in the latest index",
            )

        # Upfront text-length validation: if the selected node has too little
        # text, the LLM will correctly refuse to generate items and we'd
        # waste an API call. Fail fast with a clear message instead.
        text_len = self._collect_node_text_len(node)
        if text_len < _MIN_NODE_TEXT_CHARS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"The selected node has only {text_len} characters of text — "
                    f"too little for the LLM to generate meaningful items "
                    f"(minimum: {_MIN_NODE_TEXT_CHARS} chars). "
                    "Try selecting a longer paragraph, or a parent section/chapter "
                    "(which aggregates the text of all its leaves)."
                ),
            )

        generate_quiz_fn, Difficulty, ItemType = _quiz_agent()
        try:
            it = ItemType(item_type)
            diff = Difficulty(difficulty)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid item_type or difficulty: {e}",
            )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp:
            import json as _json
            _json.dump(index_payload, tmp, ensure_ascii=False)
            tmp_path = tmp.name

        try:
            quiz_payload = generate_quiz_fn(
                tmp_path,
                item_type=it,
                n=n,
                difficulty=diff,
                node_id=node_id,
            )
        except Exception as e:
            logger.exception("Quiz generation agent failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Quiz generation failed: {str(e)[:300]}",
            )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        # The agent's defensive parsing returns a partial QuizOutput with
        # n_produced=0 instead of raising when the LLM call itself failed
        # (quota, network, malformed JSON) OR when the LLM legitimately
        # returned an empty array (e.g. content judged too thin). For the
        # API surface we want this to be a hard error rather than a silent
        # empty quiz that the frontend would render as "session over".
        if quiz_payload.get("n_produced", 0) == 0:
            warnings = (quiz_payload.get("metadata", {}) or {}).get("warnings") or []
            joined = " | ".join(warnings) if warnings else ""
            is_quota = "RESOURCE_EXHAUSTED" in joined or "quota" in joined.lower()

            if is_quota:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        "Gemini quota exhausted. Wait for the daily reset (~9am IT), "
                        "rotate the API key, or temporarily switch model with "
                        "AGENT_GEMINI_MODEL=gemini-2.5-flash-lite (higher quota). "
                        f"Underlying: {joined[:200]}"
                    ),
                )

            if not joined:
                # No warnings = the LLM returned an empty list cleanly.
                # Most likely the source text wasn't substantive enough.
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "The LLM judged the selected node insufficient to "
                        "generate meaningful items, even though there's some "
                        "text. Try a parent section/chapter (more content), "
                        "or pick a paragraph with denser substantive material. "
                        "If the content really is enough, lowering difficulty "
                        "may help."
                    ),
                )

            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Quiz generation produced 0 items. Underlying: {joined[:300]}",
            )

        with SessionLocal() as db:
            artifact = ArtifactRepository.create_artifact(
                db=db,
                material_id=material_id,
                artifact_type=ArtifactType.QUIZ,
                content=quiz_payload,
            )
            return {
                "artifact_id": artifact.id,
                "material_id": material_id,
                "quiz": quiz_payload,
            }

    def list_quizzes(self, material_id: int) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            artifacts = ArtifactRepository.get_artifacts_by_material(
                db, material_id, ArtifactType.QUIZ.value
            )
            return [
                {
                    "artifact_id": a.id,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    "quiz": a.content,
                }
                for a in artifacts
            ]

    # ----- Evaluation (Part 3b) ---------------------------------------------

    def evaluate_response(
        self,
        material_id: int,
        quiz_artifact_id: int,
        item_index: int,
        response_text: Optional[str],
        response_audio: Optional[UploadFile],
        session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Evaluate a student's response against item #item_index of a quiz.

        Either `response_text` (text modality) OR `response_audio` (audio
        modality) must be provided. If both are provided, audio takes
        precedence and the textual content is ignored.
        """
        with SessionLocal() as db:
            quiz_artifact = ArtifactRepository.get_artifact_by_id(
                db, material_id, quiz_artifact_id
            )
            if not quiz_artifact or quiz_artifact.artifact_type != ArtifactType.QUIZ:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Quiz artifact not found for this material",
                )
            quiz_payload = quiz_artifact.content

        items = quiz_payload.get("items") or []
        if not (0 <= item_index < len(items)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"item_index {item_index} out of range (quiz has {len(items)} items)",
            )

        evaluate_fn, from_quiz_item, ResponseModality = _eval_agent()
        try:
            assessment_item = from_quiz_item(
                items[item_index], language=quiz_payload.get("language", "it")
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Quiz item could not be adapted to AssessmentItem: {e}",
            )

        sid = session_id or f"sess_{uuid.uuid4().hex[:10]}"

        # Resolve modality + response payload.
        if response_audio is not None:
            modality = ResponseModality.AUDIO
            saved_audio_path = self._persist_uploaded_audio(material_id, response_audio)
            try:
                trace_payload = evaluate_fn(
                    assessment_item, saved_audio_path,
                    session_id=sid, response_modality=modality,
                )
            except Exception as e:
                logger.exception("Eval agent failed (audio)")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Evaluation failed: {str(e)[:300]}",
                )
            finally:
                # We KEEP the audio file on disk for traceability — the
                # evaluator already stored its trace in the file system AND
                # we'll persist a copy in DB below.
                pass
        else:
            if not response_text:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Either response_text or response_audio must be provided",
                )
            modality = ResponseModality.TEXT
            try:
                trace_payload = evaluate_fn(
                    assessment_item, response_text,
                    session_id=sid, response_modality=modality,
                )
            except Exception as e:
                logger.exception("Eval agent failed (text)")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Evaluation failed: {str(e)[:300]}",
                )

        with SessionLocal() as db:
            artifact = ArtifactRepository.create_artifact(
                db=db,
                material_id=material_id,
                artifact_type=ArtifactType.TRACE,
                content=trace_payload,
            )
            return {
                "artifact_id": artifact.id,
                "material_id": material_id,
                "session_id": sid,
                "trace": trace_payload,
            }

    def list_traces(self, material_id: int) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            artifacts = ArtifactRepository.get_artifacts_by_material(
                db, material_id, ArtifactType.TRACE.value
            )
            return [
                {
                    "artifact_id": a.id,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    "trace": a.content,
                }
                for a in artifacts
            ]

    # ----- Helpers ----------------------------------------------------------

    def _latest_index_payload(self, material_id: int) -> dict[str, Any]:
        return self.get_latest_index(material_id)["index"]

    @staticmethod
    def _find_node(node: dict, target_id: str) -> Optional[dict]:
        if not isinstance(node, dict):
            return None
        if node.get("node_id") == target_id:
            return node
        for c in node.get("children", []) or []:
            found = AgentService._find_node(c, target_id)
            if found is not None:
                return found
        return None

    @staticmethod
    def _collect_node_text_len(node: dict) -> int:
        """Estimate total text length under a node.

        For a leaf paragraph this is just len(node['text']). For an internal
        node we sum the text length of every leaf descendant — which is also
        the input that quiz_creation_agent will collect when generating.
        """
        if not isinstance(node, dict):
            return 0
        children = node.get("children") or []
        if not children:
            return len((node.get("text") or "").strip())
        return sum(AgentService._collect_node_text_len(c) for c in children)

    @staticmethod
    def _persist_uploaded_audio(material_id: int, audio: UploadFile) -> str:
        """Save the uploaded audio under uploads/audio_responses/material_X/."""
        target_dir = os.path.join("uploads", "audio_responses", f"material_{material_id}")
        os.makedirs(target_dir, exist_ok=True)
        filename = f"{uuid.uuid4().hex[:10]}_{audio.filename or 'audio.bin'}"
        target = os.path.join(target_dir, filename.replace(" ", "_"))
        with open(target, "wb") as f:
            audio.file.seek(0)
            f.write(audio.file.read())
        audio.file.close()
        return target


# Singleton exported to controllers
agent_service = AgentService()
