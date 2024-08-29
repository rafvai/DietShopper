from sqlite3 import IntegrityError
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from markupsafe import Markup
from sqlalchemy import inspect
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import BadRequest
from collections import defaultdict
from sqlalchemy.sql import text
from sqlalchemy.exc import SQLAlchemyError
from .helpers import create_food_pie_chart, create_line_graph, is_later, login_required, collect_meal_data, insert_meals_and_foods, safeSubtract, dateDifference
from .models import Newsletter, Substitutes, Users, DayTypes, MealTypes, Foods, DietPlans, Meals, Measurement
from . import db
import logging
import plotly.io as pio

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
main = Blueprint('main', __name__)

# Define homepage
@main.route("/", methods=['GET', 'POST'])
@login_required
def index():
    """Show welcome message and options"""

    # store user id in session
    userid = session.get("user_id")
    # if user_id is not in session, redirect to login
    if not userid:
        flash("User not logged in", "error")
        return redirect(url_for('main.login'))
    
    # query the database for the user's username
    user = db.session.query(Users).filter(Users.user_id == userid).first()
    if not user:
        flash("An error occurred while retrieving user's username", "error")
        return redirect(url_for('main.login'))
    
    if request.method == 'GET':
        return render_template("index.html", username=user.username)
    
    elif request.method == 'POST':
        # store user info 
        name = request.form.get("name")
        email = request.form.get("email")
        # check for potential errors
        if not name or not email:
            flash("Name and/or email missing", "error")
            return redirect(url_for("main.index"))
        
        # create and store user inputs inside a newsletter obj   
        new_newsletter = Newsletter(email=email, name=name)
        # add it to db and commit
        try:
            db.session.add(new_newsletter)
            db.session.commit()
            flash("Successfully subscribed to the newsletter!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred while adding to the newsletter: {str(e)}", "error")

    return render_template("index.html", username=user.username)



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


@main.route("/about", methods=['GET'])
@login_required
def about():

    # store user id in session
    userid = session.get("user_id")
    # if user_id is not in session, redirect to login
    if not userid:
        flash("User not logged in", "error")
        return redirect(url_for('main.login'))
    
    # query the database for the user's username
    user = db.session.query(Users).filter(Users.user_id == userid).first()
    if not user:
        flash("An error occurred while retrieving user's username", "error")
        return redirect(url_for('main.login'))
    
    if request.method == 'GET':
        """ render the page description of the app """
        return render_template("about.html", username = user.username.capitalize())

@main.route("/project", methods=['GET'])
@login_required
def project():
     # store user id in session
    userid = session.get("user_id")
    # if user_id is not in session, redirect to login
    if not userid:
        flash("User not logged in", "error")
        return redirect(url_for('main.login'))
    
    # query the database for the user's username
    user = db.session.query(Users).filter(Users.user_id == userid).first()
    if not user:
        flash("An error occurred while retrieving user's username", "error")
        return redirect(url_for('main.login'))
    
    if request.method == 'GET':
        """ render the page description of the project """
        return render_template("project.html", username = user.username.capitalize())


@main.route("/my-profile", methods=['GET'])
@login_required
def my_profile():
    """ Allow user to manage info on the personal page """

    userid = session["user_id"]

    # Retrieve and display the info submitted by the user
    current_user = Users.query.filter_by(user_id=userid).first()

    if current_user:
        # Format the creation date
        created_at = current_user.created_at.strftime('%Y-%m-%d')
        return render_template("my_profile.html", username=current_user.username, email=current_user.email, created=created_at)
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
    # retrieve diet plan info
    diet_info = DietPlans.query.filter_by(dietplan_id = diet_plan_id).first()
    # error handling for bad input
    if not diet_info:
        flash("The selected dietplan doesn't exist", "error")
    # retrieve food and quantity for the selected diet plan
    items = db.session.query(Foods.name, Meals.quantity).join(Meals, Foods.food_id == Meals.food_id).filter(
        Meals.dietplan_id == diet_plan_id).all()
    if not items:
        flash ("You don't have any food in the selected diet plan", "error")
    # store them in a dict 
    aggregate_items = {}
    for name, quantity in items:
        aggregate_items[name] = aggregate_items.get(name, 0) + quantity
    if not aggregate_items:
        flash ("Error creating your shopping list", "error")
        return render_template("shopping_list.html")
    return render_template("shopping_list.html", items=aggregate_items, diet_info = diet_info)


