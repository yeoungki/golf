from flask import Blueprint, render_template, request
from werkzeug.utils import redirect

bp = Blueprint('main', __name__, url_prefix='/')


@bp.route('/')
def index():
    return render_template('index.html')

@bp.route('/work')
def work():
    results = check_login()
    if results:
        # Correct username and password
        return render_template('work.html', message='Welcome, admin!')
    else:
        # Incorrect username or password
        return render_template('work.html', message='Invalid credentials. Please try again.')    

def check_login():
    return render_template('work.html')