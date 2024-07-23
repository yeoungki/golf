from flask import Blueprint, url_for, render_template, flash, request, session, g
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import redirect
from flask_login import logout_user, login_required
from project import db
from project.forms import UserLoginForm
from project.models import User

bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/')
def index():
    return "Hello, World!"

@bp.route('/login', methods=('GET', 'POST'))
def login():
    form = UserLoginForm()
    if request.method == 'POST':
        print("*****************")
        error = None
        user = User.query.filter_by(user_id=form.username.data).first()  # 평문으로 비교할 때도 username으로 조회
        print(user)
        if not user:
            error = "존재하지 않는 사용자입니다."
        elif user.password != form.password.data:  
            error = "비밀번호가 올바르지 않습니다."
        if error is None:
            session.clear()
            session['user_id'] = user.id
            print("***********OK***********")
            return redirect(url_for('main.work'))  # 로그인 성공 시 work 페이지로 리다이렉트
        else:
            print("***********NG***********")
            flash('가입된 회원아이디가 아니거나 비밀번호가 틀립니다. 비밀번호는 대소문자를 구분합니다')
            return redirect(url_for('auth.login'))
        
    return render_template('auth/login.html', form=form)

@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = User.query.get(user_id)