from typing import Literal

from pydantic import BaseModel, Field

ChatStatus = Literal["ok", "rejected", "error"]
Role = Literal["user", "assistant"]


class ChatRequest(BaseModel):
    user_id: str = Field(min_length=1)
    conversation_id: str | None = None
    message: str = Field(min_length=1)


class ChatResponse(BaseModel):
    reply: str
    status: ChatStatus


class GithubConnectRequest(BaseModel):
    user_id: str = Field(min_length=1)
    conversation_id: str | None = None
    token: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    repo: str = Field(min_length=1)


class GithubStatus(BaseModel):
    connected: bool
    owner: str = ""
    repo: str = ""


class Message(BaseModel):
    """A single persisted turn."""

    id: int | None = None
    user_id: str
    conversation_id: str | None = None
    role: Role
    content: str
    created_at: str


class HistoryResponse(BaseModel):
    user_id: str
    messages: list[Message]
