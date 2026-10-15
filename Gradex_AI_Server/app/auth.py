"""Role dependencies for lecturer HTTP and WebSocket routes."""
from fastapi import HTTPException, Request, WebSocket

from Gradex_AI_Server.app.session_auth import session_user, trusted_origin


async def require_lecturer(request: Request) -> None:
    user = getattr(request.state, "user", None) or await session_user(request)
    if user["role"] != "lecturer":
        raise HTTPException(403, "Lecturer access required")


async def require_websocket_lecturer(websocket: WebSocket) -> bool:
    try:
        user = getattr(websocket.state, "user", None) or await session_user(websocket)
        if user["role"] != "lecturer" or not trusted_origin(websocket):
            raise HTTPException(403, "Lecturer access required")
        return True
    except HTTPException:
        await websocket.close(code=1008, reason="Please sign in as a lecturer")
        return False
