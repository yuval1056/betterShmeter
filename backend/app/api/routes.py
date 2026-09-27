"""Thin HTTP layer: translates requests/responses and turns unexpected
exceptions into a 500. No business logic lives here."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationList,
    GithubConnectRequest,
    GithubStatus,
    HistoryResponse,
)
from app.services.git_service import credentials, mcp_client
from app.services.chat_service import handle_message
from app.storage.repository import MessageRepository

router = APIRouter()


def get_repository(request: Request) -> MessageRepository:
    return request.app.state.repository


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.post("/chat", response_model=ChatResponse)
async def post_chat(
    payload: ChatRequest,
    repository: MessageRepository = Depends(get_repository),
) -> ChatResponse:
    try:
        return await handle_message(
            repository, payload.user_id, payload.message, payload.conversation_id
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="internal error") from exc


@router.get("/history/{user_id}", response_model=HistoryResponse)
async def get_history(
    user_id: str,
    repository: MessageRepository = Depends(get_repository),
) -> HistoryResponse:
    try:
        messages = await repository.get_history(user_id)
        return HistoryResponse(user_id=user_id, messages=messages)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="internal error") from exc


@router.delete("/history/{user_id}")
async def delete_history(
    user_id: str,
    repository: MessageRepository = Depends(get_repository),
) -> dict:
    try:
        await repository.clear_history(user_id)
        return {"status": "cleared"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="internal error") from exc


@router.get("/conversations/{user_id}", response_model=ConversationList)
async def list_conversations(
    user_id: str,
    repository: MessageRepository = Depends(get_repository),
) -> ConversationList:
    try:
        return ConversationList(
            user_id=user_id, conversations=await repository.list_conversations(user_id)
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="internal error") from exc


@router.get("/conversations/{user_id}/{conversation_id}", response_model=HistoryResponse)
async def get_conversation(
    user_id: str,
    conversation_id: str,
    repository: MessageRepository = Depends(get_repository),
) -> HistoryResponse:
    try:
        messages = await repository.get_history(user_id, conversation_id=conversation_id)
        return HistoryResponse(user_id=user_id, messages=messages)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="internal error") from exc


@router.delete("/conversations/{user_id}/{conversation_id}")
async def delete_conversation(
    user_id: str,
    conversation_id: str,
    repository: MessageRepository = Depends(get_repository),
) -> dict:
    try:
        await repository.delete_conversation(user_id, conversation_id)
        return {"status": "deleted"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="internal error") from exc


async def _status(user_id: str) -> GithubStatus:
    creds = await credentials.get_user_credentials(user_id)
    if not creds:
        return GithubStatus(connected=False)
    return GithubStatus(connected=True, owner=creds.owner, repo=creds.repo)


@router.post("/github/connect", response_model=GithubStatus)
async def github_connect(payload: GithubConnectRequest) -> GithubStatus:
    creds = credentials.GitCredentials(
        token=payload.token.strip(),
        owner=payload.owner.strip(),
        repo=payload.repo.strip(),
    )
    # Nothing is saved unless the MCP server confirms the token and repo.
    try:
        await mcp_client.verify_repo(payload.user_id, creds.token, creds.owner, creds.repo)
    except mcp_client.VerificationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await credentials.save_credentials(payload.user_id, creds, payload.conversation_id)
    return await _status(payload.user_id)


@router.get("/github/status/{user_id}", response_model=GithubStatus)
async def github_status(user_id: str) -> GithubStatus:
    return await _status(user_id)


@router.delete("/github/{user_id}", response_model=GithubStatus)
async def github_disconnect(user_id: str) -> GithubStatus:
    await credentials.delete_credentials(user_id)
    await mcp_client.close_session(user_id)
    return GithubStatus(connected=False)
