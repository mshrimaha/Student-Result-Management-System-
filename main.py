import os
import json
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from replit import db

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-change-me")

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

SUBJECTS = ["Mathematics", "Science", "English", "History", "Computer"]
STUDENT_PREFIX = "student:"


def student_key(student_id):
    return f"{STUDENT_PREFIX}{student_id.strip().upper()}"


def get_student(student_id):
    key = student_key(student_id)
    if key in db.keys():
        raw = db[key]
        try:
            return json.loads(raw) if isinstance(raw, str) else dict(raw)
        except Exception:
            return dict(raw) if hasattr(raw, "items") else None
    return None


def save_student(record):
    db[student_key(record["id"])] = json.dumps(record)


def delete_student(student_id):
    key = student_key(student_id)
    if key in db.keys():
        del db[key]
        return True
    return False


def list_students():
    students = []
    for key in db.prefix(STUDENT_PREFIX):
        raw = db[key]
        try:
            data = json.loads(raw) if isinstance(raw, str) else dict(raw)
            students.append(data)
        except Exception:
            continue
    students.sort(key=lambda s: s.get("id", ""))
    return students


def compute_stats(marks):
    values = [int(v) for v in marks.values()]
    total = sum(values)
    count = len(values) or 1
    average = round(total / count, 2)
    if average >= 90:
        grade = "A+"
    elif average >= 80:
        grade = "A"
    elif average >= 70:
        grade = "B"
    elif average >= 60:
        grade = "C"
    elif average >= 50:
        grade = "D"
    else:
        grade = "F"
    passed = all(v >= 35 for v in values)
    return {
        "total": total,
        "max_total": count * 100,
        "average": average,
        "grade": grade,
        "status": "PASS" if passed else "FAIL",
    }


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            flash("Please log in to access the admin area.", "error")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapper


def parse_form(form):
    student_id = form.get("id", "").strip().upper()
    name = form.get("name", "").strip()
    marks = {}
    errors = []
    if not student_id:
        errors.append("Student ID is required.")
    if not name:
        errors.append("Student name is required.")
    for subject in SUBJECTS:
        raw = form.get(subject, "").strip()
        if raw == "":
            errors.append(f"Marks for {subject} are required.")
            continue
        try:
            value = int(raw)
        except ValueError:
            errors.append(f"Marks for {subject} must be a whole number.")
            continue
        if value < 0 or value > 100:
            errors.append(f"Marks for {subject} must be between 0 and 100.")
            continue
        marks[subject] = value
    return student_id, name, marks, errors


@app.route("/")
def home():
    total_students = len(list(db.prefix(STUDENT_PREFIX)))
    return render_template("index.html", total_students=total_students, subjects=SUBJECTS)


@app.route("/results", methods=["GET", "POST"])
def results():
    student = None
    stats = None
    searched_id = ""
    if request.method == "POST":
        searched_id = request.form.get("student_id", "").strip().upper()
        if not searched_id:
            flash("Please enter a Student ID.", "error")
        else:
            student = get_student(searched_id)
            if student is None:
                flash(f"No record found for Student ID '{searched_id}'.", "error")
            else:
                stats = compute_stats(student.get("marks", {}))
    return render_template(
        "results.html",
        student=student,
        stats=stats,
        searched_id=searched_id,
        subjects=SUBJECTS,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin"] = True
            flash("Welcome back, admin.", "success")
            next_url = request.args.get("next") or url_for("admin")
            return redirect(next_url)
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("admin", None)
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


@app.route("/admin")
@login_required
def admin():
    students = list_students()
    return render_template("admin.html", students=students, subjects=SUBJECTS)


@app.route("/admin/add", methods=["GET", "POST"])
@login_required
def admin_add():
    form_data = {"id": "", "name": "", "marks": {s: "" for s in SUBJECTS}}
    if request.method == "POST":
        student_id, name, marks, errors = parse_form(request.form)
        form_data = {
            "id": student_id,
            "name": name,
            "marks": {s: request.form.get(s, "") for s in SUBJECTS},
        }
        if not errors and get_student(student_id) is not None:
            errors.append(f"A student with ID '{student_id}' already exists.")
        if errors:
            for err in errors:
                flash(err, "error")
        else:
            save_student({"id": student_id, "name": name, "marks": marks})
            flash(f"Student '{name}' (ID: {student_id}) added successfully.", "success")
            return redirect(url_for("admin"))
    return render_template(
        "edit.html",
        mode="add",
        form_data=form_data,
        subjects=SUBJECTS,
    )


@app.route("/admin/edit/<student_id>", methods=["GET", "POST"])
@login_required
def admin_edit(student_id):
    student = get_student(student_id)
    if student is None:
        flash(f"No record found for Student ID '{student_id}'.", "error")
        return redirect(url_for("admin"))
    form_data = {
        "id": student["id"],
        "name": student["name"],
        "marks": {s: str(student["marks"].get(s, "")) for s in SUBJECTS},
    }
    if request.method == "POST":
        new_id, name, marks, errors = parse_form(request.form)
        form_data = {
            "id": new_id,
            "name": name,
            "marks": {s: request.form.get(s, "") for s in SUBJECTS},
        }
        if not errors and new_id != student["id"] and get_student(new_id) is not None:
            errors.append(f"A student with ID '{new_id}' already exists.")
        if errors:
            for err in errors:
                flash(err, "error")
        else:
            if new_id != student["id"]:
                delete_student(student["id"])
            save_student({"id": new_id, "name": name, "marks": marks})
            flash(f"Student '{name}' (ID: {new_id}) updated successfully.", "success")
            return redirect(url_for("admin"))
    return render_template(
        "edit.html",
        mode="edit",
        form_data=form_data,
        subjects=SUBJECTS,
        original_id=student["id"],
    )


@app.route("/admin/delete/<student_id>", methods=["POST"])
@login_required
def admin_delete(student_id):
    if delete_student(student_id):
        flash(f"Student '{student_id}' deleted.", "success")
    else:
        flash(f"No record found for Student ID '{student_id}'.", "error")
    return redirect(url_for("admin"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
