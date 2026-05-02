from flask import Blueprint, render_template, request, redirect, url_for, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from app.models import db, User
from app.utils.helpers import generate_avatar


auth_bp = Blueprint("auth", __name__)


# ---------------- REGISTER ----------------
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        existing_user = User.query.filter_by(email=request.form["email"]).first()
        if existing_user:
            return "Email already exists"

        # phone handling
        country_code = request.form.get("country_code", "")
        phone_number = request.form.get("phone", "")

        phone_number = phone_number.lstrip("0").replace(" ", "")
        full_phone = f"{country_code}{phone_number}"

        new_user = User(
            name=request.form["name"],
            email=request.form["email"],
            phone=full_phone,
            password=generate_password_hash(request.form["password"]),
            location=request.form.get("location"),
            experience=request.form.get("experience")
        )

        # generate avatar
        new_user.profile_image = generate_avatar(new_user.name)

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("auth.login"))

    return render_template("register.html")


# ---------------- LOGIN ----------------

from flask_login import login_user

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):

            login_user(user)  # 🔥 THIS is the real login

            # ✅ FIX: role-based redirect
            if user.is_admin:
                return redirect(url_for("admin.admin_dashboard"))
            else:
                return redirect(url_for("property.home"))

        return "Invalid email or password"

    return render_template("login.html")


# ---------------- LOGOUT ----------------
@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("property.home"))


# ---------------- DASHBOARD ----------------
@auth_bp.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")