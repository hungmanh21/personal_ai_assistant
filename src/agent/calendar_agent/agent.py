from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END
from langgraph.graph import START
from langgraph.graph import StateGraph

from ..shared.graph_utils import create_tool_node_with_fallback
from .nodes import call_chatbot
from .nodes import human_review_node
from .nodes import route_tools
from .nodes import SAFE_TOOLS
from .nodes import SENSITIVE_TOOLS
from .state import CalendarAssistantState


graph_builder = StateGraph(CalendarAssistantState)

# add node
graph_builder.add_node('chatbot', call_chatbot)
graph_builder.add_node(
    'safe_tools', create_tool_node_with_fallback(SAFE_TOOLS),
)
graph_builder.add_node(
    'sensitive_tools', create_tool_node_with_fallback(
        SENSITIVE_TOOLS,
    ),
)
graph_builder.add_node(
    'human_review_node', human_review_node,
)

# add edges
graph_builder.add_edge(START,  'chatbot')
graph_builder.add_conditional_edges(
    'chatbot', route_tools, {
        'safe': 'safe_tools',
        'human_review': 'human_review_node',
        END: END,
    },
)

graph_builder.add_edge('safe_tools', 'chatbot')
graph_builder.add_edge('sensitive_tools', 'chatbot')

memory = InMemorySaver()
graph = graph_builder.compile(
    checkpointer=memory,
)

# save image of graph
graph.get_graph().draw_mermaid_png(
    output_file_path='images/calendar_graph.png',
)
