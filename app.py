import os
import json
import requests
import hmac
import hashlib

from flask import Flask, render_template, request, redirect, url_for, session, send_file
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_migrate import Migrate
from flask_mail import Mail, Message as MailMessage
from flask_cors import CORS

from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from sqlalchemy import func
from datetime import datetime, timedelta, timezone
from functools import wraps

from PIL import Image, ImageDraw, ImageFont

from config import Config
from models import db, User, Property, PropertyHistory, PaymentLog, Favorite, UserActivity, Chat, Message
from routes.api import api

import cloudinary.uploader

import hashlib
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)


db.init_app(app)
migrate = Migrate(app, db)
app.register_blueprint(api, url_prefix="/api")
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = "nestoratechnology@gmail.com"
app.config["MAIL_PASSWORD"] = "dnrk qdek hvdq wevl"  # NOT your real password
app.config["MAIL_DEFAULT_SENDER"] = "Nestora <nestoratechnology@gmail.com>"

mail = Mail(app)

app.config["UPLOAD_FOLDER"] = "static/uploads"



os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")

PAYMENT_VERIFICATION = "verification"
PAYMENT_FEATURE = "feature"
PAYMENT_SUBSCRIPTION = "subscription"

# ---------------- LOGIN ----------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

def upload_to_cloudinary(file):
    result = cloudinary.uploader.upload(
        file,
        quality="auto",        # auto compression
        fetch_format="auto"    # modern formats (webp/avif)
    )
    return result["secure_url"]

from datetime import datetime, timezone

def property_score(p):
    score = 0
    now = datetime.now(timezone.utc)

    # ⭐ Featured boost
    if p.featured:
        score += 50

    # 🔥 Featured until (safe timezone handling)
    if p.featured_until:
        featured_until = p.featured_until

        if featured_until.tzinfo is None:
            featured_until = featured_until.replace(tzinfo=timezone.utc)

        days_left = (featured_until - now).days

        if days_left > 0:
            score += min(40, days_left * 5)

    # 👀 Engagement
    score += (p.views or 0) * 0.4

    # ❤️ Favorites
    if hasattr(p, "favorites_count") and p.favorites_count:
        score += p.favorites_count * 2

    # 📍 Location boost
    popular_cities = ["lagos", "abuja", "ilorin", "ibadan"]

    if p.location:
        location = p.location.lower()
        if any(city in location for city in popular_cities):
            score += 25

    # 💰 Price logic
    if p.price:
        if 500000 <= p.price <= 5000000:
            score += 20
        elif p.price < 200000:
            score += 10
        elif p.price > 20000000:
            score -= 10

    # 🏠 Bedrooms
    if p.bedrooms in [1, 2, 3]:
        score += 15

    # 📅 Freshness
    if p.created_at:
        created_at = p.created_at

        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        days_old = (now - created_at).days

        if days_old < 3:
            score += 25
        elif days_old < 7:
            score += 15
        elif days_old < 30:
            score += 5
        else:
            score -= 5

    return score
def get_recommendations(user_id):

    try:
        activities = UserActivity.query.filter_by(user_id=user_id).all()
    except Exception:
        activities = []

    # 🔁 fallback if new user
    if not activities:
        return Property.query.order_by(Property.featured.desc()).limit(8).all()

    # 🧠 Collect behavior data
    city_count = {}
    prices = []
    bedrooms = []

    for a in activities:
        city_count[a.city] = city_count.get(a.city, 0) + 1
        if a.price:
            prices.append(a.price)
        if a.bedrooms:
            bedrooms.append(a.bedrooms)

    # 📍 most visited city
    favorite_city = max(city_count, key=city_count.get) if city_count else None

    # 💰 average price preference
    avg_price = sum(prices) / len(prices) if prices else 0

    # 🏠 most viewed bedroom type
    preferred_bedrooms = max(set(bedrooms), key=bedrooms.count) if bedrooms else None

    properties = Property.query.filter_by(approved=True).all()

    def score(p):

        s = property_score(p)

        # 🧠 personalization boost
        if favorite_city and p.location and favorite_city.lower() in p.location.lower():
            s += 50

        if avg_price and p.price and abs(p.price - avg_price) < avg_price * 0.3:
            s += 30

        if preferred_bedrooms and p.bedrooms == preferred_bedrooms:
            s += 20

        return s

    return sorted(properties, key=score, reverse=True)[:8]
    