@main.route("/food-details/<string:food_name>", methods=['GET'])
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
            day_totals = defaultdict(int)  # To store total items per day

            for row in result:
                day_name, meal_name, food, quantity = row
                output[day_name][meal_name].append((food, quantity))
                day_totals[day_name] += 1  # Increment the count of food items for the day

            # pass them to front end
            return render_template("diet_plan.html", assigned_meals=output, diet_plan_info=diet_plan_info, day_totals=day_totals, dietPlan_id = dietPlan_id)
        
        flash("Error retrieving the diet plan", "error")
    
    # handle case where no diet plan is selected or invalid input
    return redirect(url_for('main.diet_plan'))


@main.route("/add-diet", methods=['GET', 'POST'])
@login_required
def add_diet():

    """ Allow user to add a new diet plan """
    # handle and store the autentication of the user
    userid = session["user_id"]
    
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
        flash("Diet plan added successfully!", "success")
        return redirect(url_for('main.diet_plan'))

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Database error during diet plan addition: {e}")
        flash("An error occurred while adding the diet plan. Please try again.", "error")
        return redirect(url_for('main.add_diet'))
    except BadRequest as e:
        flash(f"Invalid input: {e.description}", "error")
        return redirect(url_for('main.add_diet'))
    

@main.route("/remove-diet/<int:diet_plan_id>", methods=['POST'])
@login_required
def remove_diet(diet_plan_id):
    """ Allow user to delete a diet plan """

    userid = session.get("user_id")

    try:
        # get the diet plan
        diet_plan_to_delete = DietPlans.query.filter_by(user_id=userid, dietplan_id=diet_plan_id).first()

        # Check if the diet plan exists
        if diet_plan_to_delete is None:
            flash("Diet plan not found or invalid.", "error")
            return redirect(url_for('main.diet_plan'))
        
        # retrieve the list of all meals for that dietplan id
        Meals.query.filter_by(dietplan_id = diet_plan_id).delete(synchronize_session=False)
            
        db.session.delete(diet_plan_to_delete)
        db.session.commit()

        flash("Selected diet plan has been successfully deleted.", "success")
    except Exception as e:
        db.session.rollback()
        logging.getLogger(__name__).error(f"Error deleting diet plan {diet_plan_id} for user {userid}: {e}")
        flash("An error occurred while deleting the diet plan.", "error")
    
    return redirect(url_for('main.diet_plan'))


@main.route("/add-food", methods=['GET', 'POST'])
@login_required
def add_food():
    """Allow user to add food inside db"""

    if request.method == 'GET':
        try:
            # Initialize an empty list to store column names
            columns = []
            # Use SQLAlchemy's inspector to get column names from the 'foods' table
            inspector = inspect(db.engine)
            # Retrieve all column names
            for column_info in inspector.get_columns("Foods"): 
                column_name = column_info['name']  
                # Skip the primary key column
                if column_name == "food_id":
                    continue
                else:
                    columns.append(column_name.capitalize())
            
            # Render the template with the column names
            return render_template("add_food.html", columns=columns)
        except SQLAlchemyError as e:
            logger.error(f"Database error occurred while retrieving columns: {e}")
            flash("An error occurred while retrieving food columns", "error")
            return redirect(url_for('main.index'))  

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
            # Convert inputs into appropriate formats
            calories = int(calories)
            protein = float(protein)
            carbs = float(carbs)
            fats = float(fats)
        except ValueError:
            flash("All values must be of a correct format", "error")
            return redirect(url_for('main.add_food'))

        try:
            # Create a new instance of Foods
            new_food = Foods(name=name, calories=calories, protein=protein, carbs=carbs, fats=fats)
            # Add and commit the new record to the database
            db.session.add(new_food)
            db.session.commit()

            # Flash success message
            flash("The food has been added successfully!", "success")
        except SQLAlchemyError as e:
            logger.error(f"Database error occurred while adding food: {e}")
            db.session.rollback()
            flash("An error occurred while adding the food", "error")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            db.session.rollback()
            flash("An unexpected error occurred", "error")

        return redirect(url_for('main.add_food'))

