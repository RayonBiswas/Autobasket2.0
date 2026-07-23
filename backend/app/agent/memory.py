# In-memory session store mapping session_id -> list of message dicts
# Message format: {"role": "user"|"assistant"|"system", "content": "text"}

_sessions = {}
_pending_confirmations = {}


def get_history(session_id: str) -> list:
    """Retrieve chat history for a session."""
    if not session_id:
        return []
    if session_id not in _sessions:
        _sessions[session_id] = []
    return _sessions[session_id]


def add_message(session_id: str, role: str, content: str):
    """Append a message to the session's chat history."""
    if not session_id:
        return
    if session_id not in _sessions:
        _sessions[session_id] = []
    _sessions[session_id].append({"role": role, "content": content})


def clear_history(session_id: str):
    """Reset chat history for a session."""
    if session_id in _sessions:
        _sessions[session_id] = []
    if session_id in _pending_confirmations:
        del _pending_confirmations[session_id]


def set_pending_confirmation(session_id: str, payload: dict):
    if not session_id:
        return
    _pending_confirmations[session_id] = payload


def get_pending_confirmation(session_id: str):
    if not session_id:
        return None
    return _pending_confirmations.get(session_id)


def clear_pending_confirmation(session_id: str):
    if not session_id:
        return
    _pending_confirmations.pop(session_id, None)
