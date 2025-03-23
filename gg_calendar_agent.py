from __future__ import annotations

from typing import Annotated
from typing import Literal
from typing import TypedDict

from cons import CALENDAR_AGENT_SYSTEM_PROMPT_PATH
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END
from langgraph.graph import START
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.message import AnyMessage
from langgraph.prebuilt import tools_condition
from langgraph.types import Command
from langgraph.types import interrupt
from llm import model
from tools import create_calendar_event
from tools import delete_calendar_event
from tools import get_next_n_calendar_events
from utils import create_tool_node_with_fallback
from utils import read_markdown
_ = load_dotenv()


class CalendarAssistantState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    user_info: list[dict]


class CalendarAssistant:
    def __init__(self, model):
        self.model = model
        self.__init_chatbot()
        graph_builder = StateGraph(CalendarAssistantState)

        # add node
        graph_builder.add_node('chatbot', self.call_chatbot)
        graph_builder.add_node('fetch_user_info', self._fetch_user_info)
        graph_builder.add_node(
            'safe_tools', create_tool_node_with_fallback(self.safe_tools),
        )
        graph_builder.add_node(
            'sensitive_tools', create_tool_node_with_fallback(
                self.sensitive_tools,
            ),
        )
        graph_builder.add_node(
            'human_review_node', self.human_review_node,
        )

        # add edges
        graph_builder.add_edge(START,  'fetch_user_info')
        graph_builder.add_edge('fetch_user_info',  'chatbot')
        graph_builder.add_conditional_edges(
            'chatbot', self.route_tools, {
                'safe': 'safe_tools',
                'human_review': 'human_review_node',
                END: END,
            },
        )

        graph_builder.add_edge('safe_tools', 'chatbot')
        graph_builder.add_edge('sensitive_tools', 'chatbot')

        memory = MemorySaver()
        self.graph = graph_builder.compile(
            # checkpointer=memory,
        )

        # save image of graph
        self.graph.get_graph().draw_mermaid_png(
            output_file_path='images/calendar_graph.png',
        )

    def __init_chatbot(self):
        assistant_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    'system',
                    read_markdown(CALENDAR_AGENT_SYSTEM_PROMPT_PATH),
                ),
                ('placeholder', '{messages}'),
            ],
        )

        self.safe_tools = [get_next_n_calendar_events]

        self.sensitive_tools = [delete_calendar_event, create_calendar_event]

        self.sensitive_tool_names = {t.name for t in self.sensitive_tools}

        self.assistant_runnable = assistant_prompt | self.model.bind_tools(
            self.safe_tools + self.sensitive_tools,
        )

    def call_chatbot(
        self, state: CalendarAssistantState,
        config: RunnableConfig,
    ):
        while True:
            result = self.assistant_runnable.invoke(state)
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

    def route_tools(self, state: CalendarAssistantState):
        next_node = tools_condition(state)
        # If no tools are invoked, return to the user
        if next_node == END:
            return END
        ai_message = state['messages'][-1]
        # This assumes single tool calls.
        # To handle parallel tool calling, you'd want to
        # use an ANY condition
        first_tool_call = ai_message.tool_calls[0]
        if first_tool_call['name'] in self.sensitive_tool_names:
            return 'human_review'
        return 'safe'

    def _fetch_user_info(self, state: CalendarAssistantState):
        return {
            'user_info': {
                'name': 'Hoàng Hùng Mạnh',
                'dob': 'November 21st 2003',
            },
        }

    def human_review_node(self, state) -> Command[
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


calendar_agent = CalendarAssistant(model)