@main.route("/measurements", methods=['GET', 'POST'])
@login_required
def measurements():
    """Allow user to watch past measurements and add new ones"""
    try:
        userid = session["user_id"]
    except KeyError:
        logger.error("User ID not found in session")
        flash("User session expired. Please log in again.", "error")
        return redirect(url_for("main.login"))  

    if request.method == "GET":
        try:
            past_measurements = db.session.query(Measurement.measurement_id, Measurement.created_at).filter_by(user_id=userid).all()
            if not past_measurements:
                return render_template("measurements.html", message="You don't have any records. Please add one.")
            return render_template("measurements.html", past_measurements=past_measurements)
        except SQLAlchemyError as e:
            logger.error(f"Database error occurred: {e}")
            flash("An error occurred while retrieving past measurements", "error")
            return redirect(url_for("main.measurements"))

    elif request.method == "POST":
        try:
            measurements = db.session.query(Measurement.measurement_id, Measurement.created_at).filter_by(user_id=userid).all()

            if 'compare' in request.form:
                selected_measurement_id_1 = request.form.get("selected_measurement_1")
                selected_measurement_id_2 = request.form.get("selected_measurement_2")

                if not selected_measurement_id_1 or not selected_measurement_id_2:
                    flash("Both measurements must be selected for comparison.", "error")
                    return redirect(url_for('main.measurements'))
                
                # retrieve the 2 selected measurements
                measure_1 = Measurement.query.filter_by(user_id = userid, measurement_id = selected_measurement_id_1).first()
                measure_2 = Measurement.query.filter_by(user_id = userid, measurement_id = selected_measurement_id_2).first()

                if not measure_1 or not measure_2:
                    flash("One or both measurements not found.", "error")
                    return redirect(url_for('main.measurements'))
                
                # take only dates of the measurements
                datetime1 = measure_1.created_at
                datetime2 = measure_2.created_at

                # check which one is later, if is later, put it as second measurement
                if is_later(datetime1, datetime2):
                    measure_1, measure_2 = measure_2, measure_1

                # calculate days difference
                days_difference = dateDifference(datetime1, datetime2)
                # calculate the changes between the 2 measures and return a measurement obj
                difference = safeSubtract(measure_1,  measure_2)

                # store the formatted names of the columns i intend to pass to frontend
                column_names = [col.name for col in inspect(Measurement).columns if col.name not in ["user_id", "measurement_id", "created_at"]]
                
                  # Create dictionaries for display
                display_measurement_1 = {}
                display_measurement_2 = {}
                display_difference = {}

                for column in column_names:
                    formatted_name = column.replace("_", " ").capitalize()
                    display_measurement_1[formatted_name] = getattr(measure_1, column)
                    display_measurement_2[formatted_name] = getattr(measure_2, column)
                    display_difference[formatted_name] = getattr(difference, column)

                return render_template("measurements.html",
                                       days_difference=days_difference,
                                       display_measurement_1=display_measurement_1,
                                       display_measurement_2=display_measurement_2,
                                       display_difference=display_difference,
                                       measurements=measurements)

            else:
                selected_measurement_id = request.form.get("selected_measurement")

                if not selected_measurement_id:
                    flash("No measurement selected.", "error")
                    return redirect(url_for('main.measurements'))
                
                result = Measurement.query.filter_by(user_id=userid, measurement_id=selected_measurement_id).first()

                if not result:
                    flash("Measurement not found.", "error")
                    return redirect(url_for('main.measurements'))

                column_names = [col.name for col in inspect(Measurement).columns if col.name not in ["user_id", "measurement_id", "created_at"]]
                display_measurement = {col.replace("_", " ").capitalize(): getattr(result, col) for col in column_names}

                return render_template("measurements.html",
                                       display_measurement=display_measurement,
                                       measurements=measurements,
                                       selected_measurement_id=selected_measurement_id)
        except SQLAlchemyError as e:
            logger.error(f"Database error occurred: {e}")
            flash("An error occurred while processing your request", "error")
            return redirect(url_for('main.measurements'))
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            flash("An unexpected error occurred", "error")
            return redirect(url_for('main.measurements'))

    return redirect(url_for('main.measurements'))

