from collections import defaultdict
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import BadRequest
from app.helpers import collect_meal_data, insert_meals_and_foods
from app.models import DayTypes, DietPlans, Foods, MealTypes, Meals, Patients, Specialists, Users
from app.specialist_helper import get_specialist_column_names, login_required
import logging
from . import db

specialist_bp = Blueprint('specialist', __name__, url_prefix='/specialist')



@specialist_bp.route("/login", methods=['GET', 'POST'])
def specialist_login():
    """ Allow specialists to log in """
    
    if request.method == 'POST':
        username = request.form.get("Username")
        password = request.form.get("Password")

        if not username or not password:
            flash("Must input valid username and password", "error")
            return render_template("specialist/login.html")

        specialist = Specialists.query.filter_by(username=username).first()
    
        if specialist is None or not check_password_hash(specialist.password, password):
            flash("Invalid username and/or password", "error")
            return render_template("specialist/login.html")

        session.clear()
        session['username'] = username 
        return redirect(url_for("specialist.specialist_index"))
    
    return render_template("specialist/login.html")


@specialist_bp.route("/register", methods=['GET', 'POST'])
def specialist_register():
    """ Allow a specialist to request registration """

    column_names = get_specialist_column_names()

    if request.method == 'GET':
        return render_template("specialist/register.html", column_names=column_names)
    
    elif request.method == 'POST':
        username = request.form.get("Username")
        name = request.form.get("Name")
        last_name = request.form.get("Last name")
        email = request.form.get("Email")
        password = request.form.get("Password")
        confirmation = request.form.get("Confirmation")

        if not all([username, name, last_name, email, password, confirmation]):
            flash("Must fill out all fields", "error")
            return render_template("specialist/register.html", column_names=column_names)

        if password != confirmation:
            flash("Passwords don't match", "error")
            return render_template("specialist/register.html", column_names=column_names)

        if Specialists.query.filter_by(username=username).first():
            flash("Username already in use", "error")
            return render_template("specialist/register.html", column_names=column_names)

        if Specialists.query.filter_by(email=email).first():
            flash("Email address already in use", "error")
            return render_template("specialist/register.html", column_names=column_names)

        hashed_password = generate_password_hash(password)
        new_specialist = Specialists(
            username=username,
            name=name,
            last_name=last_name,
            password=hashed_password, 
            email=email
        )

        db.session.add(new_specialist)
        db.session.commit()

        session['username'] = username  
        return redirect(url_for("specialist.specialist_index"))

    return render_template("specialist/register.html", column_names=column_names)


@specialist_bp.route("/index", methods=['GET'])
@login_required
def specialist_index():
    """ Show specialist home page """
    username = session['username']
    return render_template("specialist/index.html", username=username)

@specialist_bp.route("/logout")
def specialist_logout():
    """ Allow user to log out """
    session.clear()
    return redirect(url_for("specialist.specialist_login"))


@specialist_bp.route("/add-patient", methods=['GET', 'POST'])
@login_required
def specialist_add_patient():
    """ Allow specialist to add a patient to his list """

    specialist_name = session['username']

    if request.method == 'GET':
        return render_template("specialist/add_patient.html", column_names=['Username', 'Email'])
    
    elif request.method == 'POST':
        patient_username = request.form.get("Username")
        patient_email = request.form.get("Email")

        if not patient_username or not patient_email:
            flash("You must fill all the fields", "error")
            return redirect(url_for("specialist.specialist_add_patient"))
        
        patient_id = db.session.query(Users.user_id).filter(Users.username == patient_username, Users.email == patient_email).first()
        
        if not patient_id:
            flash("Error, please check patient's info", "error")
            return redirect(url_for("specialist.specialist_add_patient"))

        new_patient = Patients(specialist_username=specialist_name, user_id=patient_id.user_id)
        db.session.add(new_patient)
        db.session.commit()

        flash("Patient added successfully!", "added patient successfully")
        return redirect(url_for('specialist.specialist_add_patient'))
    
    return redirect(url_for('specialist.specialist_add_patient'))


@specialist_bp.route("/display-patients", methods=['GET'])
@login_required
def display_patients():
    """ Allow specialist to retrieve and see patient's usernames"""

    specialist = session['username']
    patient_usernames = db.session.query(Users.username, Users.user_id).join(Patients, Patients.user_id == Users.user_id).filter(Patients.specialist_username == specialist).all()

    if not patient_usernames:
        flash("There aren't any patients associated with the {specialist} username", "error")

    return render_template("specialist/display_patients.html", patient_usernames=patient_usernames)
    

