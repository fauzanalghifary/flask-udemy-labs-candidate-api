from flask import Flask, render_template, redirect, request, url_for, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_sqlalchemy import SQLAlchemy
import uuid
import datetime
from functools import wraps
import hmac
import hashlib
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import jwt

app = Flask(__name__)
app.config['HMAC_SECRET_KEY'] = 'pyhtonflaskhmacsecretkey'
app.config['BASIC_SECRET_KEY'] = 'basicauthkey'
app.config['JWT_SECRET_KEY'] = 'pyhtonflaskjwtsecretkey'
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///data.db"
db = SQLAlchemy(app)
limiter = Limiter(
    get_remote_address,
    app=app,
)


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


with app.app_context():
    db.drop_all()
    db.create_all()
    db.session.add(Candidate(str(uuid.uuid4()), 'Bruce Wayne', datetime.date(1996, 3, 10), 'brucew@gmail.com', 16000))
    db.session.commit()


def hmac_validator(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        client_hmac = None
        if 'api-signature' in request.headers:
            client_hmac = request.headers['api-signature']
        if not client_hmac:
            return jsonify({'messages': 'Missing headers api-signature'}), 401
        try:
            user_data = request.get_json()
            messages = str(
                request.method + '-' +
                request.path.lstrip('/') + '-' +
                user_data['full_name'] + '-' +
                user_data['birth_date'] + '-' +
                user_data['email'] + '-' +
                str(user_data['expected_salary'])
            ).lower()
            hmac_verifier = hmac.new(app.config['HMAC_SECRET_KEY'].encode('utf-8'), messages.encode('utf-8'),
                                     hashlib.sha256)
            is_verified = hmac.compare_digest(request.headers['api-signature'], hmac_verifier.hexdigest())
        except:
            return jsonify({'message': 'Invalid api-signature'}), 400
        return f(is_verified, *args, **kwargs)

    return decorated


def token_validator(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if 'api-jwt' in request.headers:
            token = request.headers['api-jwt']
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            is_valid_jwt = jwt.decode(token, app.config['JWT_SECRET_KEY'], 'HS256')
        except:
            return jsonify({'message': 'Token is invalid'}), 401
        return f(is_valid_jwt, *args, **kwargs)

    return decorated


@app.route('/api/candidate', methods=['POST'])
@limiter.limit("5/minute")
@hmac_validator
def create_candidate(is_verified):
    if not is_verified:
        api_response = {'message': 'Invalid api-signature'}
        return jsonify(api_response), 400

    data = request.get_json()

    candidate_id = str(uuid.uuid4())
    new_candidate = Candidate(candidate_id, data['full_name'],
                              datetime.datetime.strptime(data['birth_date'], '%Y-%m-%d'), data['email'],
                              data['expected_salary']
                              )
    db.session.add(new_candidate)
    db.session.commit()

    api_response = {'candidate_id': candidate_id}
    return jsonify(api_response), 201


@app.route('/api/candidate/<candidate_id>', methods=['GET'])
@limiter.limit("10/minute")
@token_validator
def get_candidate(is_valid_jwt, candidate_id):
    candidate = Candidate.query.filter_by(candidate_id=candidate_id).first()

    if not candidate:
        api_response = {'message': 'Candidate with this ID not found!'}
        return jsonify(api_response), 404

    if not is_valid_jwt:
        return jsonify(is_valid_jwt), 401

    api_response = {
        'candidate': {'full_name': candidate.full_name, 'birth_date': candidate.birth_date, 'email': candidate.email,
                      'expected_salary': candidate.expected_salary}}
    return jsonify(api_response), 200


@app.route('/api/auth', methods=['POST'])
def login():
    auth = request.authorization

    if not auth or not auth.username or not auth.password:
        api_response = {'message': 'Missing authorization properties'}
        return jsonify(api_response), 401

    candidate = Candidate.query.filter_by(email=auth.username).first()

    if not candidate:
        return jsonify({'message': 'Could not verify'}), 401

    if auth.password == app.config['BASIC_SECRET_KEY']:
        token = jwt.encode(
            {'iss': candidate.full_name,'sub': 'headhunter-candidate',
             'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=5)},
            app.config['JWT_SECRET_KEY'], 'HS256')
        api_response = {'token': token}
        return jsonify(api_response), 200

    api_response = {'message': 'Could not verify'}
    return jsonify(api_response), 401