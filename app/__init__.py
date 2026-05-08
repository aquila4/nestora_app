import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
from flask_socketio import SocketIO

from config import Config
from app.models import db, User

login_manager = LoginManager()
migrate = Migrate()
mail = Mail()
socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")

def create_app():

    app = Flask(__name__)

    # =========================
    # SITEMAP ROUTE (FIXED)
    # =========================
    @app.route("/sitemap.xml")
    def sitemap():
        return "OK"

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

    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    login_manager.init_app(app)
    CORS(app)
    socketio.init_app(app)

    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        if not user_id:
            return None
        try:
            return db.session.get(User, int(user_id))
        except Exception:
            return None

    @app.route("/favicon.ico")
    def favicon():
        return send_from_directory(
            app.static_folder,
            "favicon.ico",
            mimetype="image/vnd.microsoft.icon"
        )

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

    from app.sockets.chat_socket import init_socket_events
    init_socket_events(socketio, db)

    return app