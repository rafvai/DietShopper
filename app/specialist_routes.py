from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy import inspect
from werkzeug.security import check_password_hash, generate_password_hash
from app.models import Specialists, Patients
from . import db


specialist_bp = Blueprint('specialist',__name__,url_prefix='/specialist')

@specialist_bp.route("/login", methods = ['GET', 'POST'])
def specialist_login():
    """ Allow specialists to log in """
    
    if request.method == 'GET':
        # create an inspector obj to retrieve column names
        inspector = inspect(db.engine)
        fields = []

        for column_info in inspector.get_columns('Specialists'):
            column_name = column_info['name']
            # skip columns with an automatic assigned value
            if column_name not in ["specialist_id", "created_at"]:
                fields.append(column_name.capitalize())
    
        return render_template("specialist/login.html", column_names = fields)
    
    elif request.method == 'POST':
        username = request.form.get("Username")
        password = request.form.get("Password")

        if not username or not password:
            flash("Must input valid username and password", "error")
            return render_template("specialist/login.html")

        # Use ORM to query for the user
        specialist = Specialists.query.filter_by(username=username).first()
    
        if specialist is None:
            flash("Invalid username and/or password", "error")
            return render_template("specialist/login.html")

        # Check password
        if not check_password_hash(specialist.password, password):
            flash("Invalid username and/or password", "error")
            return render_template("specialist/login.html")
        
        # clear the current session
        session.clear()

        session["user_id"] = specialist.user_id
        return redirect(url_for("specialist.specialist_index"))
    
    return render_template("specialist/login.html")


    

