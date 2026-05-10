"""Format-specific parsers.

Each module exposes a single `parse(path) -> Document` function. The agent
graph dispatches to the right parser based on detected source type. After
parsing, no downstream node knows or cares which parser produced the blocks.
"""

from processing_agent.parsers.pdf_parser import parse as parse_pdf
from processing_agent.parsers.pptx_parser import parse as parse_pptx
from processing_agent.parsers.md_parser import parse as parse_md
from processing_agent.parsers.audio_parser import parse as parse_audio
from processing_agent.parsers.video_parser import parse as parse_video

__all__ = [
    "parse_pdf",
    "parse_pptx",
    "parse_md",
    "parse_audio",
    "parse_video",
]
