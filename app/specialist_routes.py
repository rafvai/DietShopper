from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy import inspect
from werkzeug.security import check_password_hash, generate_password_hash
from app.models import Specialists
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

        session["user_id"] = specialist.specialist_id  # Ensure correct user_id field
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
            if column_name not in ["specialist_id", "created_at", "approved"]:
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

        session["user_id"] = new_specialist.specialist_id  # Ensure correct user_id field
        return redirect(url_for("specialist.specialist_index"))

    return render_template("specialist/register.html", column_names=column_names)

@specialist_bp.route("/index", methods=['GET'])
def specialist_index():
    """ Show specialist home page """

    return render_template("specialist/index.html")