def is_subscription_active(user):
    if user.subscription_plan == "free":
        return False
    
    if user.subscription_expiry is None:
        return False

    return user.subscription_expiry > datetime.now(timezone.utc)

def expire_boosts():
    properties = Property.query.filter_by(featured=True).all()

    for p in properties:
        if p.featured_until and p.featured_until < datetime.now(timezone.utc):
            p.featured = False
            p.featured_paid = False

    db.session.commit()


def generate_avatar(name):
    if not name:
        name = "User"

    initials = "".join([n[0] for n in name.split()][:2]).upper()

    # create unique filename per user
    filename = hashlib.md5(name.encode()).hexdigest() + ".png"
    path = os.path.join("static/avatars", filename)

    # return if already exists (IMPORTANT for speed)
    if os.path.exists(path):
        return filename

    # create image
    img = Image.new('RGB', (200, 200), color=(13, 138, 188))  # blue background
    draw = ImageDraw.Draw(img)

    # text (center)
    try:
        font = ImageFont.truetype("arial.ttf", 80)
    except:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), initials, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text(((200 - w) / 2, (200 - h) / 2), initials, fill="white", font=font)

    os.makedirs("static/avatars", exist_ok=True)
    img.save(path)

    return filename

def send_receipt_email(user, amount, payment_type, reference):

    msg = MailMessage(
        subject="Payment Receipt - Nestora",
        recipients=[user.email]
    )

    msg.html = f"""
    <h2>Payment Successful 🎉</h2>

    <p>Hello <b>{user.name}</b>,</p>

    <p>Your payment was successful.</p>

    <ul>
        <li><b>Amount:</b> ₦{amount}</li>
        <li><b>Type:</b> {payment_type}</li>
        <li><b>Reference:</b> {reference}</li>
    </ul>

    <p>Thank you for using Nestora.</p>
    """

    mail.send(msg)



def initialize_payment(email, amount, callback_url, metadata):
    url = "https://api.paystack.co/transaction/initialize"

    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "email": email,
        "amount": int(amount * 100),  # convert to kobo
        "callback_url": callback_url,
        "metadata": metadata
    }

    response = requests.post(url, json=data, headers=headers)
    return response.json()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------- ADMIN DECORATOR ----------------
def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            return "Access Denied", 403
        return func(*args, **kwargs)
    return wrapper

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/api/properties")
def api_properties():
    properties = Property.query.filter_by(approved=True).all()

    return {
        "data": [
            {
                "id": p.id,
                "title": p.title,
                "price": p.price,
                "location": p.location,
                "image": p.images[0] if p.images else ""
            }
            for p in properties
        ]
    }


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/how-it-works")
def how_it_works():
    return render_template("how_it_works.html")


