"""LangGraph wiring.

The graph structure mirrors the brief's pipeline:

    detect_format
        -> [parse_pdf | parse_pdf_slides | parse_pptx | parse_md
            | parse_audio | parse_video]
        -> normalize_to_blocks
        -> detect_language
        -> clean_blocks
        -> detect_typographic_structure
        -> [build_hierarchy_from_structure  (structured)
            | semantic_segmentation -> hierarchical_clustering  (semantic)]
        -> decide_depth
        -> label_nodes
        -> validate_and_serialize
        -> END

The two conditional edges live in `agent.nodes.routing.route_parser` and
`route_structure_branch`.

Errors short-circuit: every node early-returns when `state["errors"]` is
non-empty, and the conditional selectors route to a `halt` sink that flows
straight to END. This keeps the graph linear in the happy path while making
failure modes loud and traceable.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from processing_agent.nodes import (
    cleaning,
    clustering,
    depth,
    hierarchy,
    labeling,
    language,
    routing,
    segmentation,
    structure,
    validate,
)
from processing_agent.state import IndexingState


def _halt(state: IndexingState) -> dict:
    """Sink node for routes taken when an error has been raised earlier."""
    return {}


def build_graph():
    g: StateGraph = StateGraph(IndexingState)

    # --- entry & format dispatch ---
    g.add_node("detect_format", routing.detect_format)
    g.add_node("parse_pdf", routing.parse_pdf_node)
    g.add_node("parse_pdf_slides", routing.parse_pdf_slides_node)
    g.add_node("parse_pptx", routing.parse_pptx_node)
    g.add_node("parse_md", routing.parse_md_node)
    g.add_node("parse_audio", routing.parse_audio_node)
    g.add_node("parse_video", routing.parse_video_node)
    g.add_node("halt", _halt)

    # --- shared (format-agnostic) pipeline ---
    g.add_node("normalize_to_blocks", routing.normalize_to_blocks)
    g.add_node("detect_language", language.detect_language)
    g.add_node("clean_blocks", cleaning.clean_blocks)
    g.add_node("detect_typographic_structure", structure.detect_typographic_structure)

    # --- structured branch ---
    g.add_node(
        "build_hierarchy_from_structure",
        hierarchy.build_hierarchy_from_structure,
    )

    # --- semantic branch ---
    g.add_node("semantic_segmentation", segmentation.semantic_segmentation)
    g.add_node("hierarchical_clustering", clustering.hierarchical_clustering)

    # --- finishing ---
    g.add_node("decide_depth", depth.decide_depth)
    g.add_node("label_nodes", labeling.label_nodes)
    g.add_node("validate_and_serialize", validate.validate_and_serialize)

    # --- edges ---
    g.set_entry_point("detect_format")
    g.add_conditional_edges(
        "detect_format",
        routing.route_parser,
        {
            "parse_pdf": "parse_pdf",
            "parse_pdf_slides": "parse_pdf_slides",
            "parse_pptx": "parse_pptx",
            "parse_md": "parse_md",
            "parse_audio": "parse_audio",
            "parse_video": "parse_video",
            "halt": "halt",
        },
    )

    for parser_node in (
        "parse_pdf",
        "parse_pdf_slides",
        "parse_pptx",
        "parse_md",
        "parse_audio",
        "parse_video",
    ):
        g.add_edge(parser_node, "normalize_to_blocks")

    g.add_edge("normalize_to_blocks", "detect_language")
    g.add_edge("detect_language", "clean_blocks")
    g.add_edge("clean_blocks", "detect_typographic_structure")

    g.add_conditional_edges(
        "detect_typographic_structure",
        routing.route_structure_branch,
        {
            "structured": "build_hierarchy_from_structure",
            "semantic": "semantic_segmentation",
            "halt": "halt",
        },
    )

    g.add_edge("build_hierarchy_from_structure", "decide_depth")
    g.add_edge("semantic_segmentation", "hierarchical_clustering")
    g.add_edge("hierarchical_clustering", "decide_depth")

    g.add_edge("decide_depth", "label_nodes")
    g.add_edge("label_nodes", "validate_and_serialize")
    g.add_edge("validate_and_serialize", END)
    g.add_edge("halt", END)

    return g.compile()
