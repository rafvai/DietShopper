from sqlite3 import IntegrityError
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from markupsafe import Markup
from sqlalchemy import inspect
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import BadRequest
from collections import defaultdict
from sqlalchemy.sql import text
from sqlalchemy.exc import SQLAlchemyError
from .helpers import create_food_pie_chart, is_later, login_required, collect_meal_data, insert_meals_and_foods, safeSubtract, dateDifference
from .models import Substitutes, Users, DayTypes, MealTypes, Foods, DietPlans, Meals, Measurement
from . import db
import logging
import plotly.io as pio


main = Blueprint('main', __name__)

# Define homepage
@main.route("/", methods=['GET'])
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
    # retrieve user inputs
    if request.method == 'POST':
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        # if some fields are missing return error
        if not username or not password or not confirmation or not email:
            flash("Must fill out all fields", "error")
            return render_template("register.html")
        # if password is not the same as confirmation
        if password != confirmation:
            flash("Passwords don't match", "error")
            return render_template("register.html")
        # if the username is already in use
        if Users.query.filter_by(username=username).first():
            flash("Username already in use", "error")
            return render_template("register.html")
        # if email is already in use 
        if Users.query.filter_by(email=email).first():
            flash("Email address already in use", "error")
            return render_template("register.html")

        hashed_password = generate_password_hash(password)
        new_user = Users(username=username, password=hashed_password, email=email)

        db.session.add(new_user)
        db.session.commit()

        session["user_id"] = new_user.user_id
        return redirect(url_for("main.index"))
    
    return render_template("register.html")

@main.route("/my-profile", methods=['GET'])
@login_required
def my_profile():
    """ Allow user to manage info on the personal page """

    userid = session["user_id"]

    # Retrieve and display the info submitted by the user
    current_user = Users.query.filter_by(user_id=userid).first()

    if current_user:
        return render_template("my_profile.html", username=current_user.username, email=current_user.email, created=current_user.created_at)
    else:
        flash("User not found", "error")
        return redirect(url_for('main.index'))

@main.route("/edit-profile", methods=['GET', 'POST'])
@login_required
def edit_profile():
    """ Allow user to edit info on their profile """
    
    userid = session.get("user_id")
    field = request.args.get('field')
    
    if request.method == "POST":
        user = Users.query.filter_by(user_id=userid).first()

        if field == "username":
            new_username = request.form.get("new_username")
            if new_username:
                # Check if the new username is already taken
                existing_user = Users.query.filter_by(username=new_username).first()
                if existing_user:
                    flash("Username already in use, please choose another one", "error")
                else:
                    try:
                        user.username = new_username
                        db.session.commit()
                        flash("Username updated successfully", "success")
                    except IntegrityError:
                        db.session.rollback()
                        flash("An error occurred while updating username", "error")
            else:
                flash("Please enter a new username", "error")

        elif field == "email":
            new_email = request.form.get("new_email")
            if new_email:
                # Check if the new email is already taken
                existing_email = Users.query.filter_by(email=new_email).first()
                if existing_email:
                    flash("Email already in use, please choose another one", "error")
                else:
                    try:
                        user.email = new_email
                        db.session.commit()
                        flash("Email updated successfully", "success")
                    except IntegrityError:
                        db.session.rollback()
                        flash("An error occurred while updating email", "error")
            else:
                flash("Please enter a new email", "error")

        return redirect(url_for('main.my_profile'))
    
    if field not in ["username", "email"]:
        flash("Invalid field", "error")
        return redirect(url_for('main.my_profile'))

    return render_template("edit_profile.html", field=field)



@main.route("/logout")
def logout():
    """Log user out"""
    session.clear()
    return redirect(url_for("main.login"))


@main.route("/shopping-list", methods=['GET'])
@login_required
def shopping_list():
    """Show the shopping list for the user"""
    userid = session["user_id"]

    # Select the diet plans available for that user
    dietplans = DietPlans.query.filter_by(user_id=userid).all()
    if not dietplans:
        # Return a message and a link to guide the user to add a diet plan
        message = ("You don't have any diet plan assigned, let's go add a new one!<br>"
                   f'<a href="{url_for("main.add_diet")}">Add a Diet Plan</a>')
        return render_template("shopping_list.html", message=message)
    # Send diet plan options to frontend
    return render_template("shopping_list.html", message="Choose your diet plan", alternative_dietplans=dietplans)

    
