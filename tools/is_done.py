import json
from utils import history as h
from fns import messages_prompt

# > NOTE: The prompt should include what follow-up actions are available to
# > determine if the user has what they need to complete their task.

def prompt_evaluate(catalog):
    "evaluates the user's query and returns a one-word response."

    return f"""
You will be observing a conversation to determine if the conversation is complete.

You do not answer the user, you answer the question: "Is the user's task complete?"

The following follow-up tasks are available to the user:
{json.dumps(catalog, indent=2)}

If any of these follow-up tasks are appropriate, the conversation is "incomplete". Do not return the actual follow-up task, just return "incomplete".

If there are no follow-up tasks that would improve the conversation, return "done".

If you are unable to determine the status, return "error".

IMPORTANT: ONLY RETURN "done", "incomplete", or "error". No additional help or information should be provided.
"""


def is_done(history, catalog):
    """
    Decides when the assistant has fulfilled its purpose
    """
    stripped_history = h.strip_history_meta(history)
    # find the first user message
    first_user_msg = next(
        (h for h in stripped_history if h["role"] == "user"),
        None
    )
    # if the user message is not found, return False
    if not first_user_msg:
        print("Whooops! `user` message not found")
        return False
    
    last_user_msg = next(
        (h for h in reversed(stripped_history) if h["role"] == "user"),
        None
    )
    
    # find the last assistant message
    assistant_message = next(
        (h for h in reversed(stripped_history) if h["role"] == "assistant"),
        None
    )
    # if the assistant message is not found, return False
    if not assistant_message:
        print("Whooops! `assistant` message not found")
        return False

    descriptions = (["The user can " + action["description"] for action in catalog.values()])
    pertinent = [
        {
            "role": "system",
            "content": prompt_evaluate(descriptions)
        },
        first_user_msg,
        assistant_message,
        *([] if last_user_msg["content"] == first_user_msg["content"] else [last_user_msg]),
    ]

    try:
        print("Prompting for evaluation")
        status = messages_prompt(pertinent)
    except Exception as e:
        status = "incomplete"

    # conditions
    if status == "done":
        print("▶ `is_done` Status: the result is complete")
        return True
    elif status == "incomplete":
        print("▶ `is_done`: Status: the result is incomplete")
        return False
    elif status == "error":
        print("▶ `is_done` Error: the result is an error message")
        return False
    else:
        print("▶ `is_done` Error: received unexpected response:\n\n", status, "\n\n")
        return False