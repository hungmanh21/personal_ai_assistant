from __future__ import annotations

import uuid
from typing import Literal

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.prebuilt import tools_condition
from langgraph.store.base import BaseStore
from langgraph.types import Command
from langgraph.types import interrupt
from llm import model

from ..prompt import GMAIL_AGENT_SYSTEM_PROMPT
from .state import GmailAssistantState
from .tools import fetch_inbox_messages
from .tools import get_email_details
from .tools import send_email

_ = load_dotenv()

SENSITIVE_TOOLS = [send_email]
SENSITIVE_TOOL_NAMES = {t.name for t in SENSITIVE_TOOLS}

SAFE_TOOLS = [fetch_inbox_messages, get_email_details]

assistant_prompt = ChatPromptTemplate.from_messages(
    [
        (
            'system',
            GMAIL_AGENT_SYSTEM_PROMPT,
        ),
        ('placeholder', '{messages}'),
    ],
)

assistant_runnable = assistant_prompt | model.bind_tools(
    SAFE_TOOLS + SENSITIVE_TOOLS,
)


def call_chatbot(
    state: GmailAssistantState,
    config: RunnableConfig,
    store: BaseStore,
):
    user_id = config['configurable']['user_id']
    items = store.search(
        (user_id, 'memories'), query=state['messages'][-1].content, limit=2,
    )
    memories = '\n'.join(item.value['data'] for item in items)
    memories = f'## Memories of user\n{memories}' if memories else ''
    if memories:
        new_first_message_with_memo = state['messages'][0].content + memories
        state['messages'][0].content = new_first_message_with_memo

    # Store new memories if the user asks the model to remember
    last_message = state['messages'][-1]
    if 'remember' in last_message.content.lower():
        memory = last_message
        store.put(
            (user_id, 'memories'), str(
                uuid.uuid4(),
            ), {'data': memory.content},
        )

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


def route_tools(state: GmailAssistantState):
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


def human_review_node(state: GmailAssistantState) -> Command[
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
