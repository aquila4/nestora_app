from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


# ---------------- USER MODEL ----------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)

    # BASIC INFO
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    phone = db.Column(db.String(20))
    password = db.Column(db.String(255))

    # ROLE
    is_admin = db.Column(db.Boolean, default=False)

    # PROFILE
    profile_image = db.Column(db.String(255), default="default-avatar.png")
    location = db.Column(db.String(200))
    experience = db.Column(db.String(200))

    # SUBSCRIPTION SYSTEM
    subscription_plan = db.Column(db.String(20), default="free")  # free / pro
    subscription_expiry = db.Column(db.DateTime, nullable=True)

    # ================= VERIFICATION SYSTEM (CLEAN) =================
    verification_status = db.Column(
        db.String(20),
        default="unverified"
    )
    # unverified | pending | verified | rejected

    verification_doc = db.Column(
        db.String(255),
        nullable=True
    )

    verification_note = db.Column(
        db.Text,
        nullable=True
    )

    verified_at = db.Column(
        db.DateTime,
        nullable=True
    )
    # ---------------- PROPERTY MODEL ----------------
class Property(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(200))
    price = db.Column(db.Float)
    location = db.Column(db.String(200))
    description = db.Column(db.Text)
    images = db.Column(db.JSON)
    bedrooms = db.Column(db.Integer)

    property_type = db.Column(db.String(20))

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user = db.relationship("User", backref="properties")

    approved = db.Column(db.Boolean, default=False)

    featured = db.Column(db.Boolean, default=False)
    featured_until = db.Column(db.DateTime, nullable=True)

    views = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    

class PropertyHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    property_id = db.Column(
    db.Integer,
    db.ForeignKey("property.id", ondelete="CASCADE")
)
    
    title = db.Column(db.String(200))
    price = db.Column(db.Float)
    location = db.Column(db.String(200))
    description = db.Column(db.Text)
    image = db.Column(db.String(300))

    edited_at = db.Column(db.DateTime, default=datetime.utcnow)


class PaymentLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    user = db.relationship("User", backref="payments")

    reference = db.Column(db.String(100), unique=True)
    amount = db.Column(db.Float)

    payment_type = db.Column(db.String(50))  # verification / feature / subscription
    status = db.Column(db.String(20))        # success / failed / pending

    property_id = db.Column(db.Integer)

    payment_metadata = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    property_id = db.Column(db.Integer, db.ForeignKey("property.id"))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="favorites")
    property = db.relationship("Property", backref="favorites")

class UserActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    property_id = db.Column(
    db.Integer,
    db.ForeignKey('property.id', ondelete="CASCADE")
)

    action = db.Column(db.String(50))  # view, click, whatsapp
    city = db.Column(db.String(100))
    price = db.Column(db.Integer)
    bedrooms = db.Column(db.Integer)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Chat(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    agent_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    property_id = db.Column(
        db.Integer,
        db.ForeignKey("property.id", ondelete="CASCADE"),
        nullable=False
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    messages = db.relationship(
        "Message",
        backref="chat",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    chat_id = db.Column(
        db.Integer,
        db.ForeignKey("chat.id", ondelete="CASCADE"),
        nullable=False
    )

    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    is_read = db.Column(db.Boolean, default=False)