from flask import Blueprint, render_template
from flask_login import login_required, current_user
from datetime import datetime

from app.models import db, Chat, Message, User
from flask_socketio import emit, join_room

chat_bp = Blueprint("chat", __name__)

# ---------------- OPEN CHAT ----------------
@chat_bp.route("/chat/<int:property_id>/<int:agent_id>")
@login_required
def open_chat(property_id, agent_id):

    chat = Chat.query.filter(
        ((Chat.user_id == current_user.id) & (Chat.agent_id == agent_id)) |
        ((Chat.user_id == agent_id) & (Chat.agent_id == current_user.id)),
        Chat.property_id == property_id
    ).first()

    if not chat:
        chat = Chat(
            user_id=current_user.id,
            agent_id=agent_id,
            property_id=property_id
        )
        db.session.add(chat)
        db.session.commit()

    messages = Message.query.filter_by(chat_id=chat.id)\
        .order_by(Message.created_at.asc()).all()

    # mark as read
    for msg in messages:
        if msg.sender_id != current_user.id:
            msg.is_read = True

    db.session.commit()

    chat_agent = User.query.get(agent_id)

    return render_template(
        "chat.html",
        chat=chat,
        messages=messages,
        chat_agent=chat_agent
    )


# ---------------- INBOX / MESSAGES ----------------
@chat_bp.route("/messages")
@login_required
def inbox():

    chats = Chat.query.filter(
        (Chat.user_id == current_user.id) |
        (Chat.agent_id == current_user.id)
    ).order_by(Chat.id.desc()).all()

    for chat in chats:

        chat.last_message = Message.query.filter_by(chat_id=chat.id)\
            .order_by(Message.created_at.desc()).first()

        chat.unread_count = Message.query.filter_by(
            chat_id=chat.id,
            is_read=False
        ).filter(Message.sender_id != current_user.id).count()

        chat.other_user = User.query.get(
            chat.agent_id if chat.user_id == current_user.id else chat.user_id
        )

    return render_template("chat_inbox.html", chats=chats)


# ---------------- SOCKET EVENTS ----------------
def register_socket_events(socketio):

    @socketio.on("join_chat")
    def handle_join(data):
        chat_id = data.get("chat_id")
        join_room(f"chat_{chat_id}")

    @socketio.on("send_message")
    def handle_send_message(data):

        chat_id = data.get("chat_id")
        text = data.get("text")

        if not text or text.strip() == "":
            return

        chat = Chat.query.get(chat_id)

        if not chat:
            return

        if current_user.id not in [chat.user_id, chat.agent_id]:
            return

        msg = Message(
            chat_id=chat_id,
            sender_id=current_user.id,
            text=text,
            is_read=False,
            created_at=datetime.utcnow()
        )

        db.session.add(msg)
        db.session.commit()

        emit("receive_message", {
            "chat_id": chat_id,
            "sender_id": current_user.id,
            "text": text,
            "created_at": msg.created_at.strftime("%H:%M")
        }, room=f"chat_{chat_id}")