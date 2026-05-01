from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from flask_login import login_required, current_user
from datetime import datetime, timezone

from app.models import db, Property, User, UserActivity
from app.services.properties import property_score
from app.services.recommendations import get_recommendations
from app.utils.helpers import compress_image

from werkzeug.utils import secure_filename
import cloudinary.uploader

from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import PropertyHistory
import os

from app.models import db, Property

property_bp = Blueprint("property", __name__)


# ---------------- LANDING ----------------
@property_bp.route("/")
def landing():
    return render_template("landing.html")


# ---------------- HOME ----------------
@property_bp.route("/home")
def home():

    search = request.args.get("search")
    filter_type = request.args.get("filter")

    city = request.args.get("city")
    min_price = request.args.get("min_price")
    max_price = request.args.get("max_price")
    bedrooms = request.args.get("bedrooms")

    now = datetime.now(timezone.utc)

    query = Property.query.filter(Property.approved == True)

    if search:
        query = query.filter(
            (Property.title.ilike(f"%{search}%")) |
            (Property.location.ilike(f"%{search}%"))
        )

    if city:
        query = query.filter(Property.location.ilike(f"%{city}%"))

    if min_price:
        query = query.filter(Property.price >= int(min_price))

    if max_price:
        query = query.filter(Property.price <= int(max_price))

    if bedrooms:
        if bedrooms == "3+":
            query = query.filter(Property.bedrooms >= 3)
        else:
            query = query.filter(Property.bedrooms == int(bedrooms))

    if filter_type == "sale":
        query = query.filter(Property.property_type == "sale")

    elif filter_type == "rent":
        query = query.filter(Property.property_type == "rent")

    elif filter_type == "featured":
        query = query.filter(Property.featured == True)

    elif filter_type == "verified":
        query = query.join(User).filter(User.verification_status == "verified")

    properties = query.all()
    properties = sorted(properties, key=property_score, reverse=True)

    recommended = get_recommendations(current_user.id) if current_user.is_authenticated else properties[:6]

    return render_template(
        "home.html",
        properties=properties,
        recommended=recommended,
        now=now
    )


@property_bp.route("/agent/<int:user_id>")
def agent_profile(user_id):

    user = User.query.get_or_404(user_id)

    properties = Property.query.filter_by(
        user_id=user.id,
        approved=True
    ).order_by(Property.id.desc()).all()

    return render_template(
        "agent_profile.html",
        user=user,
        properties=properties
    )
# ---------------- PROPERTY DETAIL ----------------
@property_bp.route("/property/<int:id>")
def property_detail(id):

    prop = Property.query.get_or_404(id)
    agent = db.session.get(User, prop.user_id)

    prop.is_boost_active = (
        prop.featured and prop.featured_until and prop.featured_until > datetime.now(timezone.utc)
    )

    if current_user.is_authenticated:

        activity = UserActivity(
            user_id=current_user.id,
            property_id=prop.id,
            action="view",
            city=prop.location,
            price=prop.price,
            bedrooms=prop.bedrooms
        )

        db.session.add(activity)
        db.session.commit()

    return render_template("property.html", property=prop, agent=agent, now=datetime.now(timezone.utc))


# ---------------- WHATSAPP TRACK ----------------
@property_bp.route("/track-whatsapp/<int:property_id>")
@login_required
def track_whatsapp(property_id):

    prop = Property.query.get_or_404(property_id)

    activity = UserActivity(
        user_id=current_user.id,
        property_id=property_id,
        action="whatsapp",
        city=prop.location,
        price=prop.price,
        bedrooms=prop.bedrooms
    )

    db.session.add(activity)
    db.session.commit()

    return redirect("https://wa.me/2348105208988")

@property_bp.route("/my-properties")
@login_required
def my_properties():
    properties = Property.query.filter_by(user_id=current_user.id)\
        .order_by(Property.id.desc()).all()

    return render_template("my_properties.html", properties=properties)



# ---------------- STATIC PAGES ----------------
@property_bp.route("/contact")
def contact():
    return render_template("contact.html")


@property_bp.route("/help")
def help_center():
    return render_template("help.html")


@property_bp.route("/privacy")
def privacy():
    return render_template("privacy.html")


@property_bp.route("/how-it-works")
def how_it_works():
    return render_template("how_it_works.html")


@property_bp.route("/careers")
def careers():
    return render_template("careers.html")


@property_bp.route("/terms")
def terms():
    return render_template("terms.html")


@property_bp.route("/about")
def about():
    return render_template("about.html")


# ---------------- LISTING FLOW ----------------

@property_bp.route("/list-property/step1", methods=["GET", "POST"])
@login_required
def list_step1():
    if request.method == "POST":
        session["listing"] = session.get("listing", {})
        session["listing"]["property_type"] = request.form["property_type"]
        session.modified = True
        return redirect(url_for("property.list_step2"))

    return render_template("list_step1.html")