@main.route("/shopping-list/<int:diet_plan_id>", methods=['GET'])
@login_required
def show_selected_shopping_list(diet_plan_id):
    """Show the shopping list for the selected diet plan"""
    # retrieve food and quantity for the selected diet plan
    items = db.session.query(Foods.name, Meals.quantity).join(Meals, Foods.food_id == Meals.food_id).filter(
        Meals.dietplan_id == diet_plan_id).all()
    # store them in a dict 
    aggregate_items = {}
    for name, quantity in items:
        aggregate_items[name] = aggregate_items.get(name, 0) + quantity
    if not aggregate_items:
        flash ("You don't have any food in the selected diet plan", "error availability dietplans")
        return render_template("shopping_list.html")
    return render_template("shopping_list.html", items=aggregate_items)


@main.route("/food-details/<string:food_name>", methods=['GET', 'POST'])
@login_required
def food_details(food_name):
    """Allow user to see food details and the substitutes for a specific food"""

    userid = session["user_id"]
    
    if request.method == "GET":
        # Fetch food properties from the Foods table
        food_properties = Foods.query.filter_by(name=food_name).first()
        
        if not food_properties:
            flash(f"No details found for {food_name}.", "error")
            return redirect(url_for("main.shopping_list"))
        
        # show chart of nutrients
        fig = create_food_pie_chart(food_properties)
        chart = pio.to_html(fig, full_html = False)
        
        # Fetch substitutes from the Substitutes table
        substitutes_results = Substitutes.query.filter_by(food_id=food_properties.food_id).all()

        # Create an empty list to store all of the details of the equivalent foods
        substitutes = []
        
        if not substitutes_results:
            flash(f"No substitutes found for {food_name}.", "info")
            return render_template("food_details.html", food=food_properties, chart = Markup(chart))
        
        # Loop through the list of substitutes' obj and for each one create a food obj
        for result in substitutes_results:
            substitute_food = Foods.query.filter_by(food_id=result.substitute_food_id).first()
            if substitute_food:
                substitutes.append(substitute_food)
        
        return render_template("food_details.html", food=food_properties, substitutes=substitutes, chart= Markup(chart))
    
    ######## to do
    elif request.method == "POST":
        pass


@main.route("/diet-plan", methods=['GET', 'POST'])
@login_required
def diet_plan():
    """Show the diet plan for the user"""
    userid = session["user_id"]

    if request.method == "GET":
        # retrieve all dietplans available for that patient
        alternative_dietplans = db.session.query(DietPlans.dietplan_id, DietPlans.name).filter(DietPlans.user_id == userid).all()
        # return all the names of the dietplans assigned for that user
        return render_template("diet_plan.html", alternative_dietplans = alternative_dietplans)    
    
    elif request.method == "POST":
        # retrieve the selected dietplan id info and store it in a variable
        dietPlan_id = request.form.get('dietPlan')
        if dietPlan_id: 
            diet_plan_info = DietPlans.query.filter_by(user_id = userid, dietplan_id = dietPlan_id).first()
            
            # store the list of all meals for that dietplan
            result = (db.session.query(DayTypes.day_name, MealTypes.meal_name, Foods.name, Meals.quantity)
            .join(Meals, Meals.day_type_id == DayTypes.day_type_id)
            .join(MealTypes, MealTypes.meal_type_id == Meals.meal_type_id)
            .join(Foods, Foods.food_id == Meals.food_id)
            .filter(Meals.dietplan_id == dietPlan_id)
            .all())
            
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
        
        flash("Error retrieving the diet plan", "error")
    
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

        if not formatted_meal_data:
            flash("An error occurred while collecting data", "error collecting data")

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
    
