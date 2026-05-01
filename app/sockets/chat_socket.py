def init_socket_events(socketio, db):

    @socketio.on("connect")
    def handle_connect():
        print("User connected")

    @socketio.on("disconnect")
    def handle_disconnect():
        print("User disconnected")