@app.route("/careers")
def careers():
    return render_template("careers.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

@app.route("/help-center")
def help_center():
    return render_template("help_center.html")


@app.route("/contact")
def contact():
    return render_template("contact_us.html")




# ---------------- HOME ----------------
@app.route("/home")
def home():
    search = request.args.get("search")
    filter_type = request.args.get("filter")

    # 🧠 SMART FILTERS
    city = request.args.get("city")
    min_price = request.args.get("min_price")
    max_price = request.args.get("max_price")
    bedrooms = request.args.get("bedrooms")

    now = datetime.now(timezone.utc)

    # 🔁 EXPIRE SUBSCRIPTIONS (OPTIMIZED)
    User.query.filter(
        User.subscription_expiry != None,
        User.subscription_expiry < now
    ).update({
        User.subscription_plan: "free",
        User.subscription_expiry: None
    })

    # 🔥 EXPIRE BOOSTED PROPERTIES (OPTIMIZED)
    Property.query.filter(
        Property.featured == True,
        Property.featured_until != None,
        Property.featured_until < now
    ).update({
        Property.featured: False,
        Property.featured_until: None
    })

    db.session.commit()

    # 🧠 BASE QUERY
    query = Property.query.filter(Property.approved == True)

    # 🔍 SEARCH FILTER
    if search:
        query = query.filter(
            (Property.title.ilike(f"%{search}%")) |
            (Property.location.ilike(f"%{search}%"))
        )

    # 🏙 CITY FILTER (INCLUDES ILORIN)
    if city:
        query = query.filter(Property.location.ilike(f"%{city}%"))

    # 💰 PRICE FILTER
    if min_price:
        query = query.filter(Property.price >= int(min_price))

    if max_price:
        query = query.filter(Property.price <= int(max_price))

    # 🛏 BEDROOM FILTER
    if bedrooms:
        if bedrooms == "3+":
            query = query.filter(Property.bedrooms >= 3)
        else:
            query = query.filter(Property.bedrooms == int(bedrooms))

    # 🏠 TYPE FILTER
    if filter_type == "sale":
        query = query.filter(Property.property_type == "sale")

    elif filter_type == "rent":
        query = query.filter(Property.property_type == "rent")

    elif filter_type == "featured":
        query = query.filter(Property.featured == True)

    elif filter_type == "verified":
        query = query.join(User).filter(User.verification_status == "verified")

    properties = query.all()

    # 🚀 RANKING SYSTEM (AIRBNB STYLE)
    properties = sorted(
        properties,
        key=lambda p: property_score(p),
        reverse=True
    )

    # 🧠 REAL RECOMMENDATION SYSTEM
    if current_user.is_authenticated:
        recommended = get_recommendations(current_user.id)
    else:
        recommended = properties[:6]

    return render_template(
        "home.html",
        properties=properties,
        recommended=recommended,
        now=now
    )
# ---------------- PROPERTY DETAILS ----------------
@app.route("/property/<int:id>")
def property_detail(id):

    property = Property.query.get_or_404(id)

    if current_user.is_authenticated:

        activity = UserActivity(
            user_id=current_user.id,
            property_id=property.id,
            action="view",
            city=property.location,
            price=property.price,
            bedrooms=property.bedrooms
        )

        db.session.add(activity)
        db.session.commit()

    return render_template("property.html", property=property)

@app.route("/track-whatsapp/<int:property_id>")
def track_whatsapp(property_id):

    if current_user.is_authenticated:

        property = Property.query.get(property_id)

        activity = UserActivity(
            user_id=current_user.id,
            property_id=property_id,
            action="whatsapp",
            city=property.location,
            price=property.price,
            bedrooms=property.bedrooms
        )

        db.session.add(activity)
        db.session.commit()

    return redirect("https://wa.me/2348105208988")

# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        print("USER:", user)
        print("PASSWORD INPUT:", password)

        if user:
            print("HASH IN DB:", user.password)

        if user and check_password_hash(user.password, password):

            login_user(user)

            # 👇 SIMPLE AND CLEAN
            if user.is_admin:
                return redirect(url_for("admin_dashboard"))

            return redirect(url_for("home"))

        return "Invalid email or password"

    return render_template("login.html")
# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("home"))


# ---------------- ADD PROPERTY ----------------
@app.route("/list-property/step1", methods=["GET", "POST"])
@login_required
def list_step1():
    if request.method == "POST":
        session["listing"] = {}
        session["listing"]["property_type"] = request.form["property_type"]
        return redirect(url_for("list_step2"))

    return render_template("list_step1.html")


@app.route("/list-property/step2", methods=["GET", "POST"])
@login_required
def list_step2():
    if request.method == "POST":

        if "listing" not in session:
            session["listing"] = {}

        session["listing"]["location"] = request.form.get("location")
        session.modified = True  # 🔥 ADD THIS

        return redirect(url_for("list_step3"))

    return render_template("list_step2.html")

@app.route("/list-property/step3", methods=["GET", "POST"])
@login_required
def list_step3():

    if "listing" not in session:
        session["listing"] = {}

    if request.method == "POST":

        # save basic details
        session["listing"]["title"] = request.form.get("title")
        session["listing"]["description"] = request.form.get("description")

        property_type = session["listing"].get("property_type")

        # 🔥 ONLY save bedrooms if NOT land
        if property_type != "land":
            session["listing"]["bedrooms"] = request.form.get("bedrooms")
        else:
            session["listing"]["bedrooms"] = None

        session.modified = True

        return redirect(url_for("list_step4"))

    return render_template("list_step3.html")

@app.route("/list-property/step4", methods=["GET", "POST"])
@login_required
def list_step4():

    if request.method == "POST":

        files = request.files.getlist("images")

        image_urls = []

        for file in files[:10]:  # LIMIT 10 IMAGES
            if file and file.filename != "":

                result = cloudinary.uploader.upload(file)
                image_urls.append(result["secure_url"])

        # store Cloudinary URLs instead of filenames
        session["listing"]["images"] = image_urls
        session.modified = True

        return redirect(url_for("list_step5"))

    return render_template("list_step4.html")

@app.route("/list-property/step5", methods=["GET", "POST"])
@login_required
def list_step5():

    if "listing" not in session:
        session["listing"] = {}

    if request.method == "POST":

        session["listing"]["price"] = request.form.get("price")
        session.modified = True

        # 🔥 IMPORTANT FIX: redirect to review
        return redirect(url_for("list_review"))

    return render_template("list_step5.html")

@app.route("/list-property/review", methods=["GET", "POST"])
@login_required
def list_review():

    data = session.get("listing")

    if request.method == "POST":

        new_property = Property(
            title=data.get("title"),
            location=data.get("location"),
            price=data.get("price"),
            description=data.get("description"),
            images=data.get("images"),  # ✅ NEW
            bedrooms=data.get("bedrooms"),
            property_type=data.get("property_type"),
            user_id=current_user.id,
            approved=True
        )

        db.session.add(new_property)
        db.session.commit()

        session.pop("listing", None)

        return redirect(url_for("home"))

    return render_template("list_review.html", data=data)
# ---------------- PAYSTACK ----------------
@app.route("/pay/<int:property_id>")
@login_required
def pay(property_id):

    property = Property.query.get_or_404(property_id)

    url = "https://api.paystack.co/transaction/initialize"

    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "email": current_user.email,
        "amount": 5000 * 100,
        "callback_url": url_for("verify_payment", property_id=property.id, _external=True)
    }

    response = requests.post(url, json=data, headers=headers)
    res = response.json()

    return redirect(res["data"]["authorization_url"])


