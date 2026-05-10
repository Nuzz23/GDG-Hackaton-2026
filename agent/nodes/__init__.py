"""Graph nodes. Each module exposes one or more callables of shape
`(state: IndexingState) -> dict` that LangGraph wires into the StateGraph.

Conditional edges (the only branching surface) live in `routing`. Everything
else is a straight node.
"""
