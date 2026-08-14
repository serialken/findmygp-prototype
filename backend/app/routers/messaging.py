from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal, get_db
from app.deps import get_current_user
from app.models import CarrierProfile, Conversation, Message, User
from app.schemas import ConversationOut, MessageCreate, MessageOut
from app.security import decode_token
from app.websockets.manager import messaging_manager

router = APIRouter(tags=["messaging"])


def _is_participant(conversation: Conversation, user: User) -> bool:
    is_client = conversation.client_id == user.id
    is_carrier = user.carrier_profile is not None and conversation.carrier_id == user.carrier_profile.id
    return is_client or is_carrier or user.role.value == "admin"


async def _get_authorized_conversation(db: AsyncSession, conversation_id: str, user: User) -> Conversation:
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation introuvable")
    if not _is_participant(conversation, user):
        raise HTTPException(status_code=403, detail="Accès non autorisé à cette conversation")
    return conversation


@router.get("/messaging/conversations", response_model=List[ConversationOut])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role.value == "carrier" and current_user.carrier_profile:
        result = await db.execute(
            select(Conversation).where(Conversation.carrier_id == current_user.carrier_profile.id)
        )
    else:
        result = await db.execute(select(Conversation).where(Conversation.client_id == current_user.id))
    return result.scalars().all()


@router.post("/messaging/conversations/{carrier_id}", response_model=ConversationOut, status_code=201)
async def get_or_create_conversation(
    carrier_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    carrier_result = await db.execute(select(CarrierProfile).where(CarrierProfile.id == carrier_id))
    if not carrier_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Transporteur introuvable")

    result = await db.execute(
        select(Conversation).where(
            Conversation.client_id == current_user.id, Conversation.carrier_id == carrier_id
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation:
        return conversation

    conversation = Conversation(client_id=current_user.id, carrier_id=carrier_id)
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


@router.get("/messaging/conversations/{conversation_id}/messages", response_model=List[MessageOut])
async def list_messages(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conversation = await _get_authorized_conversation(db, conversation_id, current_user)
    result = await db.execute(
        select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at)
    )
    return result.scalars().all()


@router.post("/messaging/conversations/{conversation_id}/messages", response_model=MessageOut, status_code=201)
async def send_message(
    conversation_id: str,
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conversation = await _get_authorized_conversation(db, conversation_id, current_user)
    sender_role = "carrier" if (
        current_user.carrier_profile is not None and conversation.carrier_id == current_user.carrier_profile.id
    ) else "client"

    message = Message(
        conversation_id=conversation.id,
        sender_user_id=current_user.id,
        sender_role=sender_role,
        text=payload.text,
        delivered_at=datetime.utcnow(),
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)

    await messaging_manager.broadcast(
        conversation.id,
        {
            "type": "new_message",
            "id": message.id,
            "sender_user_id": message.sender_user_id,
            "sender_role": message.sender_role,
            "text": message.text,
            "created_at": message.created_at.isoformat(),
            "delivered_at": message.delivered_at.isoformat() if message.delivered_at else None,
        },
    )
    return message


@router.websocket("/ws/messaging/{conversation_id}")
async def messaging_ws(websocket: WebSocket, conversation_id: str, token: str):
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await websocket.close(code=4401)
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
        conversation = result.scalar_one_or_none()
        result_user = await db.execute(
            select(User).where(User.id == payload.get("sub")).options(selectinload(User.carrier_profile))
        )
        user = result_user.scalar_one_or_none()
        if not conversation or not user or not _is_participant(conversation, user):
            await websocket.close(code=4403)
            return

    await messaging_manager.connect(conversation_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive / ignored client pings
    except WebSocketDisconnect:
        messaging_manager.disconnect(conversation_id, websocket)