@property_bp.route("/list-property/step2", methods=["GET", "POST"])
@login_required
def list_step2():
    if request.method == "POST":
        session.setdefault("listing", {})
        session["listing"]["location"] = request.form.get("location")
        session.modified = True

        return redirect(url_for("property.list_step3"))

    return render_template("list_step2.html")


@property_bp.route("/list-property/step3", methods=["GET", "POST"])
@login_required
def list_step3():
    session.setdefault("listing", {})

    if request.method == "POST":
        session["listing"]["title"] = request.form.get("title")
        session["listing"]["description"] = request.form.get("description")

        if session["listing"].get("property_type") != "land":
            session["listing"]["bedrooms"] = request.form.get("bedrooms")
        else:
            session["listing"]["bedrooms"] = None

        session.modified = True
        return redirect(url_for("property.list_step4"))

    return render_template("list_step3.html")


@property_bp.route("/list-property/step4", methods=["GET", "POST"])
@login_required
def list_step4():
    session.setdefault("listing", {})

    if request.method == "POST":

        files = request.files.getlist("images")
        image_urls = []

        for file in files[:10]:
            if file and file.filename:
                compressed_file = compress_image(file)
                result = cloudinary.uploader.upload(compressed_file)
                image_urls.append(result["secure_url"])

        session["listing"]["images"] = image_urls
        session.modified = True

        return redirect(url_for("property.list_step5"))

    return render_template("list_step4.html")


@property_bp.route("/list-property/step5", methods=["GET", "POST"])
@login_required
def list_step5():
    session.setdefault("listing", {})

    if request.method == "POST":
        session["listing"]["price"] = request.form.get("price")
        session.modified = True

        return redirect(url_for("property.list_review"))

    return render_template("list_step5.html")


@property_bp.route("/list-property/review", methods=["GET", "POST"])
@login_required
def list_review():

    data = session.get("listing")

    if request.method == "POST":

        new_property = Property(
            title=data.get("title"),
            location=data.get("location"),
            price=data.get("price"),
            description=data.get("description"),
            images=data.get("images"),
            bedrooms=data.get("bedrooms"),
            property_type=data.get("property_type"),
            user_id=current_user.id,
            approved=True
        )

        db.session.add(new_property)
        db.session.commit()

        session.pop("listing", None)

        return redirect(url_for("property.home"))

    return render_template("list_review.html", data=data)





# ---------------- EDIT PROPERTY ----------------
@property_bp.route("/property/edit/<int:property_id>", methods=["GET", "POST"])
@login_required
def edit_property(property_id):

    prop = Property.query.get_or_404(property_id)

    # 🔐 Security check
    if prop.user_id != current_user.id:
        return "Unauthorized", 403

    if request.method == "POST":

        prop.title = request.form["title"]
        prop.location = request.form["location"]
        prop.price = request.form["price"]
        prop.description = request.form["description"]

        files = request.files.getlist("images")

        new_images = prop.images or []

        for file in files:
            if file and file.filename:

                compressed_file = compress_image(file)
                result = cloudinary.uploader.upload(compressed_file)

                new_images.append(result["secure_url"])

        prop.images = new_images

        db.session.commit()

        flash("Property updated successfully", "success")
        return redirect(url_for("property.home"))

    return render_template("edit_property.html", property=prop)
# ---------------- ADMIN ROUTES ----------------


# ---------------- PROFILE UPDATE ----------------
@property_bp.route("/update-profile", methods=["POST"])
@login_required
def update_profile():

    file = request.files.get("profile_image")

    if not file or file.filename == "":
        flash("No image selected")
        return redirect(request.referrer or url_for("property.home"))

    try:
        result = cloudinary.uploader.upload(file)
        image_url = result["secure_url"]

        user = User.query.get(current_user.id)
        user.profile_image = image_url

        db.session.commit()

        flash("Profile updated successfully")

    except Exception as e:
        print(e)
        flash("Image upload failed")

    return redirect(request.referrer or url_for("property.home"))


# ---------------- PROPERTY HISTORY ----------------
@property_bp.route("/property-history/<int:property_id>")
@login_required
def property_history(property_id):

    prop = Property.query.get_or_404(property_id)

    # SECURITY CHECK
    if prop.user_id != current_user.id:
        return "Unauthorized", 403

    history = PropertyHistory.query.filter_by(
        property_id=property_id
    ).order_by(PropertyHistory.id.desc()).all()

    return render_template(
        "property_history.html",
        property=prop,
        history=history
    )


# ---------------- RESTORE PROPERTY ----------------
@property_bp.route("/property/restore/<int:history_id>")
@login_required
def restore_property(history_id):

    history = PropertyHistory.query.get_or_404(history_id)
    prop = Property.query.get_or_404(history.property_id)

    # SECURITY CHECK
    if prop.user_id != current_user.id:
        return "Unauthorized", 403

    # restore data
    prop.title = history.title
    prop.location = history.location
    prop.price = history.price
    prop.description = history.description

    if getattr(history, "image", None):
        prop.images = history.image

    db.session.commit()

    flash("Property restored successfully", "success")

    return redirect(url_for("property.property_detail", id=prop.id))