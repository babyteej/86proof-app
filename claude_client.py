"""
86 Proof Claude Client
─────────────────────────────────────────
Handles all communication with the Anthropic API.

The chat flow:
  1. System prompt defines Claude's persona and rules
  2. Data context is prepended to the conversation (always available)
  3. Conversation history is passed for multi-turn context within session
  4. Claude responds, response is returned to the app

Model choice: claude-sonnet-4-5
  - Strong reasoning for operational analysis
  - Much cheaper than Opus for high-volume chat usage
  - 200K context window handles full bar program data easily
"""

import os
import anthropic
from prompts import SYSTEM_PROMPT, build_data_context


# ── CONFIG ─────────────────────────────────────────────
MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 2000


def get_client():
    """
    Initialize the Anthropic client using the API key from .env.
    Raises a clear error if the key is missing.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY not set in environment. "
            "Make sure your .env file contains a valid API key."
        )
    return anthropic.Anthropic(api_key=api_key)


def chat(user_message, conversation_history, bar_data):
    """
    Send a chat message to Claude and return the response.

    Args:
      user_message: The new message from the user (str)
      conversation_history: List of prior messages in this conversation
                            Format: [{"role": "user"|"assistant", "content": "..."}]
      bar_data: The parsed bar program data dict from data_loader

    Returns:
      The text of Claude's response (str)
    """
    client = get_client()

    # Build the data context — gets prepended as a user message
    # so Claude has the program data available for every question
    data_context = build_data_context(bar_data)

    # Construct the messages list
    # Pattern: first message is the data context (acts as setup),
    # then the conversation history, then the new user message
    messages = []

    # Inject the data context as the first user message
    # This is a common pattern — system prompts define behavior,
    # data context defines the world Claude is operating in
    messages.append({
        "role": "user",
        "content": data_context
    })

    messages.append({
        "role": "assistant",
        "content": "I have your bar program data loaded and I'm ready to help. "
                   "What would you like to look at?"
    })

    # Add the conversation history
    messages.extend(conversation_history)

    # Add the new user message
    messages.append({
        "role": "user",
        "content": user_message
    })

    # Make the API call
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    # Extract the text from the response
    return response.content[0].text