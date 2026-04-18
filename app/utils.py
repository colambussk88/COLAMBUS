from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user


def require_roles(*roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            if current_user.role not in roles:
                # Redirect to a clear access denied page
                return redirect(url_for("auth.access_denied"))
            return f(*args, **kwargs)

        return wrapped

    return decorator
