"""Decorator that redirects to the setup wizard when setup is incomplete.

Usage::

    from web.setup_guard import setup_complete_required

    @bp.route("/")
    @login_required
    @setup_complete_required
    def index():
        ...

The decorator checks :func:`web.setup_state.is_setup_complete` on every
request to the wrapped view.  If setup has not been completed the user is
redirected to :func:`web.routes.setup_wizard.index` so they can finish the
wizard before reaching operational pages.

This guard is intentionally separate from ``login_required`` so the two
concerns can be combined in any order without coupling.
"""

from __future__ import annotations

import functools

from flask import current_app, redirect, url_for

from web.setup_state import is_setup_complete


def setup_complete_required(view):
    """Redirect to the setup wizard if setup has not been completed.

    Wraps a Flask view function so that any request to that view is
    intercepted and redirected to ``/setup/`` when
    :func:`web.setup_state.is_setup_complete` returns ``False``.

    Args:
        view: The Flask view function to protect.

    Returns:
        The wrapped view function with the setup guard applied.
    """

    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        app = current_app._get_current_object()
        if not is_setup_complete(app):
            return redirect(url_for("setup.index"))
        return view(*args, **kwargs)

    return wrapped
