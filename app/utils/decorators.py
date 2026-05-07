from functools import wraps
from flask import abort
from flask_login import current_user, login_required


# =========================
# LOGIN REQUIRED (CLEAN)
# =========================
def login_required_custom(f):
    """
    Protect routes for logged-in users only
    (Flask-Login version, NOT session-based)
    """
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated_function


# =========================
# ADMIN ONLY
# =========================
def admin_required(f):
    """
    Allow only admin users
    """
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):

        if not current_user.is_authenticated:
            abort(401)

        if not current_user.is_admin:
            abort(403)   # Forbidden (NOT redirect loop)

        return f(*args, **kwargs)

    return decorated_function


# =========================
# AGENT OR ADMIN
# =========================
def agent_required(f):
    """
    Allow agents and admins
    """
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):

        if not current_user.is_authenticated:
            abort(401)

        # assumes you have a "role" field
        if current_user.role not in ["agent", "admin"]:
            abort(403)

        return f(*args, **kwargs)

    return decorated_function