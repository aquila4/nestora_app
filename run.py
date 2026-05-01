from app import create_app, socketio

app = create_app()

# 🚀 Production entry point (used by gunicorn)
application = app