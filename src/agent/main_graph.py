from __future__ import annotations

from langchain_openai import AzureOpenAIEmbeddings
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START
from langgraph.graph import StateGraph
from langgraph.store.memory import InMemoryStore

from .main_graph_nodes import calendar_agent_node
from .main_graph_nodes import classifier_node
from .main_graph_nodes import gmail_agent_node
from .main_graph_nodes import normal_chatbot
from .main_graph_nodes import supervisor_node
from .state import AssistantState


memory = MemorySaver()
embeddings = AzureOpenAIEmbeddings(
    model='text-embedding-3-large',
    dimensions=1536,
)
store = InMemoryStore(
    index={
        'embed': embeddings,
    },
)

builder = StateGraph(AssistantState)
builder.add_edge(START, 'classifier')

builder.add_node('classifier', classifier_node)
builder.add_node('supervisor', supervisor_node)
builder.add_node('normal_chatbot', normal_chatbot)
builder.add_node('calendar_agent', calendar_agent_node)
builder.add_node('gmail_agent', gmail_agent_node)
graph = builder.compile(checkpointer=memory, store=store)

# save image of graph
graph.get_graph().draw_mermaid_png(
    output_file_path='images/supervisors.png',
)