# ---------------- VERIFY PAYMENT ----------------


# ---------------- ADMIN ROUTES ----------------

# FEATURE PROPERTY
@app.route("/admin/property/feature/<int:property_id>")
@login_required
@admin_required
def admin_feature_property(property_id):
    property = Property.query.get_or_404(property_id)
    property.featured = True
    db.session.commit()
    return redirect(url_for("admin_dashboard"))

# DELETE PROPERTY
@app.route("/admin/property/delete/<int:property_id>")
@login_required
@admin_required
def admin_delete_property(property_id):

    property = Property.query.get_or_404(property_id)

    UserActivity.query.filter_by(property_id=property_id).delete()
    Favorite.query.filter_by(property_id=property_id).delete()

    db.session.delete(property)
    db.session.commit()

    return redirect(url_for("admin_dashboard"))

# APPROVE PROPERTY
@app.route("/admin/property/approve/<int:property_id>")
@login_required
@admin_required
def admin_approve_property(property_id):
    property = Property.query.get_or_404(property_id)
    property.approved = True
    db.session.commit()
    return redirect(url_for("admin_dashboard"))

# REJECT PROPERTY
@app.route("/admin/property/reject/<int:property_id>")
@login_required
@admin_required
def admin_reject_property(property_id):
    property = Property.query.get_or_404(property_id)
    property.approved = False
    db.session.commit()
    return redirect(url_for("admin_dashboard"))

    # VERIFY USER
@app.route("/admin/user/verify/<int:user_id>")
@login_required
@admin_required
def verify_user(user_id):
    user = User.query.get_or_404(user_id)
    user.verification_status = "verified"
    db.session.commit()
    return redirect(url_for("admin_dashboard"))

# REJECT USER
@app.route("/admin/user/reject/<int:user_id>")
@login_required
@admin_required
def reject_user(user_id):
    user = User.query.get_or_404(user_id)
    user.verification_status = "rejected"
    db.session.commit()
    return redirect(url_for("admin_dashboard"))