@main.route("/add_measurement", methods=['GET', 'POST'])
@login_required
def add_measurement():
    """Allow user to add a new measurement"""
    try:
        userid = session['user_id']
    except KeyError:
        logger.error("User ID not found in session")
        flash("User session expired. Please log in again.", "error")
        return redirect(url_for("auth.login"))  # Adjust to your login endpoint

    column_names = []
    try:
        # Retrieve and format column names
        inspector = inspect(Measurement)
        for column in inspector.columns:
            if column.name in ["user_id", "measurement_id", "created_at"]:
                continue
            elif column.name in ["BMI", "BMR"]:
                column_names.append(column.name)
            else:
                column_names.append(column.name.replace("_", " ").capitalize())
    except SQLAlchemyError as e:
        logger.error(f"Database error occurred: {e}")
        flash("An error occurred while retrieving column names", "error")
        return redirect(url_for("main.measurements"))

    if request.method == 'GET':
        return render_template("add_measurement.html", column_names=column_names)

    elif request.method == 'POST':
        # Retrieve user's inputs and create a new Measurement record
        new_record = Measurement(user_id=userid)
        try:
            for name in column_names:
                value = request.form.get(name)
                if name in ["BMI", "BMR"]:
                    setattr(new_record, name, value)
                else:
                    formatted_name = name.replace(" ", "_").lower()
                    setattr(new_record, formatted_name, value)

            # Add the record to the database
            db.session.add(new_record)
            db.session.commit()

            # Display success message
            flash('Record added successfully!', 'success')
        except SQLAlchemyError as e:
            logger.error(f"Database error occurred: {e}")
            db.session.rollback()
            flash("An error occurred while adding the record", "error")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            db.session.rollback()
            flash("An unexpected error occurred", "error")

    return redirect(url_for("main.measurements"))

@main.route("/graphs", methods=['GET', 'POST'])
@login_required
def graphs():
    """Allow user to see his progression graphs"""
    try:
        userid = session['user_id']
    except KeyError:
        logger.error("User ID not found in session")
        flash("User session expired. Please log in again.", "error")
        return redirect(url_for("auth.login"))  # Adjust to your login endpoint

    if request.method == 'GET':
        try:
            # Retrieve the names of the parameters from the measurement table
            parameters = [col.name.replace("_", " ").capitalize() for col in inspect(Measurement).columns if col.name not in ["user_id", "measurement_id", "created_at"]]
            if not parameters:
                flash("An error occurred while retrieving parameter names", "error")
                return redirect(url_for("main.measurements"))
        except SQLAlchemyError as e:
            logger.error(f"Database error occurred: {e}")
            flash("An error occurred while retrieving parameter names", "error")
            return redirect(url_for("main.measurements"))

        # Return the page passing parameter names
        return render_template("graphs.html", parameters=parameters)

    elif request.method == 'POST':
        selected_parameter = request.form.get("selected_parameter")
        if not selected_parameter:
            flash("Please select a parameter", "error")
            return redirect(url_for("main.graphs"))

        try:
            # Format the selected parameter
            if selected_parameter in ["Bmi", "Bmr"]:
                formatted_parameter = selected_parameter.upper()
            else:
                formatted_parameter = selected_parameter.lower().replace(" ", "_")

            # Get all the records for the selected parameter
            values = db.session.query(getattr(Measurement, formatted_parameter), Measurement.created_at).filter_by(user_id=userid).all()
        except SQLAlchemyError as e:
            logger.error(f"Database error occurred: {e}")
            flash("An error occurred while retrieving data", "error")
            return redirect(url_for("main.graphs"))
        except AttributeError:
            logger.error("Selected parameter does not exist in the database")
            flash("Invalid parameter selected", "error")
            return redirect(url_for("main.graphs"))

        if not values:
            flash("No data available for the selected parameter", "error")
            return redirect(url_for("main.graphs"))

        try:
            graph = create_line_graph(values, selected_parameter)
            if not graph:
                raise ValueError("Graph creation failed")
        except ValueError as e:
            logger.error(f"Graph creation error: {e}")
            flash("An error occurred while creating the graph", "error")
            return redirect(url_for("main.graphs"))

        chart = pio.to_html(graph, full_html=False)
        return render_template("graphs.html", chart=chart)