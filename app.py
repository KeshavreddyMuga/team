import os
from datetime import datetime
from flask import Flask, request, redirect, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from dotenv import load_dotenv

load_dotenv()

# ----------------------------------------------------
# CONFIG
# ----------------------------------------------------
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "team_secret_key")

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///team_workspace.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'

# Email Setup
app.config['MAIL_SERVER'] = "smtp.gmail.com"
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = ("Team Workspace", os.getenv("MAIL_USERNAME"))

mail = Mail(app)
db = SQLAlchemy(app)

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# ----------------------------------------------------
# STYLE
# ----------------------------------------------------
STYLE = """
<style>
body { font-family: Arial; padding: 30px; background: #f0f0f0; margin: 0; }
.container { background: white; padding: 25px; border-radius: 10px; max-width: 900px; margin: auto; }
button { padding: 10px 20px; background: black; color: white; border: none; border-radius: 8px; cursor: pointer; }
.small { padding: 6px 14px; }
</style>
"""

# ----------------------------------------------------
# DATABASE MODELS
# ----------------------------------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    email = db.Column(db.String(200), unique=True)
    password = db.Column(db.String(200))

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    weeks = db.Column(db.Integer)
    current_week = db.Column(db.Integer, default=1)

class ProjectWeek(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer)
    week_number = db.Column(db.Integer)
    go_next_members = db.Column(db.Text, default="")

class Upload(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer)
    week_number = db.Column(db.Integer)
    file_name = db.Column(db.String(300))
    uploaded_by = db.Column(db.String(200))
    description = db.Column(db.Text)
    uploaded_time = db.Column(db.DateTime, default=datetime.utcnow)

# ----------------------------------------------------
# EMAIL SENDER
# ----------------------------------------------------
def send_email_to_all(subject, body):
    try:
        emails = [u.email for u in User.query.all() if u.email]
        if not emails:
            return
        mail.send(Message(subject=subject, recipients=emails, body=body))
    except:
        pass

# ----------------------------------------------------
# ROUTES
# ----------------------------------------------------
@app.route("/")
def home():
    return STYLE + """
    <div class='container'>
        <h2>Team Workspace Organizer</h2>
        <a href='/login'><button class='small'>Login</button></a>
        <a href='/register'><button class='small'>Register</button></a>
    </div>
    """

@app.route("/init_db")
def init_db():
    with app.app_context():
        db.create_all()
    return "Database initialized!"

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"].lower()
        pwd = request.form["password"]

        if User.query.filter_by(email=email).first():
            return STYLE + "<h3>Email already exists</h3>"

        db.session.add(User(name=name, email=email, password=pwd))
        db.session.commit()
        return redirect("/login")

    return STYLE + """
    <div class='container'>
      <h2>Register</h2>
      <form method='POST'>
        <label>Name</label><input name='name'>
        <label>Email</label><input name='email'>
        <label>Password</label><input type='password' name='password'>
        <button>Register</button>
      </form>
      <a href='/login'><button class='small'>Login</button></a>
    </div>
    """

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].lower()
        pwd = request.form["password"]
        user = User.query.filter_by(email=email).first()

        if not user or user.password != pwd:
            return STYLE + "<h3>Invalid login</h3>"

        session["user_id"] = user.id
        session["user_name"] = user.name
        return redirect("/dashboard")

    return STYLE + """
    <div class='container'>
      <h2>Login</h2>
      <form method='POST'>
        <label>Email</label><input name='email'>
        <label>Password</label><input type='password' name='password'>
        <button>Login</button>
      </form>
    </div>
    """

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    projects = Project.query.all()
    items = "".join(f"<li><a href='/project/{p.id}'>{p.name}</a></li>" for p in projects)

    return STYLE + f"""
    <div class='container'>
      <h2>Welcome {session['user_name']}</h2>

      <h3>Create Project</h3>
      <form method='POST' action='/create_project'>
        <label>Name</label><input name='name'>
        <label>Weeks</label><input type='number' name='weeks'>
        <button>Create</button>
      </form>

      <h3>Your Projects</h3>
      <ul>{items}</ul>

      <a href='/logout'><button class='small'>Logout</button></a>
    </div>
    """

@app.route("/create_project", methods=["POST"])
def create_project():
    name = request.form["name"]
    weeks = int(request.form["weeks"])

    p = Project(name=name, weeks=weeks)
    db.session.add(p)
    db.session.commit()

    for w in range(1, weeks + 1):
        db.session.add(ProjectWeek(project_id=p.id, week_number=w))
    db.session.commit()

    return redirect("/dashboard")

@app.route("/project/<int:pid>")
def project_page(pid):
    if "user_id" not in session:
        return redirect("/login")

    p = Project.query.get(pid)
    return STYLE + f"""
    <div class='container'>
      <h2>{p.name}</h2>
      <h3>Week {p.current_week}/{p.weeks}</h3>
      <a href='/dashboard'><button class='small'>Back</button></a>
    </div>
    """

@app.route("/project_completed/<int:pid>")
def completed(pid):
    p = Project.query.get(pid)
    return STYLE + f"""
    <div class='container'>
      <h2>🎉 Project Completed</h2>
      <h3>{p.name} is done!</h3>
      <a href='/dashboard'><button class='small'>Back</button></a>
    </div>
    """

# ----------------------------------------------------
# LOCAL RUN
# ----------------------------------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000)
