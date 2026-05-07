from app import create_app, socketio

app = create_app()

# 🚀 Production entry point (used by gunicorn)
application = app

# 👇 Add this for local running
if __name__ == "__main__":
    socketio.run(app, debug=True)