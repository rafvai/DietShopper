from datetime import datetime
from flask import request, redirect, url_for, session

def convert_quantity_to_grams(quantity_str):
    """Convert quantity string (e.g., '100gr') to integer grams."""
    if quantity_str.endswith('gr'):
        return int(quantity_str[:-2])
    # Add other conversions if needed (e.g., 'kg')
    return 0  # Default to 0 if the format is unrecognized

 #login required decorator
def login_required(f):

    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('main.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def format_diet_plan(dietplan):
    formatted_data = []
    for day, meals in dietplan.items():
        day_section = {"day": day.capitalize(), "meals": []}
        for meal_type, items in meals.items():
            meal_section = {"meal_type": meal_type.capitalize(), "items": [{"food": food.capitalize(), "quantity": quantity} for food, quantity in items]}
            day_section["meals"].append(meal_section)
        formatted_data.append(day_section)
    return formatted_data

def collect_meal_data(form_data, dietplan_id):

    from werkzeug.exceptions import BadRequest
    from app.models import  DayTypes, MealTypes

    """Collect meal data from form submission."""
    meal_data = {}
    days = DayTypes.query.all()
    meals = MealTypes.query.all()

    # Insert meals and foods into Meals table     
    for day in days:
        day_id = day.day_type_id
        for meal in meals:
            meal_id = meal.meal_type_id
            # get from the user inputs the list of foods with relative quantity for a specified day and a specified meal
            foods_ids = form_data.getlist(f"food-{day_id}-{meal_id}[]")
            quantities = form_data.getlist(f"quantity-{day_id}-{meal_id}[]")
            

            if len(foods_ids) != len(quantities):
                raise BadRequest("Mismatch between number of foods and quantities.")

            for food_id, quantity in zip(foods_ids, quantities):
                if not quantity.isdigit() or int(quantity) <= 0:
                    raise BadRequest("Quantity must be a positive integer.")

                if day_id not in meal_data:
                    meal_data[day_id] = {}

                if meal_id not in meal_data[day_id]:
                    meal_data[day_id][meal_id] = []

                meal_data[day_id][meal_id].append({
                    "dietplan_id": dietplan_id,
                    "day_type_id": day_id,
                    "meal_type_id": meal_id,
                    "food_id": food_id,
                    "quantity": int(quantity)
                })

    return meal_data

def insert_meals_and_foods(meal_data):
    from app.models import Meals
    from app import db
    import logging

    # Configure logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    """Insert meals and foods into the database."""
    try:
        for day_id, meals in meal_data.items():
            for meal_id, foods in meals.items():
                for food in foods:
                    # Create a new meal entry
                    new_meal = Meals(
                        dietplan_id=food['dietplan_id'],
                        day_type_id=food['day_type_id'],
                        meal_type_id=food['meal_type_id'],
                        food_id=food['food_id'],
                        quantity=food['quantity']
                    )
                    # Add the new meal to the session
                    db.session.add(new_meal)
                    logger.info(f"Added meal: {new_meal}")
        
        # Commit the session
        db.session.commit()
        logger.info("All meals inserted successfully.")
    
    except Exception as e:
        # Rollback in case of any error
        db.session.rollback()
        logger.error(f"An error occurred: {e}")
        raise

    finally:
        # Close the session if needed (depends on your app configuration)
        db.session.close()

# design a method that takes 2 lists and perform the subtraction even if one or more element are None 
def safeSubtract(y, z):
    difference = []
    for x in range(max(len(y), len(z))):
        if(y[x] == None and z[x] == None):
            k = None
            difference.append(k)
        elif(y[x] == None):
            difference.append(z[x])
        elif(z[x] == None):
            difference.append(y[x])
        else:
            difference.append(y[x] - z[x])
    return difference

# Function to calculate the days of difference between two date-time strings
def dateDifference(date1, date2):
    # Convert strings to datetime objects, including time
    datetime1 = datetime.strptime(date1, '%Y-%m-%d %H:%M:%S')
    datetime2 = datetime.strptime(date2, '%Y-%m-%d %H:%M:%S')

    # Calculate the difference
    difference = datetime1 - datetime2

    # Return the absolute difference in days
    return abs(difference.days)