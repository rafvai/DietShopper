from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from sqlalchemy import inspect
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import BadRequest
from collections import defaultdict
from sqlalchemy.sql import text
from sqlalchemy.exc import SQLAlchemyError
from .helpers import login_required, collect_meal_data, insert_meals_and_foods, safeSubtract, dateDifference
from .models import Users, DayTypes, MealTypes, Foods, DietPlans, Meals, Measurement
from . import db
import logging

main = Blueprint('main', __name__)

# Define homepage
@main.route("/")
@login_required
def index():
    """Show welcome message and options"""
    userid = session["user_id"]
    user = Users.query.get(userid)
    welcome_message = f"Welcome back, {user.username}!" if user else "Welcome!"
    return render_template("index.html", welcome_message=welcome_message)


@main.route("/login", methods=["GET", "POST"])
def login():
    """Allow user to log in"""
    session.clear()
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            flash("Must input valid username and password", "error")
            return render_template("login.html")

        # Use ORM to query for the user
        user = Users.query.filter_by(username=username).first()
    
        if user is None:
            flash("Invalid username and/or password", "error")
            return render_template("login.html")

        # Check password
        if not check_password_hash(user.password, password):
            flash("Invalid username and/or password", "error")
            return render_template("login.html")

        session["user_id"] = user.user_id
        return redirect(url_for("main.index"))
    
    return render_template("login.html")


@main.route("/register", methods=["GET", "POST"])
def register():
    """Allow new user to register"""
    if request.method == 'POST':
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username or not password or not confirmation or not email:
            flash("Must fill out all fields", "error")
            return render_template("register.html")

        if password != confirmation:
            flash("Passwords don't match", "error")
            return render_template("register.html")

        if Users.query.filter_by(username=username).first():
            flash("Username already in use", "error")
            return render_template("register.html")
        
        if Users.query.filter_by(email=email).first():
            flash("Email address already in use", "error")
            return render_template("register.html")

        hashed_password = generate_password_hash(password)
        new_user = Users(username=username, password=hashed_password, email=email)

        db.session.add(new_user)
        db.session.commit()

        session["user_id"] = new_user.user_id
        print(session["user_id"])
        return redirect(url_for("main.index"))
    
    return render_template("register.html")


@main.route("/logout")
def logout():
    """Log user out"""
    session.clear()
    return redirect(url_for("main.login"))


@main.route("/shopping-list", methods=['GET', 'POST'])
@login_required
def shopping_list():
    """Show the shopping list for the user"""
    userid = session["user_id"]

    if request.method == 'GET':
        # select the dietplans available for that user and store in a variable
        query = text("SELECT dietplan_id, name FROM DietPlans WHERE user_id = :userid")
        dietplans = db.session.execute(query, {'userid': userid}).fetchall()
        # if the user hasn't any dietplan assigned
        if len(dietplans) < 1:
            # return a message and a link to guide the user to add a diet plan
            message = ("You don't have any diet plan assigned, let's go add a new one!<br>"
                    f'<a href="{url_for("diet_plan")}">Add a Diet Plan</a>')
            return render_template("shopping_list.html", message = message)
        # send dietplans options to frontend
        return render_template("shopping_list.html", message = "Choose your diet plan", alternative_dietplans=dietplans)
    
    else:
        # take and store the selected diet plan
        dietPlan = request.form.get('dietPlan')
        if dietPlan:
            # for that diet plan store all of the food items with their relative quantity 
            shopping_list_query = text("SELECT Foods.name, Meals.quantity FROM Foods JOIN Meals ON Foods.food_id = Meals.food_id JOIN DietPlans ON DietPlans.dietplan_id = Meals.dietplan_id WHERE DietPlans.user_id = :userid AND DietPlans.dietplan_id = :dietplan")
            items = db.session.execute(shopping_list_query, {'userid': userid, 'dietplan': dietPlan}).fetchall()
            aggregate_items = {}
            for name, quantity in items:
                # if the item is already in the shopping list, update the total amount, otherwise add the item and its quantity
                aggregate_items[name] = aggregate_items.get(name, 0) + quantity
            # if the shopping list is empty
            if not aggregate_items:
                return render_template ("shopping_list.html" , message1 = "You don't have any food in the selected diet plan")
            
            return render_template("shopping_list.html", items=aggregate_items)
        
        flash("Please select a valid diet plan", "error")
    return redirect(url_for("main.shopping_list"))


