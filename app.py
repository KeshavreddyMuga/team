# app_option_b.py
import os
import traceback
import requests
from datetime import datetime
from uuid import uuid4
from flask import Flask, request, redirect, session, send_from_directory, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

# ----------------------------------------------------
# FLASK CONFIG
# ----------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "team_secret_key")

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///team_workspace.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.environ.get("UPLOAD_FOLDER", "uploads")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# ----------------------------------------------------
# RESEND CONFIG
# ----------------------------------------------------
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")

db = SQLAlchemy(app)

# ----------------------------------------------------
# STYLE
# ----------------------------------------------------
STYLE = """
<style>
body { font-family: Arial; background:#eef; padding:20px; }
.container { background:white; padding:20px; border-radius:12px; box-shadow:0 0 10px rgba(0,0,0,0.1); max-width:900px; margin:auto; }
button { padding:10px; background:black; color:white; border:none; border-radius:6px; cursor:pointer; margin-top:10px; }
input, textarea, select { width:100%; padding:10px; border:1px solid #ccc; margin-top:5px; border-radius:6px; }
.badge { display:inline-block; padding:6px 10px; background:#ddd; border-radius:6px; margin-right:6px; }
.success { color:green; font-weight:bold; }
.small { font-size:0.9em; color:#555; }
</style>
"""

def logout_btn():
    return "<a href='/logout' style='float:right;padding:10px;'>Logout</a>" if session.get("user_id") else ""

# ----------------------------------------------------
# MODELS
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
    completed = db.Column(db.Boolean, default=False)
    completed_time = db.Column(db.DateTime, nullable=True)

class Upload(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer)
    week_number = db.Column(db.Integer)
    file_name = db.Column(db.String(300))
    uploaded_by = db.Column(db.String(200))
    description = db.Column(db.Text)
    uploaded_time = db.Column(db.DateTime, default=datetime.utcnow)

class ProjectMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer)
    user_id = db.Column(db.Integer)

class WeekStatus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer)
    week_number = db.Column(db.Integer)
    user_id = db.Column(db.Integer)
    action = db.Column(db.String(20))  # 'next' or 'finish'
    clicked_time = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# ----------------------------------------------------
# EMAIL HELPERS
# ----------------------------------------------------
def send_email(to, subject, body):
    try:
        url = "https://api.resend.com/emails"
        payload = {
            "from": SENDER_EMAIL,
            "to": to,
            "subject": subject,
            "text": body
        }
        headers = {
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        }
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        app.logger.info("RESEND %s %s", r.status_code, r.text)
        return r.status_code in (200, 201)
    except Exception as e:
        app.logger.exception("EMAIL ERROR")
        return False

def notify_members(project_id, subject, body):
    member_rows = ProjectMember.query.filter_by(project_id=project_id).all()
    for m in member_rows:
        u = User.query.get(m.user_id)
        if u and u.email:
            send_email(u.email, subject, body)

# ----------------------------------------------------
# ROUTES (auth + basic)
# ----------------------------------------------------
@app.route("/")
def home():
    return STYLE + logout_btn() + """
    <div class='container'>
        <h2>Team Workspace (Option B)</h2>
        <a href='/login'><button>Login</button></a>
        <a href='/register'><button>Register</button></a>
        <p>Each project can have its own members in this mode.</p>
    </div>
"""

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"].lower()
        pwd = request.form["password"]
        if User.query.filter_by(email=email).first():
            return STYLE + "<script>alert('Email exists');window.location='/register';</script>"
        db.session.add(User(name=name, email=email, password=pwd))
        db.session.commit()
        return redirect("/login")
    return STYLE + """
    <div class='container'>
        <h2>Register</h2>
        <form method='POST'>
            <input name='name' placeholder='Name'>
            <input name='email' placeholder='Email'>
            <input name='password' type='password' placeholder='Password'>
            <button>Register</button>
        </form>
        <a href='/login'><button>Login</button></a>
    </div>
"""

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].lower()
        pwd = request.form["password"]
        user = User.query.filter_by(email=email).first()
        if not user or user.password != pwd:
            return STYLE + "<script>alert('Invalid login');window.location='/login';</script>"
        session["user_id"] = user.id
        session["user_name"] = user.name
        return redirect("/dashboard")
    return STYLE + """
    <div class='container'>
        <h2>Login</h2>
        <form method='POST'>
            <input name='email'>
            <input type='password' name='password'>
            <button>Login</button>
        </form>
        <a href='/register'><button>Register</button></a>
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
    items = ""
    for p in projects:
        member_count = ProjectMember.query.filter_by(project_id=p.id).count()
        items += f"<li><a href='/project/{p.id}'>{p.name} (Week {p.current_week}/{p.weeks}) - Members: {member_count}</a></li>"
    return STYLE + logout_btn() + f"""
    <div class='container'>
        <h2>Welcome {session['user_name']}</h2>
        <form method='POST' action='/create_project'>
            <input name='name' placeholder='Project Name'>
            <input name='weeks' type='number' placeholder='Weeks'>
            <button>Create</button>
        </form>
        <ul>{items}</ul>
    </div>
