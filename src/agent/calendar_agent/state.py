from __future__ import annotations

from typing import Annotated
from typing import TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class CalendarAssistantState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
