from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

import config

db = SQLAlchemy()
migrate = Migrate()


def create_app():
    app = Flask(__name__)
    app.config.from_object(config)
    app.config['SECRET_KEY'] = 'your_secret_key'  # 비밀 키 설정

    # ORM
    db.init_app(app)
    migrate.init_app(app, db)
    from project import models

    # 블루프린트
    from .views import main_views, auth_views,work_views
    app.register_blueprint(main_views.bp)
    app.register_blueprint(auth_views.bp)
    app.register_blueprint(work_views.bp)

    return app