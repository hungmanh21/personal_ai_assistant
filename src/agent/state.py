from __future__ import annotations

from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph import MessagesState
from langgraph.graph.message import add_messages


class AssistantState(MessagesState):
    next: str
    gmail_assistant_msgs: Annotated[list[AnyMessage], add_messages]
    calendar_assistant_msgs: Annotated[list[AnyMessage], add_messages]
