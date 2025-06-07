from __future__ import annotations

from ..shared.utils import read_markdown


CALENDAR_AGENT_SYSTEM_PROMPT = read_markdown('calendar_agent.md')
GMAIL_AGENT_SYSTEM_PROMPT = read_markdown('gmail_agent.md')
SUPERVISOR_SYSTEM_PROMPT = read_markdown('supervisor.md')
CLASSIFY_SYSTEM_PROMPT = read_markdown('prompt_classify.md')