@app.route("/edit-property/<int:property_id>", methods=["GET", "POST"])
@login_required
def edit_property(property_id):
    property = Property.query.get_or_404(property_id)

    if property.user_id != current_user.id:
        return "Unauthorized", 403

    if request.method == "POST":

        # ✅ SAVE HISTORY
        history = PropertyHistory(
            property_id=property.id,
            title=property.title,
            price=property.price,
            location=property.location,
            description=property.description,
            image=property.images[0] if property.images else None
        )
        db.session.add(history)
            # 🔍 COMPARE OLD VS NEW (ADD THIS HERE)
        new_price = request.form["price"]
        if str(property.price) != new_price:
                print("price changed")

        # ✅ UPDATE PROPERTY
        property.title = request.form["title"]
        property.location = request.form["location"]
        property.price = request.form["price"]
        property.description = request.form["description"]

        file = request.files["image"]

        if file and file.filename != "":
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            property.image = filename

        # 🔥 FORCE RE-APPROVAL
        property.approved = False
        property.featured = False

        db.session.commit()

        return redirect(url_for("my_properties"))

    return render_template("edit_property.html", property=property)


@app.route("/property-history/<int:property_id>")
@login_required
def property_history(property_id):

    property = Property.query.get_or_404(property_id)

    # only owner or admin
    if property.user_id != current_user.id and not current_user.is_admin:
        return "Unauthorized", 403

    history = PropertyHistory.query.filter_by(property_id=property_id)\
        .order_by(PropertyHistory.edited_at.desc()).all()

    return render_template("property_history.html", history=history)

@app.route("/property/restore/<int:history_id>")
@login_required
@admin_required  # or owner check if you prefer
def restore_property(history_id):

    history = PropertyHistory.query.get_or_404(history_id)
    property = Property.query.get_or_404(history.property_id)

    property.title = history.title
    property.price = history.price
    property.location = history.location
    property.description = history.description
    property.image = history.image
    

    db.session.commit()

    return redirect(url_for("admin_dashboard"))



@app.route("/agent/<int:user_id>")
def agent_profile(user_id):
    agent = User.query.get_or_404(user_id)

    properties = Property.query.filter_by(
        user_id=agent.id,
        approved=True
    ).order_by(Property.featured.desc()).all()

    return render_template(
        "agent_profile.html",
        agent=agent,
        properties=properties
    )
@app.route("/verify-payment")
@login_required
def verify_payment():

    reference = request.args.get("reference")
    if not reference:
        return "Missing reference", 400

    # ✅ prevent duplicate processing
    existing = PaymentLog.query.filter_by(reference=reference).first()
    if existing:
        return redirect(url_for("home"))

    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"
    }

    response = requests.get(url, headers=headers)
    res = response.json()

    # ❌ safety check
    if not res.get("status"):
        return "Invalid response", 400

    data = res.get("data")
    if not data:
        return "No transaction data", 400
    print("🔥 PAYMENT CALLBACK HIT")
    print("DATA:", data)

    metadata = data.get("metadata", {})
    payment_type = metadata.get("type")
    property_id = metadata.get("property_id")
    print("🔥 PAYMENT TYPE:", payment_type)
    print("🔥 PROPERTY ID:", property_id)

    amount = data.get("amount", 0) / 100
    status = data.get("status")

    # 🧾 GET USER FROM PAYSTACK
    user_email = data.get("customer", {}).get("email")
    user = User.query.filter_by(email=user_email).first()

    # ⚠️ DEBUG CHECK (PUT IT HERE)
    if not user:
        print("⚠️ User not found for payment email:", user_email)
        return "User mismatch", 400
  
    # 🧾 SAVE PAYMENT LOG (ALWAYS)
    payment_log = PaymentLog(
        user_id=user.id if user else None,
        reference=reference,
        amount=amount,
        payment_type=payment_type,
        status=status,
        property_id=property_id
    )

    db.session.add(payment_log)


    # ❌ FAILED PAYMENT
    if status != "success":
        db.session.commit()
        return "Payment failed", 400

    # 🔐 VERIFY AGENT
    if payment_type == PAYMENT_VERIFICATION:
        current_user.is_verified = True
        current_user.verification_status = "verified"
        current_user.verification_paid = True
    
    # ⭐ BOOST PROPERTY
    elif payment_type == PAYMENT_FEATURE and property_id:
        prop = Property.query.get(property_id)
        if prop:
            prop.featured = True
            prop.featured_paid = True
            prop.featured_until = datetime.now(timezone.utc) + timedelta(days=7)
            print("🔥 BOOST TRIGGERED")

    # 📦 SUBSCRIPTION
    elif payment_type == PAYMENT_SUBSCRIPTION:
        current_user.subscription_plan = "pro"
        current_user.subscription_expiry = datetime.now(timezone.utc) + timedelta(days=30)

    db.session.commit()

    # 📧 SEND RECEIPT EMAIL (SAFE)
    try:
        send_receipt_email(
            current_user,
            amount,
            payment_type,
            reference
        )
    except Exception as e:
        print("🔥 REAL ERROR:", e)
        return str(e), 500

    return redirect(url_for("home"))


