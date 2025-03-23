from __future__ import annotations

import chainlit as cl
from dateutil import parser
from graph import ai_assistant
from langchain.schema.runnable.config import RunnableConfig
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from tools import get_credentials
from utils import read_personal_info


@cl.on_chat_start
async def get_credentials_from_user():
    personal_info = read_personal_info()
    credentials_file_path = personal_info.get('token_access_path', None)

    if not credentials_file_path:
        res = await cl.AskActionMessage(
            content='I need your credentials to get access to your Calendar.',
            actions=[
                cl.Action(
                    name='continue', payload={
                        'value': 'continue',
                    }, label='✅ Continue',
                ),
                cl.Action(
                    name='cancel', payload={
                        'value': 'cancel',
                    }, label='❌ Cancel',
                ),
            ],
        ).send()

        if res and res.get('payload', {}).get('value') == 'continue':
            # Send a clean confirmation message
            await cl.Message(
                content=(
                    '✅ Thank you for your permission! '
                    'How can I help you today?'
                ),
            ).send()
            get_credentials()
        else:
            await cl.Message(content='❌ You cancelled your request.').send()


def format_time(iso_str):
    """Convert ISO time string to readable format."""
    return parser.isoparse(iso_str).strftime('%d/%m/%Y %H:%M:%S')


def create_delete_confirmation(calendar_name):
    """Create confirmation message for deleting a calendar event."""
    return (
        f'⚠️ **Xác nhận xoá sự kiện** ⚠️\n\n'
        f'Bạn có chắc chắn muốn xóa sự kiện này khỏi lịch **{calendar_name}** '
        'không? 🗓️❌\n\n'
        '👉 Nếu đồng ý, vui lòng nhập **Approve**.\n'
        '💬 Nếu có góp ý hoặc muốn thay đổi, hãy nhập phản hồi của bạn nhé!'
    )


def create_event_confirmation(tool_call_arg):
    """Create confirmation message for creating a calendar event."""
    start_time = format_time(tool_call_arg['start_time'])
    end_time = format_time(tool_call_arg['end_time'])

    calendar_name = tool_call_arg['calendar_name']
    title = tool_call_arg['title']
    location = tool_call_arg['location']
    description = tool_call_arg['description']

    return (
        f'🎉 **Sự kiện mới của bạn đã sẵn sàng!** 🎉\n\n'
        f'🗓️ **Lịch:** {calendar_name}\n'
        f'📌 **Tiêu đề:** {title}\n'
        f'📍 **Địa điểm:** {location}\n'
        f'🕒 **Thời gian:** {start_time} → {end_time}\n'
        f'📝 **Mô tả:** {description}\n\n'
        '✅ Nếu mọi thứ đều ổn, vui lòng nhập **Approve**.\n'
        '✏️ Nếu muốn chỉnh sửa, hãy nhập góp ý của bạn nhé! 😊'
    )


def creat_send_email_confirmation(tool_call_arg):
    """Create confirmation message for sending an email."""
    to_email = tool_call_arg['to_email']
    subject = tool_call_arg['subject']
    message_body = tool_call_arg['message_body']

    return (
        f'📧 **Xác nhận gửi email** 📧\n\n'
        f'📤 **Đến:** {to_email}\n'
        f'📨 **Chủ đề:** {subject}\n'
        f'📝 **Nội dung:** {message_body}\n\n'
        '👉 Nếu đồng ý, vui lòng nhập **Approve**.\n'
        '💬 Nếu có góp ý hoặc muốn thay đổi, hãy nhập phản hồi của bạn nhé!'
    )


def handle_msg_confirmation(data):
    """Handle tool call confirmation messages."""
    tool_call_arg = data.value['tool_call']['args']
    tool_name = data.value['tool_call']['name']

    if tool_name == 'delete_calendar_event':
        return create_delete_confirmation(tool_call_arg['calendar_name'])
    elif tool_name == 'create_calendar_event':
        return create_event_confirmation(tool_call_arg)
    elif tool_name == 'send_email':
        return creat_send_email_confirmation(tool_call_arg)


async def process_stream_data(stream_data, final_answer):
    """Process stream data and update final answer."""
    for node, stream_mode, data in stream_data:
        if stream_mode == 'messages':
            msg, metadata = data
            if (
                msg.content and
                not isinstance(msg, HumanMessage) and
                    metadata['langgraph_node'] == 'chatbot'
            ):
                await final_answer.stream_token(msg.content)

        elif stream_mode == 'updates' and '__interrupt__' in data:
            confirm_msg = handle_msg_confirmation(data['__interrupt__'][0])
            actions = [
                cl.Action(
                    name='approve',
                    icon='mouse-pointer-click',
                    payload={'value': 'example_value'},
                    label='Approve',
                ),
            ]
            await cl.Message(confirm_msg, actions=actions).send()

    if final_answer.content:
        await final_answer.send()


@cl.on_message
async def on_message(msg: cl.Message):
    """Main message handler for Chainlit."""
    config = {'configurable': {'thread_id': cl.context.session.id}}
    final_answer = cl.Message(content='')
    snapshot = ai_assistant.graph.get_state(config)

    # If there's a pending operation waiting for input
    if snapshot.next:
        action = (
            {'action': 'continue'}
            if msg.content.lower() == 'approve'
            else {'action': 'feedback', 'data': msg.content}
        )

        stream_data = ai_assistant.graph.stream(
            Command(resume=action),
            config=RunnableConfig(**config),
            stream_mode=['updates', 'messages'],
            subgraphs=True,
        )
        await process_stream_data(stream_data, final_answer)

    # Initial message flow
    else:
        stream_data = ai_assistant.graph.stream(
            {'messages': [HumanMessage(content=msg.content)]},
            stream_mode=['updates', 'messages'],
            config=RunnableConfig(**config),
            subgraphs=True,
        )
        await process_stream_data(stream_data, final_answer)
