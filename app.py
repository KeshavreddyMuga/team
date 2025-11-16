import os
import traceback
from datetime import datetime
from flask import Flask, request, redirect, session, url_for, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message

# ----------------------------------------------------
# CONFIG
# ----------------------------------------------------
app = Flask(__name__)
app.secret_key = "team_secret_key"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///team_workspace.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'

# Email setup
app.config['MAIL_SERVER'] = "smtp.gmail.com"
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = "keshavareddymuga@gmail.com"
app.config['MAIL_PASSWORD'] = "qsggsnebvaafshqb"
app.config['MAIL_DEFAULT_SENDER'] = ("Team Workspace", "keshavareddymuga@gmail.com")

mail = Mail()
mail.init_app(app)

db = SQLAlchemy(app)

# Render uses eventlet → async_mode="eventlet"
socketio = SocketIO(app, async_mode="eventlet")

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# ----------------------------------------------------
# STYLE + SOCKET + JS
# ----------------------------------------------------
STYLE = """
<link href='https://cdn.jsdelivr.net/npm/@sweetalert2/theme-dark@5/dark.css' rel='stylesheet'>
<script src='https://cdn.jsdelivr.net/npm/sweetalert2@11'></script>
<script src="https://cdn.socket.io/4.6.1/socket.io.min.js"></script>

<style>
body {
    font-family: Arial;
    background: linear-gradient(135deg,#9b5de5,#f15bb5,#00bbf9,#00f5d4);
    padding: 30px; margin: 0; background-attachment: fixed;
}
.container {
    background: #f5e9ff; padding:25px; border-radius:14px;
    max-width:920px; margin:auto; box-shadow:0 0 25px rgba(0,0,0,0.2);
    position: relative;
}
label { font-weight:bold; margin-top:12px; display:block; }
input, textarea, select {
    width:100%; padding:12px; margin-top:5px;
    border-radius:8px; border:1px solid #bbb;
    box-sizing: border-box;
}
button {
    width:100%; padding:12px; margin-top:12px;
    border-radius:10px; border:none; cursor:pointer;
    color:#fff; background:linear-gradient(45deg,#000,#444);
}
button.small { width:auto; padding:8px 14px; font-size:14px; }
.row { display:flex; gap:12px; flex-wrap:wrap; }
a { text-decoration:none; color:#1a73e8; }
a:hover { text-decoration:underline; }
.top-right-btn { position:absolute; top:15px; right:15px; }
.upload-item { padding:10px; border-bottom:1px solid #ddd; }
.meta { font-size:13px; color:#555; margin-top:6px; }
.small-note { font-size:13px; color:#333; margin-top:12px; }
.link-btn { background:none; border:none; color:#1a73e8; cursor:pointer; text-decoration:underline; padding:0; }
</style>

<script>
var socket = io();
window.currentProjectId = null;

socket.on('project_completed', function(data) {
  if (!data) return;
  Swal.fire({
    icon: 'success',
    title: 'Project Completed 🎉',
    text: 'Project \"' + data.name + '\" has been completed.',
    confirmButtonText: 'OK'
  }).then(function(){
    if (window.currentProjectId && parseInt(window.currentProjectId) === parseInt(data.pid)) {
      window.location = '/project_completed/' + data.pid;
    }
  });
});
</script>
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
# EMAIL HELPER
# ----------------------------------------------------
def send_email_to_all(subject, body):
    try:
        with app.app_context():
            emails = [u.email for u in User.query.all() if u.email]
            if not emails:
                return False
            msg = Message(subject=subject, recipients=emails, body=body)
            mail.send(msg)
            return True
    except Exception:
        traceback.print_exc()
        return False

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

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").lower().strip()
        pwd = request.form.get("password", "")

        if not name or not email or not pwd:
            return STYLE + """
            <script>
            Swal.fire('Missing Fields','Please fill all fields.','error')
              .then(()=>{window.location='/register'});
            </script>
"""

        if User.query.filter_by(email=email).first():
            return STYLE + """
            <script>
            Swal.fire({
              icon: 'error',
              title: 'Email Exists',
              text: 'Try logging in.',
              showCancelButton: true,
              confirmButtonText: 'Login',
              cancelButtonText: 'Retry'
            }).then((res)=>{
              if(res.isConfirmed) window.location='/login';
              else window.location='/register';
            })
            </script>
