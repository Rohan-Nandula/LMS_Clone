from flask import Flask
from datetime import timedelta, datetime

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'your_secret_key'
    app.permanent_session_lifetime = timedelta(minutes=30)

    from .ta_routes import ta_endpoints
    app.register_blueprint(ta_endpoints)

    return app