@specialist_bp.route("/display-patients/<int:patient_id>", methods=['GET', 'POST'])
@login_required
def display_selected_dietplan(patient_id):
    """ Show the selected diet plan """

    if request.method == "GET":
        retrieved_dietplans = db.session.query(DietPlans.dietplan_id, DietPlans.name).filter(DietPlans.user_id == patient_id).all()
        return render_template("specialist/display_selected_dietplan.html", retrieved_dietplans=retrieved_dietplans, patient_id=patient_id)    
    
    elif request.method == "POST":
        diet_plan_id = request.form.get('diet_plan_id')
        if diet_plan_id:     
            diet_plan_info = DietPlans.query.filter_by(dietplan_id=diet_plan_id).first()
            result = (db.session.query(DayTypes.day_name, MealTypes.meal_name, Foods.name, Meals.quantity)
                      .join(Meals, Meals.day_type_id == DayTypes.day_type_id)
                      .join(MealTypes, MealTypes.meal_type_id == Meals.meal_type_id)
                      .join(Foods, Foods.food_id == Meals.food_id)
                      .filter(Meals.dietplan_id == diet_plan_id)
                      .all())
                
            output = defaultdict(lambda: defaultdict(list))
            day_totals = defaultdict(int)

            for row in result:
                day_name, meal_name, food, quantity = row
                output[day_name][meal_name].append((food, quantity))
                day_totals[day_name] += 1

            return render_template("specialist/display_selected_dietplan.html", assigned_meals=output, diet_plan_info=diet_plan_info, patient_id=patient_id, day_totals=day_totals)
        
        flash("Error retrieving the diet plan", "error")

    return redirect(url_for("specialist.display_patients"))


@specialist_bp.route("/add-diet", methods=['GET', 'POST'])
@login_required
def specialist_add_diet():
    """ Allow specialist to create a diet plan for the patients """
    specialist = session["username"]

    if not specialist:
        flash("Specialist not logged in", "error")
        return redirect(url_for('specialist.specialist_login'))
    
    if request.method == "GET":
        try:
            # retrieve a list of patients usernames and id for that specialist
            patients = db.session.query(Patients.user_id, Users.username).join(Users, Users.user_id == Patients.user_id).filter(Patients.specialist_username == specialist).all()
            # if no patient is found or an error occurs return flash message
            if not patients:
                flash("An error occurred while retrieving patients associated with {specialist}", "error")
                return redirect(url_for('specialist.specialist_add_diet'))
            
            # retrieve days, meals and food names
            days = DayTypes.query.all()
            meals = MealTypes.query.all()
            foods = Foods.query.all()
            
            return render_template("specialist/specialist_add_diet.html", patients=patients, days=days, meals=meals, foods=foods)
        except SQLAlchemyError as e:
            logging.error(f"Database error: {e}")
            flash("An error occurred while retrieving data. Please try again later.", "error")
            return redirect(url_for('specialist.specialist_index'))
        
    elif request.method == "POST":
        # Retrieve diet plan details
        patient_id = request.form.get("patient_id")
        diet_name = request.form.get("dietName")
        diet_description = request.form.get("dietDescription")

        if not patient_id or not diet_name or not diet_description:
            flash("All headers fields are required.", "error")
            return redirect(url_for('specialist.specialist_add_diet'))
        
        try:
            # insert new diet plan, create a diet plan obj
            new_diet_plan = DietPlans(user_id = patient_id, name = diet_name, description = diet_description)
            db.session.add(new_diet_plan)
            db.session.flush()

            # create a dict to store meals for every day
            formatted_meal_data = collect_meal_data(request.form, new_diet_plan.dietplan_id)

            if not formatted_meal_data:
                flash("An error occurred while collecting data", "error collecting data")

            insert_meals_and_foods(formatted_meal_data)

            db.session.commit()
            flash("Diet plan added successfully!", "success")
            return redirect(url_for('specialist.specialist_add_diet'))

        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Database error during diet plan addition: {e}")
            flash("An error occurred while adding the diet plan. Please try again.", "error")
            return redirect(url_for('specialist.specialist_add_diet'))
        except BadRequest as e:
            flash(f"Invalid input: {e.description}", "error")
            return redirect(url_for('specialist.specialist_add_diet'))
                
    return render_template("specialist/specialist_add_diet.html")



    