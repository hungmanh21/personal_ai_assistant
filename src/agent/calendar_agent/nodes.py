from __future__ import annotations

from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.prebuilt import tools_condition
from langgraph.types import Command
from langgraph.types import interrupt
from llm import model

from ..prompt import CALENDAR_AGENT_SYSTEM_PROMPT
from .state import CalendarAssistantState
from .tools import create_calendar_event
from .tools import delete_calendar_event
from .tools import get_next_n_calendar_events

SENSITIVE_TOOLS = [delete_calendar_event, create_calendar_event]
SENSITIVE_TOOL_NAMES = {t.name for t in SENSITIVE_TOOLS}

SAFE_TOOLS = [get_next_n_calendar_events]


assistant_prompt = ChatPromptTemplate.from_messages(
    [
        (
            'system',
            CALENDAR_AGENT_SYSTEM_PROMPT,
        ),
        ('placeholder', '{messages}'),
    ],
)

assistant_runnable = assistant_prompt | model.bind_tools(
    SAFE_TOOLS + SENSITIVE_TOOLS,
)


def call_chatbot(
        state: CalendarAssistantState,
        config: RunnableConfig,
):
    while True:
        result = assistant_runnable.invoke(state)
        # If the LLM happens to return an empty response,
        # we will re-prompt it
        # for an actual response.
        if not result.tool_calls and (
            not result.content
            or isinstance(result.content, list)
            and not result.content[0].get('text')
        ):
            messages = state['messages'] + \
                [('user', 'Respond with a real output.')]
            state = {**state, 'messages': messages}
        else:
            break
    return {'messages': result}


def route_tools(state: CalendarAssistantState):
    next_node = tools_condition(state)
    # If no tools are invoked, return to the user
    if next_node == END:
        return END
    ai_message = state['messages'][-1]
    # This assumes single tool calls.
    # To handle parallel tool calling, you'd want to
    # use an ANY condition
    first_tool_call = ai_message.tool_calls[0]
    if first_tool_call['name'] in SENSITIVE_TOOL_NAMES:
        return 'human_review'
    return 'safe'


def human_review_node(state: CalendarAssistantState) -> Command[
        Literal[
            'chatbot',
            'sensitive_tools',
        ]
]:
    last_message = state['messages'][-1]
    tool_call = last_message.tool_calls[-1]

    human_review = interrupt(
        {
            'question': 'Is this correct?',
            # Surface tool calls for review
            'tool_call': tool_call,
        },
    )

    review_action = human_review['action']
    review_data = human_review.get('data')

    # if approved, call the tool
    if review_action == 'continue':
        return Command(goto='sensitive_tools')

    # provide feedback to LLM
    elif review_action == 'feedback':
        # NOTE: we're adding feedback message as a ToolMessage
        # to preserve the correct order in the message history
        # (AI messages with tool calls need
        #  to be followed by tool call messages)
        tool_message = {
            'role': 'tool',
            # This is our natural language feedback
            'content': review_data,
            'name': tool_call['name'],
            'tool_call_id': tool_call['id'],
        }
        return Command(goto='chatbot', update={'messages': [tool_message]})
