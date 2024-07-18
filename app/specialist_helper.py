
from flask import redirect, request, session, url_for
from sqlalchemy import inspect
from . import db


def login_required(f):

    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('specialist.specialist_login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def get_specialist_column_names():
    inspector = inspect(db.engine)
    column_names = []

    for column_info in inspector.get_columns("Specialists"):
        column_name = column_info['name']
        if column_name not in ["created_at", "approved"]:
            if column_name == "password":
                column_names.append(column_name.capitalize())
                column_names.append("Confirmation")
            else:
                column_names.append(column_name.replace("_", " ").capitalize())

    return column_names