@main.route("/diet-plan", methods=['GET', 'POST'])
@login_required
def diet_plan():
    """Show the diet plan for the user"""
    userid = session["user_id"]

    if request.method == "GET":
        # select the dietplans available for that user and store in a variable
        retrieve_dietplans_query = text("SELECT dietplan_id, name FROM DietPlans WHERE user_id = :userid")
        alternative_dietplans = db.session.execute(retrieve_dietplans_query, {'userid': userid}).fetchall()
        # return all the names of the dietplans assigned for that user
        return render_template("diet_plan.html", alternative_dietplans = alternative_dietplans)    
    
    elif request.method == "POST":
        # retrieve the selected dietplan id info and store it in a variable
        dietPlan_id = request.form.get('dietPlan')
        if dietPlan_id: 
            diet_plan_info = DietPlans.query.filter_by(user_id = userid, dietplan_id = dietPlan_id).first()
            assigned_meals_query = text("""
            SELECT DayTypes.day_name, MealTypes.meal_name, Foods.name, Meals.quantity
            FROM Meals 
            JOIN DayTypes ON Meals.day_type_id = DayTypes.day_type_id
            JOIN MealTypes ON Meals.meal_type_id = MealTypes.meal_type_id
            JOIN Foods ON Meals.food_id = Foods.food_id
            WHERE Meals.dietplan_id = :diet_plan_id
            """) 
            # store the list of all meals for that dietplan
            result = db.session.execute(assigned_meals_query, {'diet_plan_id' : dietPlan_id}).fetchall()
            
            # create a default dict in which for every day and meal there's the corresponding food and quantity
            output = defaultdict(lambda: defaultdict(list))

            for row in result:
                day_name =  row[0]
                meal_name = row[1]
                food = row[2]
                quantity = row[3]
                output[day_name][meal_name].append((food, quantity))

        # pass them to front end
        return render_template("diet_plan.html", assigned_meals = output, diet_plan_info = diet_plan_info)
    
    # handle case where no diet plan is selected or invalid input
    return redirect(url_for('main.diet_plan'))


@main.route("/add-diet", methods=['GET', 'POST'])
@login_required
def add_diet():

    """ Allow user to add a new diet plan """
    # handle and store the autentication of the user
    userid = session["user_id"]
    if not userid:
        flash("User not logged in", "error")
        return redirect(url_for('main.login'))
    
    if request.method == "GET":
        try:
            days = DayTypes.query.all()
            meals = MealTypes.query.all()
            foods = Foods.query.with_entities(Foods.food_id, Foods.name).all()
        except SQLAlchemyError as e:
            logging.error(f"Database error: {e}")
            flash("An error occurred while retrieving data. Please try again later.", "error")
            return redirect(url_for('main.index'))

        return render_template("add_diet.html", days=days, meals=meals, foods=foods)

    
    elif request.method == "POST":
        # Retrieve diet plan details
        diet_name = request.form.get("dietName")
        diet_description = request.form.get("dietDescription")

        if not diet_name or not diet_description:
            flash("Both diet name and description are required.", "error")
            return redirect(url_for('main.add_diet'))
        
    try:
        # insert new diet plan, create a diet plan obj
        new_diet_plan = DietPlans(user_id = userid, name = diet_name, description = diet_description)
        db.session.add(new_diet_plan)
        db.session.flush()

        # create a dict to store meals for every day
        formatted_meal_data = collect_meal_data(request.form, new_diet_plan.dietplan_id)

        insert_meals_and_foods(formatted_meal_data)

        db.session.commit()
        flash("Diet plan added successfully!", "added plan successfully")
        return redirect(url_for('main.diet_plan'))

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Database error during diet plan addition: {e}")
        flash("An error occurred while adding the diet plan. Please try again.", "error")
        return redirect(url_for('main.add_diet'))
    except BadRequest as e:
        flash(f"Invalid input: {e.description}", "error")
        return redirect(url_for('main.add_diet'))

