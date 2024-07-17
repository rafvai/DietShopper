
from flask import redirect, request, session, url_for


def login_required(f):

    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('specialist.specialist_login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function