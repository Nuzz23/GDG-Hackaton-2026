"""LangGraph wiring for the evaluation agent.

Pipeline:

    detect_modality
      ├─► transcribe_audio → extract_paralinguistic ─┐
      └─► pass_through_text ─────────────────────────┤
                                                     ▼
                                       detect_assessment_type
                                                     │
                          ┌──────────┬───────────────┼──────────────┐
                          ▼          ▼               ▼              ▼
                   judge_closed  judge_flashcard  judge_open      halt
                          └──────────┴───────────────┘
                                     ▼
                       apply_two_strikes_rule
                                     ▼
                         route_intervention
                                     ▼
                      generate_student_message
                                     ▼
                         emit_trace_event
                                     ▼
                       update_session_state
                                     ▼
                                    END

Two conditional-edge selectors live in `nodes.py` (route_by_modality,
route_by_assessment_type). Errors short-circuit through `halt` → END.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from eval_agent import nodes
from eval_agent.state import EvalState


def _halt(state: EvalState) -> dict:
    return {}


def build_graph():
    g = StateGraph(EvalState)

    # Modality branch
    g.add_node("pass_through_text", nodes.pass_through_text)
    g.add_node("transcribe_audio", nodes.transcribe_audio)
    g.add_node("extract_paralinguistic", nodes.extract_paralinguistic)

    # Assessment-type branch
    g.add_node("judge_closed", nodes.judge_closed)
    g.add_node("judge_flashcard", nodes.judge_flashcard)
    g.add_node("judge_open", nodes.judge_open)
    g.add_node("halt", _halt)

    # Common tail
    g.add_node("apply_two_strikes_rule", nodes.apply_two_strikes_rule)
    g.add_node("route_intervention", nodes.route_intervention)
    g.add_node("generate_student_message", nodes.generate_student_message)
    g.add_node("emit_trace_event", nodes.emit_trace_event)
    g.add_node("update_session_state", nodes.update_session_state)

    # ---- edges ----
    # Entry: conditional dispatch by modality. LangGraph requires a node
    # entry point; we use a small selector wrapper at the start.
    g.set_conditional_entry_point(
        nodes.route_by_modality,
        {"audio": "transcribe_audio", "text": "pass_through_text"},
    )

    g.add_edge("transcribe_audio", "extract_paralinguistic")
    # Both branches converge at the assessment-type dispatch.
    g.add_conditional_edges(
        "extract_paralinguistic",
        nodes.route_by_assessment_type,
        {
            "closed": "judge_closed",
            "flashcard": "judge_flashcard",
            "open": "judge_open",
            "halt": "halt",
        },
    )
    g.add_conditional_edges(
        "pass_through_text",
        nodes.route_by_assessment_type,
        {
            "closed": "judge_closed",
            "flashcard": "judge_flashcard",
            "open": "judge_open",
            "halt": "halt",
        },
    )

    for judge in ("judge_closed", "judge_flashcard", "judge_open"):
        g.add_edge(judge, "apply_two_strikes_rule")
    g.add_edge("apply_two_strikes_rule", "route_intervention")
    g.add_edge("route_intervention", "generate_student_message")
    g.add_edge("generate_student_message", "emit_trace_event")
    g.add_edge("emit_trace_event", "update_session_state")
    g.add_edge("update_session_state", END)
    g.add_edge("halt", END)

    return g.compile()
