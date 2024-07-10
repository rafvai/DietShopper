# app/__init__.py

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session

db = SQLAlchemy()

def create_app():
    app = Flask(__name__, template_folder="templates")  # Ensure correct template folder path
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///C:/Users/Raf/Desktop/DietShopper/ultimate.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config["SESSION_PERMANENT"] = False
    app.config["SESSION_TYPE"] = "filesystem"

    db.init_app(app)
    Session(app)

    with app.app_context():
        from .models import Users, DayTypes, MealTypes, Foods, DietPlans, Meals
        db.create_all()

    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    # import and register specialist blueprint
    from.specialist_routes import specialist_bp
    app.register_blueprint(specialist_bp)

    return app
