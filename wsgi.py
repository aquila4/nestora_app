import eventlet
eventlet.monkey_patch()

from app import create_app, socketio

app = create_app()
socketio.init_app(app)

application = app  # IMPORTANT for gunicorn

if __name__ == "__main__":
    socketio.run(app, debug=True)