"""
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
        <div style='margin-top:12px'>
            <a href='/login'><button class='small'>Login</button></a>
        </div>
    </div>
"""

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        pwd = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if not user or user.password != pwd:
            return STYLE + """
            <script>
            Swal.fire('Invalid Login','Wrong email or password.','error')
              .then(()=>{window.location='/login'});
            </script>
"""
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
        <div style='margin-top:12px'>
            <a href='/register'><button class='small'>Register</button></a>
        </div>
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
    proj_html = "".join(f"<li><a href='/project/{p.id}'>{p.name}</a> — {p.weeks} Weeks</li>" for p in projects)
    return STYLE + f"""
    <div class='container'>
        <h2>Welcome {session['user_name']}</h2>

        <h3>Create Project</h3>
        <form method='POST' action='/create_project'>
            <label>Project Name</label><input name='name'>
            <label>Weeks</label><input type='number' name='weeks' min='1'>
            <button>Create Project</button>
        </form>

        <h3>Your Projects</h3>
        <ul>{proj_html or 'No projects yet'}</ul>

        <a href='/logout'><button class='small'>Logout</button></a>
    </div>
"""

@app.route("/create_project", methods=["POST"])
def create_project():
    name = request.form.get("name", "").strip()
    weeks = int(request.form.get("weeks", "1"))
    if weeks < 1:
        weeks = 1

    p = Project(name=name, weeks=weeks)
    db.session.add(p)
    db.session.commit()

    for w in range(1, weeks + 1):
        db.session.add(ProjectWeek(project_id=p.id, week_number=w))
    db.session.commit()

    return redirect("/dashboard")

@app.route("/download/<path:filename>")
def download(filename):
    if ".." in filename or filename.startswith("/"):
        return "Invalid filename", 400
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if not os.path.exists(file_path):
        return "File not found", 404
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)

@app.route("/project/<int:pid>", methods=["GET","POST"])
def project_page(pid):
    if "user_id" not in session:
        return redirect("/login")
    p = Project.query.get(pid)
    if not p:
        return STYLE + "<div class='container'><h3>Project not found.</h3></div>"

    pw = ProjectWeek.query.filter_by(project_id=pid, week_number=p.current_week).first()
    if not pw:
        pw = ProjectWeek(project_id=pid, week_number=p.current_week)
        db.session.add(pw)
        db.session.commit()

    # Upload File
    if request.method == "POST":
        f = request.files.get("file")
        desc = (request.form.get("description") or "").strip()
        if f and f.filename:
            fname = secure_filename(f.filename)
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], fname)

            base, ext = os.path.splitext(fname)
            counter = 1
            while os.path.exists(save_path):
                fname = f"{base}_{counter}{ext}"
                save_path = os.path.join(app.config["UPLOAD_FOLDER"], fname)
                counter += 1

            f.save(save_path)

            up = Upload(
                project_id=pid,
                week_number=p.current_week,
                file_name=fname,
                uploaded_by=session.get("user_name", "Unknown"),
                description=desc,
                uploaded_time=datetime.utcnow()
            )
            db.session.add(up)
            db.session.commit()

            send_email_to_all(
                f"New File Uploaded - {p.name} (Week {p.current_week})",
                f"{up.uploaded_by} uploaded '{up.file_name}'.\n\n{desc}"
            )

            return redirect(f"/project/{pid}")

    # Handle Go Next / Finish
    if request.args.get("go_next"):
        uid = str(session["user_id"])
        clicked = pw.go_next_members.split(",") if pw.go_next_members else []

        if uid not in clicked:
            clicked.append(uid)
            pw.go_next_members = ",".join([c for c in clicked if c])
            db.session.commit()

        total_users = User.query.count()

        if total_users > 0 and len(clicked) >= total_users:

            # FINISH PROJECT
            if p.current_week == p.weeks:
                send_email_to_all(
                    f"Project Completed - {p.name}",
                    f"The project '{p.name}' has been completed!"
                )
                socketio.emit('project_completed', {'pid': pid, 'name': p.name})

                return STYLE + f"""
                <script>
                Swal.fire({{
                    icon:'success',
                    title:'Project Completed 🎉',
                    text:'Project "{p.name}" is finished!'
                }}).then(()=>{{ window.location='/project_completed/{pid}'; }});
                </script>
                """

            # MOVE TO NEXT WEEK
            old = p.current_week
            p.current_week += 1

            next_pw = ProjectWeek.query.filter_by(project_id=pid, week_number=p.current_week).first()
            if not next_pw:
                next_pw = ProjectWeek(project_id=pid, week_number=p.current_week)
                db.session.add(next_pw)

            pw.go_next_members = ""
            next_pw.go_next_members = ""
            db.session.commit()

            send_email_to_all(
                f"Week Advanced - {p.name}",
                f"Project '{p.name}' moved from Week {old} to Week {p.current_week}."
            )

        return redirect(f"/project/{pid}")

    latest = Upload.query.filter_by(project_id=pid, week_number=p.current_week).order_by(Upload.uploaded_time.desc()).first()
    if latest:
        file_html = f"<p><b>{latest.uploaded_by}</b> uploaded <b>{latest.file_name}</b> — <a href='/download/{latest.file_name}'>Download</a><br>{latest.description or ''}</p>"
    else:
        file_html = "<p>No files yet</p>"

    week_buttons = "".join(f"<a href='/project/{pid}/week/{w}'><button class='small'>Week {w}</button></a> " for w in range(1, p.current_week + 1))

    clicked_names = []
    if pw.go_next_members:
        for uid in pw.go_next_members.split(","):
            if uid.isdigit():
                u = User.query.get(int(uid))
                if u:
                    clicked_names.append(u.name)

    return STYLE + f"""
    <script>window.currentProjectId = {pid};</script>
    <a class='top-right-btn' href='/project/{pid}/weeks'><button class='small'>Week Details</button></a>
    <div class='container'>
        <h2>{p.name} — Week {p.current_week}/{p.weeks}</h2>
        <div>{week_buttons}</div>
        {file_html}
        <form method='POST' enctype='multipart/form-data'>
            <label>Select File</label><input type='file' name='file'>
            <label>Description</label><textarea name='description'></textarea>
            <button>Upload</button>
        </form>
        <a href='?go_next=1'><button class='small'>{'Finish Project' if p.current_week==p.weeks else 'Go Next Week'}</button></a>
        <p class='small-note'><b>Members who clicked:</b> {', '.join(clicked_names) if clicked_names else 'None yet'}</p>
        <a href='/dashboard'><button class='small'>Back</button></a>
    </div>
"""