@app.route("/paystack/webhook", methods=["POST"])
def paystack_webhook():

    try:
        # 🔐 1. RAW BODY FIRST
        body = request.get_data()

        # 🔐 2. VERIFY SIGNATURE
        signature = request.headers.get("X-Paystack-Signature")

        computed = hmac.new(
            PAYSTACK_SECRET_KEY.encode(),
            body,
            hashlib.sha512
        ).hexdigest()

        if not signature or signature != computed:
            print("❌ INVALID SIGNATURE")
            return "invalid signature", 400

        # 🔥 3. PARSE PAYLOAD ONLY AFTER SECURITY CHECK
        payload = json.loads(body.decode("utf-8"))

        print("🔥 WEBHOOK RECEIVED:", payload)

        event = payload.get("event")

        if event != "charge.success":
            return "ignored", 200

        data = payload.get("data", {})

        reference = data.get("reference")
        amount = data.get("amount", 0) / 100
        status = data.get("status")

        metadata = data.get("metadata", {})
        payment_type = metadata.get("type")
        property_id = metadata.get("property_id")

        if property_id:
            property_id = int(property_id)

        print("🔥 PAYMENT TYPE:", payment_type)
        print("🔥 PROPERTY ID:", property_id)

        customer = data.get("customer") or {}
        user_email = customer.get("email")

        print("EVENT:", event)
        print("EMAIL:", user_email)
        print("REFERENCE:", reference)

        if not user_email:
            return "missing email", 400

        user = User.query.filter_by(email=user_email).first()
        if not user:
            return "user not found", 400

        # 🚫 prevent duplicate processing
        existing = PaymentLog.query.filter_by(reference=reference).first()
        if existing:
            return "duplicate", 200

        # 🧾 SAVE PAYMENT
        payment_log = PaymentLog(
            user_id=user.id,
            reference=reference,
            amount=amount,
            payment_type=payment_type,
            status=status,
            payment_metadata={
        "property_id": property_id,
        "raw": data  # optional (very useful for debugging)
    }
)

        db.session.add(payment_log)

        # 🔐 BUSINESS LOGIC
        if payment_type == "verification":
            user.is_verified = True
            user.verification_status = "verified"

        elif payment_type == "feature" and property_id:
            prop = Property.query.get(property_id)
            if prop:
                prop.featured = True
                prop.featured_until = datetime.now(timezone.utc) + timedelta(days=7)

        elif payment_type == "subscription":
            user.subscription_plan = "pro"
            user.subscription_expiry = datetime.now(timezone.utc) + timedelta(days=30)

        db.session.commit()

        print("✅ PAYMENT PROCESSED SUCCESSFULLY")
        return "success", 200

    except Exception as e:
        db.session.rollback()
        print("🔥 WEBHOOK ERROR TYPE:", type(e).__name__)
        print("🔥 WEBHOOK ERROR:", str(e))
        return "error", 500



    

@app.route('/admin/verification')
@login_required
def verification_requests():

    if not current_user.is_admin:
        return "Unauthorized"

    users = User.query.filter_by(verification_status="pending").all()

    return render_template("admin_verification.html", users=users)

