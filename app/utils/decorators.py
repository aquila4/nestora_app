from functools import wraps
from flask import session, redirect, url_for, flash, request


def login_required(f):
    """
    Ensure user is logged in before accessing route
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    Allow only admin users
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for('auth.login'))

        if session.get('role') != 'admin':
            flash("Access denied. Admins only.", "danger")
            return redirect(url_for('main.index'))

        return f(*args, **kwargs)
    return decorated_function


def agent_required(f):
    """
    Allow only agents (for property listings etc.)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for('auth.login'))

        if session.get('role') not in ['agent', 'admin']:
            flash("Only agents can access this page.", "danger")
            return redirect(url_for('main.index'))

        return f(*args, **kwargs)
    return decorated_function