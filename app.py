from flask import Flask, render_template, redirect, request, url_for, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_sqlalchemy import SQLAlchemy
import uuid
import random

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///carcatalog.db"
db = SQLAlchemy(app)

# The lab is behind a http proxy, so it's not aware of the fact that it should use https.
# We use ProxyFix to enable it: https://flask.palletsprojects.com/en/2.0.x/deploying/wsgi-standalone/#proxy-setups
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)


# Used for any other security related needs by extensions or application, i.e. csrf token
app.config['SECRET_KEY'] = 'mysecretkey'

# Required for cookies set by Flask to work in the preview window that's integrated in the lab IDE
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = True

# Required to render urls with https when not in a request context. Urls within Udemy labs must use https
app.config['PREFERRED_URL_SCHEME'] = 'https'


@app.route("/")
def index():
    print('Received headers', request.headers)
    return render_template('index.html')


@app.route("/redirect/")
def redirect_to_index():
    return redirect(url_for('index'))


class Candidate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.String(50), unique=True)
    full_name = db.Column(db.String(50))
    birth_date = db.Column(db.Date)
    email = db.Column(db.String(50))
    expected_salary = db.Column(db.Integer)

    def __init__(self, candidate_id, full_name, birth_date, email, expected_salary):
        self.candidate_id = candidate_id
        self.full_name = full_name
        self.birth_date = birth_date
        self.email = email
        self.expected_salary = expected_salary