@app.route("/project/<int:pid>/weeks")
def project_weeks(pid):
    if "user_id" not in session:
        return redirect("/login")
    p = Project.query.get(pid)
    if not p:
        return STYLE + "<div class='container'><h3>Project not found.</h3></div>"
    buttons = "".join(f"<a href='/project/{pid}/week/{w}'><button class='small'>Week {w}</button></a> " for w in range(1, p.current_week+1))
    return STYLE + f"""
    <div class='container'>
        <h2>Week Details — {p.name}</h2>
        {buttons}
        <a href='/project/{pid}'><button class='small'>Back</button></a>
    </div>
"""

@app.route("/project/<int:pid>/week/<int:week_number>")
def project_week_uploads(pid, week_number):
    if "user_id" not in session:
        return redirect("/login")
    p = Project.query.get(pid)
    if not p:
        return STYLE + "<div class='container'><h3>Project not found.</h3></div>"
    if week_number < 1 or week_number > p.current_week:
        return STYLE + f"<div class='container'><h3>Week not accessible.</h3><a href='/project/{pid}'><button class='small'>Back</button></a></div>"

    uploads = Upload.query.filter_by(project_id=pid, week_number=week_number).order_by(Upload.uploaded_time.desc()).all()
    uploads_html = ""
    for u in uploads:
        t = u.uploaded_time.strftime("%Y-%m-%d %H:%M:%S UTC")
        uploads_html += f"""
        <div class='upload-item'>
            <b>{u.file_name}</b> — <a href='/download/{u.file_name}'>Download</a>
            <div class='meta'>Uploaded by {u.uploaded_by} | {t}</div>
            <div>{u.description or ''}</div>
        </div>
        """

    if not uploads_html:
        uploads_html = "<p>No uploads for this week.</p>"

    return STYLE + f"""
    <div class='container'>
        <h2>{p.name} — Week {week_number} Uploads</h2>
        {uploads_html}
        <a href='/project/{pid}'><button class='small'>Back</button></a>
    </div>
"""

@app.route("/project_completed/<int:pid>")
def project_completed(pid):
    p = Project.query.get(pid)
    if not p:
        return STYLE + "<div class='container'><h3>Project not found.</h3></div>"
    return STYLE + f"""
    <div class='container'>
        <h2>Project Completed 🎉</h2>
        <h3>{p.name} is finished.</h3>
        <a href='/dashboard'><button class='small'>Back</button></a>
    </div>
"""

# ----------------------------------------------------
# RUN (Local Only)
# Render will use Gunicorn
# ----------------------------------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    socketio.run(app, host="0.0.0.0", port=5000)
