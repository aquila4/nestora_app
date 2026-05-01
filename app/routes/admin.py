from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import func

from app.models import (
    db, User, Property, PaymentLog,
    Favorite, UserActivity
)

from app.utils.decorators import admin_required
from app.services.payment_constants import (
    PAYMENT_VERIFICATION,
    PAYMENT_FEATURE,
    PAYMENT_SUBSCRIPTION
)

admin_bp = Blueprint("admin", __name__)


# ---------------- DASHBOARD ----------------
@admin_bp.route("/admin")
@admin_required
@login_required
def admin_dashboard():

    properties = Property.query.order_by(Property.id.desc()).all()

    total_properties = Property.query.count()
    featured = Property.query.filter_by(featured=True).count()

    # revenue
    total_revenue = db.session.query(
        func.sum(PaymentLog.amount)
    ).filter(PaymentLog.status == "success").scalar() or 0

    verification_revenue = db.session.query(
        func.sum(PaymentLog.amount)
    ).filter(PaymentLog.payment_type == PAYMENT_VERIFICATION).scalar() or 0

    feature_revenue = db.session.query(
        func.sum(PaymentLog.amount)
    ).filter(PaymentLog.payment_type == PAYMENT_FEATURE).scalar() or 0

    subscription_revenue = db.session.query(
        func.sum(PaymentLog.amount)
    ).filter(PaymentLog.payment_type == PAYMENT_SUBSCRIPTION).scalar() or 0

    # top users
    top_users = db.session.query(
        PaymentLog.user_id,
        func.sum(PaymentLog.amount).label("total")
    ).group_by(PaymentLog.user_id)\
     .order_by(func.sum(PaymentLog.amount).desc())\
     .limit(5).all()

    user_ids = [u.user_id for u in top_users]

    users_map = {
        u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()
    }

    top_users_data = [
        {
            "user": users_map.get(u.user_id),
            "total": u.total
        }
        for u in top_users
    ]

    # recent payments
    recent_payments = PaymentLog.query.order_by(
        PaymentLog.created_at.desc()
    ).limit(10).all()

    # verification requests
    verification_users = User.query.filter_by(
        verification_status="pending"
    ).all()

    return render_template(
        "admin.html",
        properties=properties,
        total=total_properties,
        featured=featured,
        total_revenue=total_revenue,
        verification_revenue=verification_revenue,
        feature_revenue=feature_revenue,
        subscription_revenue=subscription_revenue,
        top_users=top_users_data,
        recent_payments=recent_payments,
        verification_users=verification_users
    )


# ---------------- PROPERTY MODERATION ----------------

@admin_bp.route("/admin/property/feature/<int:property_id>")
@login_required
@admin_required
def feature_property(property_id):

    property = Property.query.get_or_404(property_id)
    property.featured = True

    db.session.commit()
    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/admin/property/delete/<int:property_id>")
@login_required
@admin_required
def delete_property(property_id):

    property = Property.query.get_or_404(property_id)

    # cleanup related data
    UserActivity.query.filter_by(property_id=property_id).delete()
    Favorite.query.filter_by(property_id=property_id).delete()

    db.session.delete(property)
    db.session.commit()

    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/admin/property/approve/<int:property_id>")
@login_required
@admin_required
def approve_property(property_id):

    property = Property.query.get_or_404(property_id)
    property.approved = True

    db.session.commit()
    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/admin/property/reject/<int:property_id>")
@login_required
@admin_required
def reject_property(property_id):

    property = Property.query.get_or_404(property_id)
    property.approved = False

    db.session.commit()
    return redirect(url_for("admin.admin_dashboard"))


# ---------------- USER VERIFICATION ----------------

@admin_bp.route("/admin/user/verify/<int:user_id>")
@login_required
@admin_required
def verify_user(user_id):

    user = User.query.get_or_404(user_id)

    user.verification_status = "verified"
    user.is_verified = True

    db.session.commit()
    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/admin/user/reject/<int:user_id>")
@login_required
@admin_required
def reject_user(user_id):

    user = User.query.get_or_404(user_id)

    user.verification_status = "rejected"

    db.session.commit()
    return redirect(url_for("admin.admin_dashboard"))


# ---------------- VERIFICATION PAGE ----------------

@admin_bp.route("/admin/verification")
@login_required
@admin_required
def verification_requests():

    users = User.query.filter_by(
        verification_status="pending"
    ).all()

    return render_template(
        "admin_verification.html",
        users=users
    )


@admin_bp.route("/admin/approve/<int:user_id>")
@login_required
@admin_required
def approve_verification(user_id):

    user = User.query.get_or_404(user_id)

    user.is_verified = True
    user.verification_status = "verified"

    db.session.commit()

    return redirect(url_for("admin.verification_requests"))


# ---------------- VIEW USER DOCUMENT ----------------

@admin_bp.route("/admin/view-doc/<int:user_id>")
@login_required
@admin_required
def view_document(user_id):

    user = User.query.get_or_404(user_id)

    file_path = f"private_uploads/{user.verification_doc}"

    return file_path  # (you can upgrade to send_file later)