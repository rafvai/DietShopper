from collections import defaultdict
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy import inspect
from werkzeug.security import check_password_hash, generate_password_hash
from app.models import DayTypes, DietPlans, Foods, MealTypes, Meals, Patients, Specialists, Users
from app.helpers import login_required
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

        # Use ORM to query for the user
        specialist = Specialists.query.filter_by(username=username).first()
    
        if specialist is None or not check_password_hash(specialist.password, password):
            flash("Invalid username and/or password", "error")
            return render_template("specialist/login.html")

        # Clear the current session
        session.clear()

        session['username'] = username 
        return redirect(url_for("specialist.specialist_index"))
    
    return render_template("specialist/login.html")


@specialist_bp.route("/register", methods=['GET', 'POST'])
def specialist_register():
    """ Allow a specialist to request registration """

    if request.method == 'GET':
        # Create an inspector object to retrieve all column names of specialists table
        inspector = inspect(db.engine)
        column_names = []

        for column_info in inspector.get_columns("Specialists"):
            column_name = column_info['name']
            # Don't take specific columns
            if column_name not in ["created_at", "approved"]:
                # Add a confirmation field after the password
                if column_name == "password":
                    column_names.append(column_name.capitalize())
                    column_names.append("Confirmation")
                else:
                    # Capitalize and add
                    column_names.append(column_name.replace("_", " ").capitalize())

        return render_template("specialist/register.html", column_names=column_names)
    
    elif request.method == 'POST':
        username = request.form.get("Username")
        name = request.form.get("Name")
        last_name = request.form.get("Last name")
        email = request.form.get("Email")
        password = request.form.get("Password")
        confirmation = request.form.get("Confirmation")

        # If some fields are missing, return error
        if not all([username, name, last_name, email, password, confirmation]):
            flash("Must fill out all fields", "error")
            return render_template("specialist/register.html", column_names=column_names)

        # If password is not the same as confirmation
        if password != confirmation:
            flash("Passwords don't match", "error")
            return render_template("specialist/register.html", column_names=column_names)

        # If the username is already in use
        if Specialists.query.filter_by(username=username).first():
            flash("Username already in use", "error")
            return render_template("specialist/register.html", column_names=column_names)

        # If email is already in use 
        if Specialists.query.filter_by(email=email).first():
            flash("Email address already in use", "error")
            return render_template("specialist/register.html", column_names=column_names)

        # Hash the password and add all info to db
        hashed_password = generate_password_hash(password)
        new_specialist = Specialists(
            username=username,
            name=name,
            last_name=last_name,
            password=hashed_password, 
            email=email
        )

        # Add new specialist and commit changes
        db.session.add(new_specialist)
        db.session.commit()

        session['username'] = username  
        return redirect(url_for("specialist.specialist_index"))

    return render_template("specialist/register.html", column_names=column_names)

@specialist_bp.route("/index", methods=['GET'])

def specialist_index():
    """ Show specialist home page """
    username = session['username']
    return render_template("specialist/index.html", username=username)

@specialist_bp.route("/logout")
def specialist_logout():
    """ Allow user to log out """
    session.clear()
    return redirect(url_for("main.login"))


@specialist_bp.route("/add-patient", methods=['GET', 'POST'])

def specialist_add_patient():
    """ Allow specialist to add a patient to his list """

    # retrieve specialist name 
    specialist_name = session['username']

    if request.method == 'GET':
        # render the page with the fields in order to find the patient
        return render_template("specialist/add_patient.html", column_names = ['Username', 'Email'])
    
    elif request.method == 'POST':
        patient_username = request.form.get("Username")
        patient_email = request.form.get("Email")

        # handle the case in which field/s is missing
        if not patient_username or not patient_email:
            flash ("You must fill all the fields", "error")
            return redirect(url_for("specialist.specialist_add_patient"))
        
        # retrieve patient id from the info specialist submitted
        patient_id = db.session.query(Users.user_id).filter(Users.username == patient_username, Users.email == patient_email).first()
        
        if not patient_id:
            flash("Error, please check patient's info", "error")
            return redirect(url_for("specialist.specialist_add_patient"))

        # create a patient obj with all info retrieved
        new_patient = Patients(specialist_username = specialist_name, user_id = patient_id.user_id)
        # add into db and commit changes
        db.session.add(new_patient)
        db.session.commit()

        flash("Patient added successfully!", "added patient successfully")
        return redirect(url_for('specialist.specialist_add_patient'))
    
    return redirect(url_for('specialist.specialist_add_patient'))


@specialist_bp.route("/display-patients", methods=['GET'])

def display_patients():
    """ Allow specialist to retrieve and see patient's usernames"""

    specialist = session['username']

    # retrieve all patients usernames associated with that specialist
    patient_usernames = db.session.query(Users.username, Users.user_id).join(Patients, Patients.user_id == Users.user_id).filter(Patients.specialist_username == specialist).all()
    # if not patients
    if not patient_usernames:
        flash ("There aren't any patients associated with the {specialist} username", "error")

    return render_template("specialist/display_patients.html", patient_usernames = patient_usernames)
    

@specialist_bp.route("/display-patients/<int:patient_id>", methods = ['GET','POST'])

def display_selected_dietplan(patient_id):
    """ Show the selected diet plan """

    if request.method == "GET":
        # retrieve all dietplans available for that patient
        retrieved_dietplans = db.session.query(DietPlans.dietplan_id, DietPlans.name).filter(DietPlans.user_id == patient_id).all()
        # return all the names of the dietplans assigned for that user
        return render_template("specialist/display_selected_dietplan.html", retrieved_dietplans = retrieved_dietplans, patient_id=patient_id)    
    
    elif request.method == "POST":
        # retrieve the selected dietplan id info and store it in a variable
        diet_plan_id = request.form.get('diet_plan_id')
        if diet_plan_id:     
            diet_plan_info = DietPlans.query.filter_by(dietplan_id = diet_plan_id).first()
                
            # store the list of all meals for that dietplan
            result = (db.session.query(DayTypes.day_name, MealTypes.meal_name, Foods.name, Meals.quantity)
            .join(Meals, Meals.day_type_id == DayTypes.day_type_id)
            .join(MealTypes, MealTypes.meal_type_id == Meals.meal_type_id)
            .join(Foods, Foods.food_id == Meals.food_id)
            .filter(Meals.dietplan_id == diet_plan_id)
            .all())
                
            # create a default dict in which for every day and meal there's the corresponding food and quantity
            output = defaultdict(lambda: defaultdict(list))

            for row in result:
                day_name =  row[0]
                meal_name = row[1]
                food = row[2]
                quantity = row[3]
                output[day_name][meal_name].append((food, quantity))

            # pass them to frontend
            return render_template("specialist/display_selected_dietplan.html", assigned_meals = output, diet_plan_info = diet_plan_info, patient_id=patient_id)
        
        flash(" Error retrieving the diet plan", "error")

    return redirect(url_for("specialist.display_patients"))
