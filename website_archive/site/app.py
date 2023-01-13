# region Imports
import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session.__init__ import Session
from functools import wraps
from helpers import login_required
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

import os
import pathlib
import requests
from flask import Flask, session, abort, redirect, request
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from pip._vendor import cachecontrol
import google.auth.transport.requests
# endregion
# region Configure application
app = Flask(__name__)
app.secret_key = "xMp7LnAc57ibKL"  #it is necessary to set a password when dealing with OAuth 2.0

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
GOOGLE_CLIENT_ID = "440122758723-grgqfn671i4hufekd3lannqif31cp2a9.apps.googleusercontent.com" 
client_secrets_file = os.path.join(pathlib.Path(__file__).parent, "client_secret.json")  
flow = Flow.from_client_secrets_file(  #Flow is OAuth 2.0 a class that stores all the information on how we want to authorize our users
    client_secrets_file=client_secrets_file,
    scopes=["https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email", "openid"],  #here we are specifing what do we get after the authorization
    redirect_uri="http://127.0.0.1:5000/callback"  #and the redirect URI is the point where the user will end up after the authorization
)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# db = SQL("sqlite:///users.db")

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# endregion

@app.route("/callback")  #this is the page that will handle the callback process meaning process after the authorization
def callback():
    flow.fetch_token(authorization_response=request.url)

    if not session["state"] == request.args["state"]:
        abort(500)  #state does not match!

    credentials = flow.credentials
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=cached_session)
    id_info = id_token.verify_oauth2_token(
        id_token=credentials._id_token,
        request=token_request,
        audience=GOOGLE_CLIENT_ID
    )

    session["google_id"] = id_info.get("sub")  #defing the results to show on the page
    session["name"] = id_info.get("name")
    session["credentials"] = credentials
    return redirect("/protected_area")  #the final page where the authorized users will end up

#region Main Routes
@app.route("/")
def index():
    if not session.get('google_id'):
        return render_template("landing.html")
    
    creds, _ = google.auth.default()
    drive_service = build('drive', 'v3', credentials=creds)
    results = drive_service.files().list(pageSize=10, fields="nextPageToken, files(id, name)").execute()
    items = results.get("files", [])

    # Print the names and IDs of the files
    if not items:
        print('No files found.')
    else:
        print('Files:')
        for item in items:
            print(f'{item["name"]} ({item["id"]})')
        return render_template("index.html")

@app.route("/login")
def login():
    authorization_url, state = flow.authorization_url()  #asking the flow class for the authorization (login) url
    session["state"] = state
    return redirect(authorization_url)

@app.route("/logout")  #the logout page and function
def logout():
    session.clear()
    return redirect("/")

@app.route("/protected_area")
@login_required
def protected_area():
    print(session['google_id'])
    return f"Hello {session['name']}! <br/> <a href='/logout'><button>Logout</button></a>"  #the logout button 
# endregion