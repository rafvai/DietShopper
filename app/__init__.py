import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

db = SQLAlchemy()

def create_app():
    app = Flask(__name__, template_folder="templates")
    
    # Load the secret key from environment variables
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret_key')

    # Load the database URI from environment variables, with a fallback to the SQLite database path
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///C:/Users/Raf/Desktop/DietShopper/ultimate.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Set the session type
    app.config["SESSION_PERMANENT"] = False
    app.config["SESSION_TYPE"] = "filesystem"
    
    # Initialize extensions
    db.init_app(app)
    Session(app)

    # Create database tables
    with app.app_context():
        from .models import Users, DayTypes, MealTypes, Foods, DietPlans, Meals
        db.create_all()

    # Register blueprints
    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .specialist_routes import specialist_bp
    app.register_blueprint(specialist_bp)

    return app
