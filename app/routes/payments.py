from flask import Blueprint, request, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, timedelta, timezone
import requests
import os

from app.models import db, Property, PaymentLog, User
from app.services.payment_service import initialize_payment
from app.services.payment_constants import (
    PAYMENT_FEATURE,
    PAYMENT_VERIFICATION,
    PAYMENT_SUBSCRIPTION
)

payments_bp = Blueprint("payments", __name__)


# =========================
# BOOST PROPERTY PAYMENT
# =========================
@payments_bp.route("/pay/boost/<int:property_id>")
@login_required
def boost_property(property_id):

    prop = Property.query.get_or_404(property_id)
    now = datetime.now(timezone.utc)

    # prevent double boost
    if prop.featured and prop.featured_until and prop.featured_until > now:
        return redirect(url_for("property.property_detail", id=property_id))

    res = initialize_payment(
        email=current_user.email,
        amount=3000,
        callback_url=url_for("payments.verify_payment", _external=True),
        metadata={
            "type": PAYMENT_FEATURE,
            "property_id": property_id
        }
    )

    if not res.get("status") or "data" not in res:
        return "Payment initialization failed", 500

    return redirect(res["data"]["authorization_url"])


# =========================
# VERIFY PAYMENT (PAYSTACK CALLBACK)
# =========================
@payments_bp.route("/verify-payment")
def verify_payment():

    reference = request.args.get("reference")
    if not reference:
        return "Missing reference", 400

    # prevent duplicate processing
    existing = PaymentLog.query.filter_by(reference=reference).first()
    if existing:
        return redirect(url_for("property.home"))

    PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")

    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}

    response = requests.get(url, headers=headers)
    res = response.json()

    if not res.get("status"):
        return "Invalid payment", 400

    data = res.get("data", {})
    metadata = data.get("metadata", {})

    payment_type = metadata.get("type")
    property_id = metadata.get("property_id")

    amount = data.get("amount", 0) / 100
    status = data.get("status")

    # =========================
    # FIND USER SAFELY (NOT current_user)
    # =========================
    user_email = data.get("customer", {}).get("email")
    user = User.query.filter_by(email=user_email).first()

    if not user:
        return "User not found", 400

    # =========================
    # SAVE PAYMENT LOG
    # =========================
    log = PaymentLog(
        user_id=user.id,
        reference=reference,
        amount=amount,
        payment_type=payment_type,
        status=status,
        property_id=property_id
    )

    db.session.add(log)

    # =========================
    # PROCESS SUCCESS PAYMENTS
    # =========================
    if status == "success":

        # BOOST PROPERTY
        if payment_type == PAYMENT_FEATURE and property_id:
            prop = Property.query.get(property_id)
            if prop:
                prop.featured = True
                prop.featured_until = datetime.now(timezone.utc) + timedelta(days=7)

        # VERIFY USER
        elif payment_type == PAYMENT_VERIFICATION:
            user.verification_status = "verified"

        # SUBSCRIPTION
        elif payment_type == PAYMENT_SUBSCRIPTION:
            user.subscription_plan = "pro"
            user.subscription_expiry = datetime.now(timezone.utc) + timedelta(days=30)

    db.session.commit()

    return redirect(url_for("property.home"))




@payments_bp.route("/pay/subscription")
@login_required
def pay_subscription():

    callback = url_for("payments.verify_payment", _external=True)

    res = initialize_payment(
        email=current_user.email,
        amount=15000,
        callback_url=callback,
        metadata={
            "type": "subscription",
            "plan": "pro"
        }
    )

    if not res.get("status"):
        return "Payment failed", 500

    return redirect(res["data"]["authorization_url"])