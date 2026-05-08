import os
from flask import Flask, send_from_directory, Response
from flask_cors import CORS
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
from flask_socketio import SocketIO

from config import Config
from app.models import db, User, Property   # ✅ IMPORTANT FIX

login_manager = LoginManager()
migrate = Migrate()
mail = Mail()
socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")


def create_app():

    app = Flask(__name__)

    # =========================
    # STATIC
    # =========================
    app.static_folder = os.path.join(app.root_path, "static")
    app.static_url_path = "/static"

    app.config.from_object(Config)

    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=False,
        SESSION_PERMANENT=True
    )

    # INIT EXTENSIONS
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    login_manager.init_app(app)
    CORS(app)
    socketio.init_app(app)

    login_manager.login_view = "auth.login"

    # =========================
    # USER LOADER
    # =========================
    @login_manager.user_loader
    def load_user(user_id):
        if not user_id:
            return None
        try:
            return db.session.get(User, int(user_id))
        except Exception:
            return None

    # =========================
    # FAVICON
    # =========================
    @app.route("/favicon.ico")
    def favicon():
        return send_from_directory(
            app.static_folder,
            "favicon.ico",
            mimetype="image/vnd.microsoft.icon"
        )

    # =========================
    # SITEMAP (FIXED)
    # =========================
    @app.route("/sitemap.xml")
    def sitemap():
        properties = Property.query.filter_by(approved=True).all()

        urls = [
            "https://www.usenestora.com/",
            "https://www.usenestora.com/home",
            "https://www.usenestora.com/list-property/step1",
        ]

        for p in properties:
            if p.slug:
                urls.append(f"https://www.usenestora.com/property/{p.slug}")

        xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
"""

        for url in urls:
            xml += f"""
    <url>
        <loc>{url}</loc>
        <changefreq>daily</changefreq>
        <priority>0.8</priority>
    </url>
"""

        xml += "\n</urlset>"

        return Response(xml, mimetype="application/xml")

    # =========================
    # BLUEPRINTS
    # =========================
    from app.routes.auth import auth_bp
    from app.routes.property import property_bp
    from app.routes.chat import chat_bp
    from app.routes.admin import admin_bp
    from app.routes.payments import payments_bp
    from app.routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(property_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    # SOCKET
    from app.sockets.chat_socket import init_socket_events
    init_socket_events(socketio, db)

    return app