@app.route('/admin/approve/<int:user_id>')
@login_required
def approve(user_id):

    if not current_user.is_admin:
        return "Unauthorized"

    user = User.query.get(user_id)
    user.is_verified = True
    user.verification_status = "verified"
    db.session.commit()

    return redirect('/admin/verification')


@app.route('/request-verification', methods=['POST'])
@login_required
def request_verification():

    file = request.files.get('document')

    if not file:
        return "No file uploaded", 400

    filename = secure_filename(file.filename)

    upload_folder = os.path.join(os.getcwd(), 'private_uploads')
    os.makedirs(upload_folder, exist_ok=True)

    file_path = os.path.join(upload_folder, filename)
    file.save(file_path)

    current_user.verification_doc = filename
    current_user.verification_status = "pending"

    db.session.commit()

    return redirect(url_for('agent_profile', user_id=current_user.id))




   



@app.route("/admin/view-doc/<int:user_id>")
@login_required
def view_doc(user_id):

    if not current_user.is_admin:
        return "Unauthorized", 403

    user = User.query.get_or_404(user_id)

    file_path = os.path.join("private_uploads", user.verification_doc)

    return send_file(file_path)
   

@app.route("/admin/refund/<int:payment_id>")
@login_required
@admin_required
def refund_payment(payment_id):

    payment = PaymentLog.query.get_or_404(payment_id)

    # call Paystack refund API
    url = "https://api.paystack.co/refund"

    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "transaction": payment.reference
    }

    response = requests.post(url, json=data, headers=headers)
    res = response.json()

    if res.get("status"):
        payment.status = "refunded"
        db.session.commit()
        return "Refund successful"

    return "Refund failed", 400

@app.route("/pay/verify-agent")
@login_required
def pay_verify_agent():

    callback = url_for("verify_payment", _external=True)

    res = initialize_payment(
        email=current_user.email,
        amount=5000,
        callback_url=callback,
        metadata={
            "type": PAYMENT_VERIFICATION
        }
    )

    return redirect(res["data"]["authorization_url"])

@app.route("/pay/boost/<int:property_id>")
@login_required
def boost_property(property_id):
    property = Property.query.get_or_404(property_id)

    # ✅ Check subscription
    if current_user.subscription_expiry:
        expiry = current_user.subscription_expiry

        # make datetime safe (remove timezone if exists)
        if expiry.tzinfo is not None:
            expiry = expiry.replace(tzinfo=None)

        # check if expired
        if expiry < datetime.utcnow():
            return "Upgrade to Pro subscription to boost properties"

    else:
        return "You need a subscription to boost properties"

    # ✅ Payment
    callback = url_for("verify_payment", _external=True)

    res = initialize_payment(
        email=current_user.email,
        amount=3000,
        callback_url=callback,
        metadata={
            "type": "feature",
            "property_id": property_id
        }
    )

    return redirect(res["data"]["authorization_url"])


@app.route("/pay/subscription")
@login_required
def pay_subscription():

    callback = url_for("verify_payment", _external=True)

    res = initialize_payment(
        email=current_user.email,
        amount=15000,
        callback_url=callback,
        metadata={
            "type": PAYMENT_SUBSCRIPTION,
            "plan": "pro"
        }
    )

    return redirect(res["data"]["authorization_url"])


