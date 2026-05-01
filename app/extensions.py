from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_mail import Mail
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_cors import CORS

# ---------------- CORE EXTENSIONS ----------------

db = SQLAlchemy()

socketio = SocketIO()

mail = Mail()

login_manager = LoginManager()

migrate = Migrate()

cors = CORS()


# ---------------- INIT FUNCTION ----------------

def init_extensions(app):

    """
    Initialize all Flask extensions in one place.
    This keeps create_app() clean and scalable.
    """

    # DATABASE
    db.init_app(app)

    # MIGRATIONS
    migrate.init_app(app, db)

    # LOGIN MANAGER
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.session_protection = "strong"

    # SOCKET IO
    socketio.init_app(
        app,
        cors_allowed_origins="*",
        async_mode="threading"
    )

    # MAIL
    mail.init_app(app)

    # CORS
    cors.init_app(app)


# ---------------- LOGIN LOADER ----------------

@login_manager.user_loader
def load_user(user_id):

    from app.models import User  # avoid circular import
    return User.query.get(int(user_id))