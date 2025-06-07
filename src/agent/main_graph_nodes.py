from __future__ import annotations

from enum import Enum
from typing import Literal

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.types import Command
from llm import model
from pydantic import BaseModel
from pydantic import Field
from typing_extensions import TypedDict

from .calendar_agent.agent import graph as calendar_agent
from .gmail_agent.agent import graph as gmail_agent
from .prompt import CLASSIFY_SYSTEM_PROMPT
from .prompt import SUPERVISOR_SYSTEM_PROMPT
from .state import AssistantState


class ConversationType(str, Enum):
    normal = 'normal'    # Does not require Gmail or Calendar
    advanced = 'advanced'  # Requires Gmail or Calendar access


class ClassificationOutput(BaseModel):
    """Classifies whether the user query requires Gmail or Calendar access."""
    classification: ConversationType = Field(
        ...,
        description="Either 'normal' (no tool access needed) or 'advanced' (Gmail or Calendar access needed)",
    )


class Router(TypedDict):
    """Worker to route to next. If no workers needed, route to FINISH."""
    next: Literal['calendar_agent', 'gmail_agent', 'FINISH']


def classifier_node(state: AssistantState):
    messages = [
        {
            'role': 'system',
            'content': CLASSIFY_SYSTEM_PROMPT,
        },
    ] + [state['messages'][-1]]
    response = model.with_structured_output(
        ClassificationOutput,
    ).invoke(messages)
    classifier_output = None
    if isinstance(response, ClassificationOutput):
        classifier_output = response.classification.value
        print('Classification output', classifier_output)

    if not classifier_output or classifier_output == ConversationType.normal.value:
        return Command(goto='normal_chatbot')
    else:
        return Command(goto='supervisor')


def normal_chatbot(state: AssistantState):
    messages = [
        {
            'role': 'system',
            'content': 'You are a helpful AI Assistant. Try to answer user question as best as possible.',
        },
    ] + state['messages']
    final_message = ''
    for response in model.stream(messages):
        final_message += response.content

    # update state
    return Command(
        update={
            'messages': [
                HumanMessage(
                    content=final_message,
                    name='normal_chatbot',
                ),
            ],
        },
        goto=END,
    )


def supervisor_node(
    state: AssistantState,
) -> Command[Literal['calendar_agent', 'gmail_agent', '__end__']]:
    messages = [
        {
            'role': 'system',
            'content': SUPERVISOR_SYSTEM_PROMPT,
        },
    ] + state['messages']
    response = model.with_structured_output(Router).invoke(messages)
    goto = response['next']
    if goto == 'FINISH':
        goto = END

    print('Next node :', response)

    return Command(goto=goto, update={'next': goto})


def calendar_agent_node(
    state: AssistantState,
) -> Command[Literal['supervisor']]:
    if 'calendar_assistant_msgs' in state:
        state['calendar_assistant_msgs'].append(state['messages'][-1])
        calendar_msgs = state['calendar_assistant_msgs']
    else:
        calendar_msgs = state['messages']
    inputs = {
        'messages': calendar_msgs,
    }
    for events in calendar_agent.stream(inputs):
        e = events
    latest_msg = e['messages'][-1].content
    return Command(
        update={
            'messages': [
                HumanMessage(
                    content=latest_msg,
                    name='calendar_agent',
                ),
            ],
            'calendar_assistant_msgs': e['messages'],
        },
        goto='supervisor',
    )


def gmail_agent_node(
    state: AssistantState,
    config: RunnableConfig,
) -> Command[Literal['supervisor']]:
    if 'gmail_assistant_msgs' in state:
        state['gmail_assistant_msgs'].append(state['messages'][-1])
        gmail_msgs = state['gmail_assistant_msgs']
    else:
        gmail_msgs = state['messages']
    inputs = {
        'messages': gmail_msgs,
    }
    for events in gmail_agent.stream(inputs, config):
        e = events

    latest_msg = e['messages'][-1].content
    return Command(
        update={
            'messages': [
                HumanMessage(
                    content=latest_msg,
                    name='gmail_agent',
                ),
            ],
            'gmail_assistant_msgs': e['messages'],
        },
        goto='supervisor',
    )
