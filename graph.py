from __future__ import annotations

from enum import Enum
from typing import Annotated
from typing import Literal

from cons import CLASSIFY_SYSTEM_PROMPT_PATH
from cons import SUPERVISOR_SYSTEM_PROMPT_PATH
from gg_calendar_agent import calendar_agent
from gmail_agent import gmail_agent
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END
from langgraph.graph import MessagesState
from langgraph.graph import START
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.message import AnyMessage
from langgraph.types import Command
from llm import model
from pydantic import BaseModel
from pydantic import Field
from typing_extensions import TypedDict
from utils import read_markdown


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


class AssistantState(MessagesState):
    next: str
    gmail_assistant_msgs: Annotated[list[AnyMessage], add_messages]
    calendar_assistant_msgs: Annotated[list[AnyMessage], add_messages]


class AIAssistant():
    members = ['calendar_agent', 'gmail_agent']

    def __init__(self, model):
        self.model = model
        self.options = self.members + ['FINISH']

        memory = MemorySaver()

        builder = StateGraph(AssistantState)
        builder.add_edge(START, 'classifier')

        builder.add_node('classifier', self.classifier_node)
        builder.add_node('supervisor', self.supervisor_node)
        builder.add_node('normal_chatbot', self.normal_chatbot)
        builder.add_node('calendar_agent', self.calendar_agent_node)
        builder.add_node('gmail_agent', self.gmail_agent_node)
        self.graph = builder.compile(checkpointer=memory)

        # save image of graph
        self.graph.get_graph().draw_mermaid_png(
            output_file_path='images/supervisors.png',
        )

    def classifier_node(self, state: AssistantState):
        messages = [
            {
                'role': 'system',
                'content': read_markdown(
                    CLASSIFY_SYSTEM_PROMPT_PATH,
                ),
            },
        ] + [state['messages'][-1]]
        response = model.with_structured_output(
            ClassificationOutput,
        ).invoke(messages)
        classifier_output = None
        if isinstance(response, ClassificationOutput):
            classifier_output = response.classification.value
            print("Classification output", classifier_output)

        if not classifier_output or classifier_output == ConversationType.normal.value:
            return Command(goto='normal_chatbot')
        else:
            return Command(goto='supervisor')

    def normal_chatbot(self, state: AssistantState):
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
        self, state: AssistantState,
    ) -> Command[Literal['calendar_agent', 'gmail_agent', '__end__']]:
        messages = [
            {
                'role': 'system',
                'content': read_markdown(
                    SUPERVISOR_SYSTEM_PROMPT_PATH,
                ),
            },
        ] + state['messages']
        response = model.with_structured_output(Router).invoke(messages)
        goto = response['next']
        if goto == 'FINISH':
            goto = END

        return Command(goto=goto, update={'next': goto})

    def calendar_agent_node(
        self, state: AssistantState,
    ) -> Command[Literal['supervisor']]:
        if 'calendar_assistant_msgs' in state:
            state['calendar_assistant_msgs'].append(state['messages'][-1])
            calendar_msgs = state['calendar_assistant_msgs']
        else:
            calendar_msgs = state['messages']
        inputs = {
            'messages': calendar_msgs,
        }
        for events in calendar_agent.graph.stream(inputs):
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
            self, state: AssistantState,
    ) -> Command[Literal['supervisor']]:
        if 'gmail_assistant_msgs' in state:
            state['gmail_assistant_msgs'].append(state['messages'][-1])
            gmail_msgs = state['gmail_assistant_msgs']
        else:
            gmail_msgs = state['messages']
        inputs = {
            'messages': gmail_msgs,
        }
        for events in gmail_agent.graph.stream(inputs):
            e = events
        print('GMAIL MESSAGES')
        for msg in e['messages']:
            print(msg.content)
            print('****')
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


ai_assistant = AIAssistant(model)
