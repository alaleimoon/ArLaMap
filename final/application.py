import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, send_file, make_response, send_from_directory
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
import random
import requests
import re

from helpers import apology, login_required

# For upload
from flask import Flask, flash, request, redirect, url_for
from werkzeug.utils import secure_filename
from flask import send_from_directory




# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# For uploads
UPLOAD_FOLDER = '/home/ubuntu/final/static/img'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024



# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response



# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///archmap.db")


global_message = None


@app.route("/")

def index():
    # select all images from db
    images_all = db.execute("SELECT filename FROM images")

    # randomly select images
    random.shuffle(images_all)
    images = []
    len_images = len(images_all)
    if len_images > 56:
        len_images = 56
    for i in range(len_images):
        images.append(images_all[i])

    # set bought message
    global_messagetemp = None
    global global_message
    if global_message:
        global_messagetemp = global_message
        global_message = None
    return render_template("index.html", global_message=global_messagetemp, images=images)
    # return apology("TODO")


@app.route("/place", methods=["GET", "POST"])
def place():
    if request.method == "POST":
        if request.form.get("filename"):
            filename=request.form.get("filename")
            place_ifm = db.execute("SELECT * FROM places WHERE id = (SELECT place_id FROM images WHERE filename = ?)", filename)

        if request.form.get("place_id"):
            place_id=request.form.get("place_id")
            place_ifm = db.execute("SELECT * FROM places WHERE id = ?", place_id)

        if request.form.get("name"):
            name = request.form.get("name")
            place_ifm = db.execute("SELECT * FROM places WHERE name = ?", name)

        filenames = db.execute("SELECT filename FROM images WHERE place_id = ?", place_ifm[0]["id"])
        return render_template("place.html", filenames=filenames, place_ifm=place_ifm[0])
    return render_template("place.html")

@app.route("/places_list")
def places_list():
    places = db.execute("SELECT * FROM places")
    return render_template("places_list.html", places=places)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():

    """Upload images"""
    if request.method == 'POST':
        # check for null
        if not request.form.get("place_name"):
            flash('No place name')
            return redirect(request.url)

        if not request.form.get("address"):
            flash('No address')
            return redirect(request.url)

        if not request.form.get("description"):
            flash('No description')
            return redirect(request.url)

        # upload function codes from flask tutorial
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)

        file = request.files['file']
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

            #check if duplicate filename:
            files = db.execute("SELECT * FROM images WHERE filename = ?", filename)
            print(len(files))
            if len(files) != 0:
                flash('Please rename the file')
                return redirect(request.url)
            else:
                # save the image
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                # save information in db:places
                place_name = request.form.get("place_name")
                address = request.form.get("address")
                description = request.form.get("description")
                db.execute("INSERT INTO places (name, address, description) VALUES (?,?,?)", place_name, address, description)

                # save information in db:images
                place_id = db.execute("SELECT id FROM places WHERE name = ?", place_name)
                db.execute("INSERT INTO images (filename, place_id) VALUES (?,?)", filename, place_id[0]["id"])

                # download, search and save latitude and longitude information in db:markers
                add_latlng(place_name, address)

                # success information
                flash('upload success')

        # Redirect user to home page
        return redirect(request.url)
    else:
        return render_template("upload.html")


@app.route("/map", methods=["GET"])
def map():
    # select all markers from db
    convert2xml();
    return render_template("map.html")

@app.route("/get-csv/<csv_id>")
def get_csv(csv_id):
    filename = f"{csv_id}.xml"
    try:
        return send_from_directory("/home/ubuntu/final/data/", filename=filename, as_attachment=True)
    except FileNotFoundError:
        return None


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["username"] = rows[0]["username"]

        # Redirect user to home page
        return redirect("/upload")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/changepw", methods=["GET", "POST"])
def changepw():
    if request.method == "POST":
        # Ensure password was submitted
        if not request.form.get("newpw"):
            return apology("must provide new password", 403)
        # hash the new pw
        newpw = request.form.get("newpw")
        password_hash = generate_password_hash(newpw)

        # upadte pw
        db.execute("UPDATE users SET hash = ? WHERE id = ?", password_hash, session["user_id"])

        # return changed message
        global global_message
        global_message = "Password Changed!"
        # Redirect user to home page
        return redirect("/")

    else:
        return render_template("changepw.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


quote_result = {}



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Ensure password was submitted
        elif not request.form.get("confirmation"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Make sure username whether repeated or not
        if len(rows) != 0:
            return apology("Username used", 403)
        # check the pw match
        if not request.form.get("password") == request.form.get("confirmation"):
            return apology("Passwords do not match", 403)

        # Hash the pw
        password = request.form.get("password")
        password_hash = generate_password_hash(password)

        # insert
        username_r = request.form.get("username")
        db.execute("INSERT INTO users (username, hash) VALUES(?,?)", username_r, password_hash)


        # Redirect user to home page
        return redirect("/")
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")



def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# convert the sql information into xml file
def convert2xml():
    markers = db.execute("SELECT * FROM markers")

    header1 = '<?xml version="1.0" encoding="UTF-8"?>\n'
    header2 = "<markers>\n"
    footer = "</markers>"

    result = ''

    for marker in markers:
        add = '    <marker id="'+ str(marker['id']) +'" name="'+ str(marker['name']) +'" address="'+ str(marker['address']) +'" lat="'+ str(marker['lat']) +'" lng="'+ str(marker['lng']) +'" type="'+ str(marker['type']) +'" />\n'
        result = result + add

    result = header1 + header2 + result + footer

    with open('/home/ubuntu/final/data/markers.xml', 'w') as file:
        file.write(result)
    file.close()
    return 0


# Search for the index of a string in a sentence: https://blog.csdn.net/tan197/article/details/82708505
def index_of_str(s1, s2):
    lt=s1.split(s2,1)
    if len(lt)==1:
        return -1
    return len(lt[0])

# Find the latitude and longitude number from the xml file downloaded from google
def search(s1, s2):
    f = open('1.xml', 'r')
    for line in f:
        index1 = index_of_str(line, s1)
        if index1 == 1:
            index2 = int(index_of_str(line, s2))
            result = line[len(s1)+1:index2]
            f.close()
            return(result)
    f.close()


# download, search, add latitude and longitude information to the sql db
def add_latlng(name, address):
    url = 'https://maps.googleapis.com/maps/api/geocode/xml?address=' + name + '&key=AIzaSyCxzw7yQm3P21o8SQRsQT61mr-Ky8mPcUM'
    r = requests.get(url)
    with open("1.xml", "wb") as code:
         code.write(r.content)

    lat1 = "    <lat>"
    lat2 = "</lat>"
    lng1 = "    <lng>"
    lng2 = "</lng>"
    typ1 = "  <type>"
    typ2 = "</type>"

    lat = search(lat1, lat2)
    lng = search(lng1, lng2)
    typ = search(typ1, typ2)

    db.execute("INSERT INTO markers (name, address, lat, lng, type) VALUES (?,?,?,?,?)", name, address, lat, lng, typ)
    return 0


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
