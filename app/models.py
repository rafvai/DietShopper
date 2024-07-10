from app import db  
from sqlalchemy.sql import func

class Users(db.Model):
    __tablename__ = 'Users'

    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=func.now())

class DayTypes(db.Model):
    __tablename__ = 'DayTypes'

    day_type_id = db.Column(db.Integer, primary_key=True)
    day_name = db.Column(db.String(255), unique=True, nullable=False)

class MealTypes(db.Model):
    __tablename__ = 'MealTypes'

    meal_type_id = db.Column(db.Integer, primary_key=True)
    meal_name = db.Column(db.String(255), unique=True, nullable=False)

class Foods(db.Model):
    __tablename__ = 'Foods'

    food_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    calories = db.Column(db.Integer)
    protein = db.Column(db.DECIMAL(5, 2))
    carbs = db.Column(db.DECIMAL(5, 2))
    fats = db.Column(db.DECIMAL(5, 2))

class DietPlans(db.Model):
    __tablename__ = 'DietPlans'

    dietplan_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('Users.user_id'))
    name = db.Column(db.String(255), nullable=True)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=func.now())

class Meals(db.Model):
    __tablename__ = 'Meals'

    meal_id = db.Column(db.Integer, primary_key=True)
    dietplan_id = db.Column(db.Integer, db.ForeignKey('DietPlans.dietplan_id'))
    day_type_id = db.Column(db.Integer, db.ForeignKey('DayTypes.day_type_id'))
    meal_type_id = db.Column(db.Integer, db.ForeignKey('MealTypes.meal_type_id'))
    food_id = db.Column(db.Integer, db.ForeignKey('Foods.food_id'))
    quantity = db.Column(db.Integer)

class Measurement(db.Model):
    __tablename__= "Measurement"

    measurement_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("Users.user_id"))
    height = db.Column(db.DECIMAL(5, 2), nullable=False)
    weight = db.Column(db.DECIMAL(5, 2), nullable=False)
    BMI = db.Column(db.DECIMAL(5, 2))
    body_fat = db.Column(db.DECIMAL(5, 2))
    fat_free_bw = db.Column(db.DECIMAL(5, 2))
    subcutaneous_fat = db.Column(db.DECIMAL(5, 2))
    visceral_fat = db.Column(db.Integer)
    body_water = db.Column(db.DECIMAL(5, 2))
    skeletal_muscle = db.Column(db.DECIMAL(5, 2))
    muscle_mass = db.Column(db.DECIMAL(5, 2))
    bone_mass = db.Column(db.DECIMAL(5, 2))
    protein = db.Column(db.DECIMAL(5, 2))
    BMR = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=func.now())

class Substitutes(db.Model):
    __tablename__="Substitutes"

    substitution_id = db.Column(db.Integer, primary_key=True)
    food_id = db.Column(db.Integer, db.ForeignKey("Foods.food_id"), nullable = True)
    substitute_food_id = db.Column(db.Integer, db.ForeignKey("Foods.food_id"), nullable = True)

class Specialists(db.Model):
    __tablename__="Specialists"

    specialist_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=func.now())

class Patients(db.Model):
    __tablename__="Patients"

    patient_id = db.Column(db.Integer, primary_key=True)
    specialist_id = db.Column(db.Integer, db.ForeignKey("Specialists.specialist_id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("Users.user_id"), nullable=False)
    created_at = db.Column(db.DateTime, default=func.now())

