from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from app.models import db, Property, User, Favorite, Chat, Message

from app.services.properties import property_score
from app.services.recommendations import get_recommendations
api_bp = Blueprint("api", __name__)


# ---------------- HEALTH CHECK ----------------
@api_bp.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


# ---------------- PROPERTIES LIST ----------------
@api_bp.route("/properties", methods=["GET"])
def get_properties():

    properties = Property.query.filter_by(approved=True).all()

    data = [
        {
            "id": p.id,
            "title": p.title,
            "price": p.price,
            "location": p.location,
            "bedrooms": p.bedrooms,
            "type": p.property_type,
            "featured": p.featured,
            "image": p.images[0] if p.images else None
        }
        for p in properties
    ]

    return jsonify({"data": data})


# ---------------- SINGLE PROPERTY ----------------
@api_bp.route("/properties/<int:property_id>", methods=["GET"])
def get_property(property_id):

    p = Property.query.get_or_404(property_id)

    return jsonify({
        "id": p.id,
        "title": p.title,
        "description": p.description,
        "price": p.price,
        "location": p.location,
        "bedrooms": p.bedrooms,
        "images": p.images,
        "featured": p.featured,
        "agent_id": p.user_id
    })


# ---------------- RECOMMENDATIONS ----------------
@api_bp.route("/recommendations", methods=["GET"])
@login_required
def recommendations():

    props = get_recommendations(current_user.id)

    return jsonify({
        "data": [
            {
                "id": p.id,
                "title": p.title,
                "price": p.price,
                "location": p.location,
                "image": p.images[0] if p.images else None
            }
            for p in props
        ]
    })


# ---------------- FAVORITE PROPERTY ----------------
@api_bp.route("/favorite/<int:property_id>", methods=["POST"])
@login_required
def favorite_property(property_id):

    fav = Favorite.query.filter_by(
        user_id=current_user.id,
        property_id=property_id
    ).first()

    if fav:
        return jsonify({"message": "Already favorited"}), 200

    fav = Favorite(
        user_id=current_user.id,
        property_id=property_id
    )

    db.session.add(fav)
    db.session.commit()

    return jsonify({"message": "Added to favorites"})


# ---------------- REMOVE FAVORITE ----------------
@api_bp.route("/unfavorite/<int:property_id>", methods=["POST"])
@login_required
def unfavorite_property(property_id):

    fav = Favorite.query.filter_by(
        user_id=current_user.id,
        property_id=property_id
    ).first()

    if not fav:
        return jsonify({"message": "Not found"}), 404

    db.session.delete(fav)
    db.session.commit()

    return jsonify({"message": "Removed from favorites"})


# ---------------- USER PROFILE ----------------
@api_bp.route("/me", methods=["GET"])
@login_required
def get_profile():

    user = current_user

    return jsonify({
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "is_verified": user.is_verified,
        "subscription": user.subscription_plan
    })


# ---------------- MY PROPERTIES ----------------
@api_bp.route("/my-properties", methods=["GET"])
@login_required
def my_properties():

    properties = Property.query.filter_by(user_id=current_user.id).all()

    return jsonify({
        "data": [
            {
                "id": p.id,
                "title": p.title,
                "price": p.price,
                "location": p.location,
                "featured": p.featured
            }
            for p in properties
        ]
    })


# ---------------- CHAT LIST ----------------
@api_bp.route("/chats", methods=["GET"])
@login_required
def get_chats():

    chats = Chat.query.filter(
        (Chat.user_id == current_user.id) |
        (Chat.agent_id == current_user.id)
    ).all()

    data = []

    for c in chats:

        last_msg = Message.query.filter_by(chat_id=c.id)\
            .order_by(Message.created_at.desc()).first()

        data.append({
            "chat_id": c.id,
            "property_id": c.property_id,
            "last_message": last_msg.text if last_msg else None,
            "last_time": last_msg.created_at if last_msg else None
        })

    return jsonify({"data": data})


# ---------------- CHAT MESSAGES ----------------
@api_bp.route("/chats/<int:chat_id>/messages", methods=["GET"])
@login_required
def get_messages(chat_id):

    messages = Message.query.filter_by(chat_id=chat_id)\
        .order_by(Message.created_at.asc()).all()

    return jsonify({
        "data": [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "text": m.text,
                "created_at": m.created_at
            }
            for m in messages
        ]
    })


# ---------------- SEND MESSAGE ----------------
@api_bp.route("/chats/<int:chat_id>/send", methods=["POST"])
@login_required
def send_message(chat_id):

    data = request.json
    text = data.get("text")

    if not text:
        return jsonify({"error": "Message required"}), 400

    msg = Message(
        chat_id=chat_id,
        sender_id=current_user.id,
        text=text
    )

    db.session.add(msg)
    db.session.commit()

    return jsonify({
        "message": "sent",
        "data": {
            "id": msg.id,
            "text": msg.text
        }
    })


# ---------------- SEARCH ----------------
@api_bp.route("/search", methods=["GET"])
def search():

    q = request.args.get("q")

    if not q:
        return jsonify({"data": []})

    properties = Property.query.filter(
        (Property.title.ilike(f"%{q}%")) |
        (Property.location.ilike(f"%{q}%"))
    ).all()

    return jsonify({
        "data": [
            {
                "id": p.id,
                "title": p.title,
                "price": p.price,
                "location": p.location,
                "image": p.images[0] if p.images else None
            }
            for p in properties
        ]
    })