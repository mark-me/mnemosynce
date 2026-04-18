"""Authentication: login, logout, and the login-required decorator.

In development (APP_ENV=development) the login check is bypassed entirely —
all routes are accessible without a session. This lets you iterate quickly
without logging in on every restart.

In production every protected route redirects to /login if no valid session
exists.
"""

import functools

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

bp = Blueprint("auth", __name__)


def login_required(view):
    """Decorator that enforces authentication in production.

    In development the wrapped view is called directly without any session
    check, so you never need to log in locally.
    """

    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if current_app.config["APP_ENV"] == "development":
            return view(*args, **kwargs)
        if not session.get("logged_in"):
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


@bp.route("/login", methods=["GET", "POST"])
def login():
    """Render and process the login form for the admin interface.

    This validates submitted credentials against the configured admin user
    and password, establishes a session on success, and redirects to the
    originally requested page or the main index.

    Returns:
        A rendered login template for GET requests or failed logins, or
        a redirect response on successful authentication.
    """
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if (
            username == current_app.config["ADMIN_USER"]
            and password == current_app.config["ADMIN_PASSWORD"]
        ):
            session.clear()
            session["logged_in"] = True
            next_page = request.args.get("next") or url_for("main.index")
            return redirect(next_page)
        flash("Invalid username or password.", "danger")
    return render_template("web/login.html")


@bp.route("/logout")
def logout():
    """Log the current user out and redirect them to the login page.

    This clears any session data associated with the user so subsequent
    requests are treated as unauthenticated.
    """
    session.clear()
    return redirect(url_for("auth.login"))