@app.route("/admin")
@login_required
@admin_required
def admin_dashboard():

    properties = Property.query.order_by(Property.id.desc()).all()

    total_properties = Property.query.count()
    featured = Property.query.filter_by(featured=True).count()

    # 💰 TOTAL REVENUE
    total_revenue = db.session.query(
        func.sum(PaymentLog.amount)
    ).filter(PaymentLog.status == "success").scalar() or 0

    # 📊 REVENUE BY TYPE
    verification_revenue = db.session.query(
        func.sum(PaymentLog.amount)
    ).filter(PaymentLog.payment_type == PAYMENT_VERIFICATION).scalar() or 0

    feature_revenue = db.session.query(
        func.sum(PaymentLog.amount)
    ).filter(PaymentLog.payment_type == PAYMENT_FEATURE).scalar() or 0

    subscription_revenue = db.session.query(
        func.sum(PaymentLog.amount)
    ).filter(PaymentLog.payment_type == PAYMENT_SUBSCRIPTION).scalar() or 0

    # 👤 TOP USERS
    top_users = db.session.query(
        PaymentLog.user_id,
        func.sum(PaymentLog.amount).label("total")
    ).group_by(PaymentLog.user_id)\
     .order_by(func.sum(PaymentLog.amount).desc())\
     .limit(5).all()

    user_ids = [u.user_id for u in top_users]

    top_users_map = {
        u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()
    }

    top_users_data = [
        {
            "user": top_users_map.get(u.user_id),
            "total": u.total
        }
        for u in top_users
    ]

    # 📅 RECENT PAYMENTS
    recent_payments = PaymentLog.query.order_by(
        PaymentLog.created_at.desc()
    ).limit(10).all()

    # 🔐 ✅ ADD THIS (VERIFICATION USERS)
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

        # ✅ PASS THIS
        verification_users=verification_users
    )

@app.route("/favorite/<int:property_id>")
@login_required
def add_favorite(property_id):

    fav = Favorite.query.filter_by(
        user_id=current_user.id,
        property_id=property_id
    ).first()

    if not fav:
        fav = Favorite(
            user_id=current_user.id,
            property_id=property_id
        )
        db.session.add(fav)
        db.session.commit()

    return redirect(request.referrer or url_for("home"))


@app.route("/unfavorite/<int:property_id>")
@login_required
def remove_favorite(property_id):

    fav = Favorite.query.filter_by(
        user_id=current_user.id,
        property_id=property_id
    ).first()

    if fav:
        db.session.delete(fav)
        db.session.commit()

    return redirect(request.referrer or url_for("home"))






# ---------------- INIT DB ----------------


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        # check if user already exists
        existing_user = User.query.filter_by(email=request.form["email"]).first()

        if existing_user:
            return "Email already exists"

        new_user = User(
            name=request.form["name"],
            email=request.form["email"],
            phone=request.form["phone"],
            password=generate_password_hash(request.form["password"]), # ✅ FIXED
            location=request.form.get("location"),
            experience=request.form.get("experience")
        )

        # 🔥 generate avatar here
        new_user.profile_image = generate_avatar(new_user.name)

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html")
@app.route("/dashboard")
@login_required
def dashboard():
    properties = Property.query.filter_by(user_id=current_user.id).all()
    return render_template("dashboard.html", properties=properties)

@app.route("/delete/<int:property_id>")
@login_required
def delete_property(property_id):
    property = Property.query.get_or_404(property_id)

    # prevent deleting others' property
    if property.user_id != current_user.id:
        return "Unauthorized", 403

    db.session.delete(property)
    db.session.commit()

    return redirect(url_for("dashboard"))



@app.route("/my-properties")
@login_required
def my_properties():

    properties = Property.query.filter_by(user_id=current_user.id).order_by(Property.id.desc()).all()

    return render_template("my_properties.html", properties=properties)


@app.route("/chat/<int:property_id>/<int:agent_id>")
@login_required
def open_chat(property_id, agent_id):

    chat = Chat.query.filter_by(
        user_id=current_user.id,
        agent_id=agent_id,
        property_id=property_id
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

    # 🔥 MARK AS READ
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

@app.route("/send_message/<int:chat_id>", methods=["POST"])
@login_required
def send_message(chat_id):

    text = request.form.get("message")

    # ❌ prevent empty messages
    if not text or text.strip() == "":
        return redirect(request.referrer)

    # 🔒 ensure chat exists
    chat = Chat.query.get_or_404(chat_id)

    # 🔒 security check (VERY IMPORTANT)
    if current_user.id not in [chat.user_id, chat.agent_id]:
        return redirect("/")

    # 💬 create message
    msg = Message(
        chat_id=chat_id,
        sender_id=current_user.id,
        text=text,
        is_read=False  # 🔥 required for unread badge system
    )

    db.session.add(msg)
    db.session.commit()

    return redirect(request.referrer)






# ---------------- RUN ----------------
import os

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080))
    )