"""

@app.route("/create_project", methods=["POST"])
def create_project():
    if "user_id" not in session:
        return redirect("/login")
    name = request.form["name"]
    weeks = int(request.form["weeks"])
    p = Project(name=name, weeks=weeks)
    db.session.add(p)
    db.session.commit()
    # add creator as member by default
    db.session.add(ProjectMember(project_id=p.id, user_id=session["user_id"]))
    db.session.commit()
    return redirect("/dashboard")

@app.route("/project/<int:pid>/add_member", methods=["POST"])
def add_member(pid):
    if "user_id" not in session:
        return redirect("/login")
    email = request.form.get("email","").lower()
    u = User.query.filter_by(email=email).first()
    if not u:
        return STYLE + "<script>alert('User not found. Ask them to register first.');window.location='/project/{}';</script>".format(pid)
    exists = ProjectMember.query.filter_by(project_id=pid, user_id=u.id).first()
    if exists:
        return redirect(f"/project/{pid}")
    db.session.add(ProjectMember(project_id=pid, user_id=u.id))
    db.session.commit()
    notify_members(pid, "Added to project", f"You were added to project ID {pid}.")
    return redirect(f"/project/{pid}")

@app.route("/download/<path:f>")
def download(f):
    return send_from_directory(app.config["UPLOAD_FOLDER"], f, as_attachment=True)

# ----------------------------------------------------
# PROJECT PAGE + UPLOADS + NEXT/FINISH logic (Option B)
# ----------------------------------------------------
@app.route("/project/<int:pid>", methods=["GET","POST"])
def project(pid):
    if "user_id" not in session:
        return redirect("/login")
    p = Project.query.get(pid)
    if not p:
        return STYLE + "<div class='container'>Project not found</div>"

    # upload
    if request.method == "POST" and 'file' in request.files:
        f = request.files["file"]
        desc = request.form.get("description", "")
        fname = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + uuid4().hex[:5] + "_" + secure_filename(f.filename)
        f.save(os.path.join(app.config["UPLOAD_FOLDER"], fname))
        db.session.add(Upload(project_id=pid, week_number=p.current_week, file_name=fname, uploaded_by=session["user_name"], description=desc))
        db.session.commit()
        notify_members(pid, f"New upload in {p.name}", f"{session['user_name']} uploaded {f.filename}")
        return redirect(f"/project/{pid}")

    # lists
    uploads = Upload.query.filter_by(project_id=pid, week_number=p.current_week).all()
    files = "".join(f"<div>{u.file_name} — <a href='/download/{u.file_name}'>Download</a></div>" for u in uploads)

    uid = session["user_id"]
    is_member = ProjectMember.query.filter_by(project_id=pid, user_id=uid).first() is not None
    members = ProjectMember.query.filter_by(project_id=pid).all()
    member_count = len(members)
    member_list_html = ""
    for m in members:
        u = User.query.get(m.user_id)
        member_list_html += f"<div>{u.name} — {u.email}</div>"

    next_clicked = WeekStatus.query.filter_by(project_id=pid, week_number=p.current_week, user_id=uid, action='next').first() is not None
    finish_clicked = WeekStatus.query.filter_by(project_id=pid, week_number=p.current_week, user_id=uid, action='finish').first() is not None

    next_count = WeekStatus.query.filter_by(project_id=pid, week_number=p.current_week, action='next').count()
    finish_count = WeekStatus.query.filter_by(project_id=pid, week_number=p.current_week, action='finish').count()

    show_join_ui = False
    # allow project owner or members to add new members easily: for simplicity allow any member to add
    if is_member:
        show_join_ui = True

    if p.completed:
        return STYLE + logout_btn() + f"""
        <div class='container'>
            <h2>{p.name} — Completed</h2>
            <p class='success'>YOUR TEAM SUCCESSFULLY COMPLETED THE PROJECT 🎉</p>
        </div>
        """

    return STYLE + logout_btn() + f"""
    <div class='container'>
        <h2>{p.name}</h2>
        <div>
            <span class='badge'>Week {p.current_week} / {p.weeks}</span>
            <span class='badge'>Next clicked: {next_count}/{member_count}</span>
            <span class='badge'>Finish clicked: {finish_count}/{member_count}</span>
        </div>
        <hr/>
        <h4>Members</h4>
        {member_list_html}
        {"<div style='margin-top:8px;'><form method='POST' action='/project/"+str(pid)+"/add_member'><input name='email' placeholder='Member email to add'><button>Add Member</button></form></div>" if show_join_ui else "<p class='small'>Only project members can add others.</p>"}
        <hr/>
        {files}
        <form method='POST' enctype='multipart/form-data'>
            <input type='file' name='file'>
            <textarea name='description' placeholder='Description'></textarea>
            <button>Upload</button>
        </form>
        <div style='margin-top:12px;'>
            {("<form method='POST' action='/project/"+str(pid)+"/click_next'><button>Go to Next Week</button></form>" if not next_clicked and is_member else "<div style='margin-top:8px;'>You already clicked Next or you are not a member.</div>")}
            {("<form method='POST' action='/project/"+str(pid)+"/click_finish'><button>Finish Project</button></form>" if (p.current_week==p.weeks and not finish_clicked and is_member) else "")}
        </div>
    </div>
    """

@app.route("/project/<int:pid>/click_next", methods=["POST"])
def click_next(pid):
    if "user_id" not in session:
        return redirect("/login")
    p = Project.query.get(pid)
    if not p or p.completed:
        return redirect(f"/project/{pid}")
    uid = session["user_id"]
    # must be a member to click
    if not ProjectMember.query.filter_by(project_id=pid, user_id=uid).first():
        return redirect(f"/project/{pid}")
    existing = WeekStatus.query.filter_by(project_id=pid, week_number=p.current_week, user_id=uid, action='next').first()
    if existing:
        return redirect(f"/project/{pid}")
    ws = WeekStatus(project_id=pid, week_number=p.current_week, user_id=uid, action='next')
    db.session.add(ws)
    db.session.commit()
    notify_members(pid, f"{session['user_name']} clicked Go to Next Week", f"{session['user_name']} clicked Go to Next Week for project {p.name} (Week {p.current_week}).")
    # check if all members clicked
    members = ProjectMember.query.filter_by(project_id=pid).all()
    member_count = len(members)
    next_count = WeekStatus.query.filter_by(project_id=pid, week_number=p.current_week, action='next').count()
    if next_count >= member_count and member_count > 0:
        if p.current_week < p.weeks:
            p.current_week += 1
            db.session.commit()
            notify_members(pid, f"Project {p.name} advanced to Week {p.current_week}", f"All members clicked Next. Project {p.name} is now at Week {p.current_week}.")
    return redirect(f"/project/{pid}")

@app.route("/project/<int:pid>/click_finish", methods=["POST"])
def click_finish(pid):
    if "user_id" not in session:
        return redirect("/login")
    p = Project.query.get(pid)
    if not p or p.completed:
        return redirect(f"/project/{pid}")
    uid = session["user_id"]
    if not ProjectMember.query.filter_by(project_id=pid, user_id=uid).first():
        return redirect(f"/project/{pid}")
    existing = WeekStatus.query.filter_by(project_id=pid, week_number=p.current_week, user_id=uid, action='finish').first()
    if existing:
        return redirect(f"/project/{pid}")
    ws = WeekStatus(project_id=pid, week_number=p.current_week, user_id=uid, action='finish')
    db.session.add(ws)
    db.session.commit()
    notify_members(pid, f"{session['user_name']} clicked Finish", f"{session['user_name']} clicked Finish on project {p.name} (Week {p.current_week}).")
    members = ProjectMember.query.filter_by(project_id=pid).all()
    member_count = len(members)
    finish_count = WeekStatus.query.filter_by(project_id=pid, week_number=p.current_week, action='finish').count()
    if finish_count >= member_count and member_count > 0:
        p.completed = True
        p.completed_time = datetime.utcnow()
        db.session.commit()
        notify_members(pid, f"Project {p.name} — Completed", f"Congratulations! Project {p.name} has been completed by all members.")
    return redirect(f"/project/{pid}")

@app.route("/test_email")
def test_email():
    ok = send_email("keshavareddymuga@gmail.com", "Test", "Resend email working!")
    return "OK" if ok else "FAILED"

# ----------------------------------------------------
# RUN SERVER
# ----------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