@main.route("/measurements", methods=['GET', 'POST'])
@login_required
def measurements():
    """Allow user to watch past measurements and add new ones"""

    userid = session["user_id"]

    if request.method == "GET":
        # Retrieve past measurements, taking only dates and ids
        past_measurements = db.session.query(Measurement.measurement_id, Measurement.created_at).filter_by(user_id=userid).all()
        if not past_measurements:
            return render_template("measurements.html", message="You don't have any records. Please add one.")
        return render_template("measurements.html", past_measurements=past_measurements)

    elif request.method == "POST":
        # Retrieve past measurements to ensure it is always available for rendering
        past_measurements = db.session.query(Measurement.measurement_id, Measurement.created_at).filter_by(user_id=userid).all()

        if 'compare' in request.form:
            # User wants to compare with another measurement
            selected_measurement_id_1 = request.form.get("selected_measurement_1")
            selected_measurement_id_2 = request.form.get("selected_measurement_2")

            if not selected_measurement_id_1 or not selected_measurement_id_2:
                flash("Both measurements must be selected for comparison.", "error")
                return redirect(url_for('main.measurements'))

            query = """SELECT height, weight, BMI, body_fat, fat_free_bw, subcutaneous_fat, visceral_fat, body_water, skeletal_muscle, muscle_mass, bone_mass, protein, BMR, created_at
                        FROM Measurement WHERE user_id = :user_id AND measurement_id = :measurement_id"""

            result_1 = db.session.execute(text(query), {"user_id": userid, "measurement_id": selected_measurement_id_1}).fetchone()
            result_2 = db.session.execute(text(query), {"user_id": userid, "measurement_id": selected_measurement_id_2}).fetchone()

            if not result_1 or not result_2:
                flash("One or both measurements not found.", "error")
                return redirect(url_for('main.measurements'))
            
            # calculate the difference in time between the 2 records
            days_difference = dateDifference(result_1[-1], result_2[-1])
            
            # calculate the difference existing between the 2 records excluding the date
            difference = safeSubtract(result_1[:-1], result_2[:-1])
            
            # store the formatted column names , don't save user, measurement and date
            column_names = [col.name.replace("_", " ").capitalize() for col in inspect(Measurement).columns if col.name not in ["user_id", "measurement_id", "created_at"]]

            # create dicts by zipping together col names and values, exclude date in display difference
            display_measurement_1 = dict(zip(column_names, result_1))
            display_measurement_2 = dict(zip(column_names, result_2))
            display_difference = dict(zip(column_names, difference))
            
            return render_template("measurements.html", 
                                   days_difference = days_difference,
                                   display_measurement_1=display_measurement_1, 
                                   display_measurement_2=display_measurement_2,
                                   display_difference=display_difference,
                                   past_measurements=past_measurements)

        else:
            # User wants to view a single measurement
            selected_measurement_id = request.form.get("selected_measurement")

            if not selected_measurement_id:
                flash("No measurement selected.", "error")
                return redirect(url_for('main.measurements'))

            query = """SELECT height, weight, BMI, body_fat, fat_free_bw, subcutaneous_fat, visceral_fat, body_water, skeletal_muscle, muscle_mass, bone_mass, protein, BMR, created_at
                       FROM Measurement WHERE user_id = :user_id AND measurement_id = :measurement_id"""

            result = db.session.execute(text(query), {"user_id": userid, "measurement_id": selected_measurement_id}).fetchone()

            if not result:
                flash("Measurement not found.", "error")
                return redirect(url_for('main.measurements'))

            column_names = [col.name.replace("_", " ").capitalize() for col in inspect(Measurement).columns if col.name not in ["user_id", "measurement_id", "created_at"]]

            display_measurement = dict(zip(column_names, result))

            return render_template("measurements.html", 
                                   display_measurement=display_measurement, 
                                   past_measurements=past_measurements,
                                   selected_measurement_id=selected_measurement_id)

    return redirect(url_for('main.measurements'))


@main.route("/add_measurement", methods =['GET','POST'])
@login_required
def add_measurement():
    """ Allow user to add a new measurement """
    userid = session['user_id']
    column_names = []

    # retrieve and format column names
    inspector = inspect(Measurement)
    for column in inspector.columns:
        if(column.name == "user_id" or column.name == "measurement_id" or column.name == "created_at"):
            continue
        elif(column.name == "BMI" or column.name == "BMR"):
            column_names.append(column.name)
        else:
            column_names.append(column.name.replace("_", " ").capitalize())

    # if request methos is get , just render column names
    if request.method == "GET":
        return render_template("add_measurement.html", column_names = column_names)
    
    # if user submits a new record
    elif request.method == "POST":
        # retrieve user's inputs
        new_record = Measurement(user_id=userid)
        
        for name in column_names:
            # Get the value from the form
            value = request.form.get(name)
            
            # Don't format only the BMI and BMR columns
            if name == "BMI" or name == "BMR":
                setattr(new_record, name, value)
            else:
                formatted_name = name.replace(" ", "_").lower()
                setattr(new_record, formatted_name, value)
        
        # Add the record to db
        db.session.add(new_record)
        db.session.commit()

        # Display success message
        flash('Record added successfully!', 'added record successfully')

    return redirect(url_for("main.measurements"))