@main.route("/remove-diet", methods=['GET', 'POST'])
@login_required
def remove_diet():
    """ Allow user to delete a diet plan """

    userid = session.get("user_id")

    if request.method == "GET":
        assigned_diets = DietPlans.query.filter_by(user_id=userid).all()
        if assigned_diets:
            return render_template("remove_diet.html", assigned_diets=assigned_diets)
        else:
            flash("There is no assigned diet plan for this user", "error retrieving diet plan")
            return redirect(url_for('main.diet_plan'))

    elif request.method == "POST":
        delete_dietids = request.form.getlist("diet_id")
        
        if not delete_dietids:
            flash("No diet plan selected for deletion", "delete not selected")
            return redirect(url_for('main.remove_diet'))

        try:
            # get the diet plans
            diet_plans_to_delete = [DietPlans.query.filter_by(user_id=userid, dietplan_id=int(diet_id)).first()
                                    for diet_id in delete_dietids]

            # Check if all the diet plans exist
            if None in diet_plans_to_delete:
                flash("Some diet plans could not be found or are invalid.", "delete failed")
                return redirect(url_for('main.remove_diet'))

            for diet_plan in diet_plans_to_delete:
                db.session.delete(diet_plan)
            db.session.commit()

            flash("Selected diet plans were successfully deleted.", "delete succesfully")
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred while deleting diet plans: {str(e)}")

    return redirect(url_for('main.diet_plan'))

@main.route("/add-food", methods=['GET', 'POST'])
@login_required
def add_food():
    """ Allow user to add food inside db """

    if request.method == 'GET':
        # Initialize an empty list to store column names
        columns = []
        # Use SQLAlchemy's inspector to get column names from the 'foods' table
        inspector = inspect(db.engine)
        # Retrieve all column names
        for column_info in inspector.get_columns("Foods"): 
            column_name = column_info['name']  # Extract the column name
            # Skip the primary key column
            if column_name == "food_id":
                continue
            else:
                columns.append(column_name.capitalize())
        
        # Render the template with the column names
        return render_template("add_food.html", columns=columns)


    elif request.method == 'POST':
        # Retrieve user inputs
        name = request.form.get("Name")
        calories = request.form.get("Calories")
        protein = request.form.get("Protein")
        carbs = request.form.get("Carbs")
        fats = request.form.get("Fats")

        # Check all fields are present
        if not name or not calories or not protein or not carbs or not fats:
            flash("You must fill all fields.", "error")
            return redirect(url_for('main.add_food'))

        try:
            # Convert into column's accepted format
            calories = int(calories)
            protein = float(protein)
            carbs = float(carbs)
            fats = float(fats)
        except ValueError:
            flash("All values must be of a correct format", "error")
            return redirect(url_for('main.add_food'))

        # Crea una nuova istanza di Foods
        new_food = Foods(name=name, calories=calories, protein=protein, carbs=carbs, fats=fats)

        # Aggiungi e commit il nuovo record al database
        db.session.add(new_food)
        db.session.commit()

        # Flash messaggio di successo
        flash("The food has been added succesfully!", "food added successfully")

        return redirect(url_for('main.add_food'))  

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
            # retrieve all fields for the selected measurement, except for measurement id and user id
            query = """SELECT height, weight, BMI, body_fat, fat_free_bw, subcutaneous_fat, visceral_fat, body_water, skeletal_muscle, muscle_mass, bone_mass, protein, BMR, created_at
                        FROM Measurement WHERE user_id = :user_id AND measurement_id = :measurement_id"""
 
            result_1 = db.session.execute(text(query), {"user_id": userid, "measurement_id": selected_measurement_id_1}).fetchone()
            result_2 = db.session.execute(text(query), {"user_id": userid, "measurement_id": selected_measurement_id_2}).fetchone()

            if not result_1 or not result_2:
                flash("One or both measurements not found.", "error")
                return redirect(url_for('main.measurements'))
            
            # store dates of the 2 records inside variables
            datetime1 = result_1[-1]
            datetime2 = result_2[-1]
            
            # display the most recent date after the other for comparison purpose
            if (is_later(datetime1, datetime2)):
                tmp = result_1
                result_1 = result_2
                result_2 = tmp

            # calculate the difference in time between the 2 records
            days_difference = dateDifference(datetime1, datetime2)
            
            # calculate the difference existing between the 2 records excluding the date
            difference = safeSubtract(result_2[:-1], result_1[:-1])
            
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