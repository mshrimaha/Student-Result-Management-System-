import os
import io
import json
import random
import sqlite3
from functools import wraps
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect, url_for, session, flash, send_file, abort, g
)
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-change-me")

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

INSTITUTION_NAME = os.environ.get(
    "INSTITUTION_NAME",
    "Visvesvaraya Technological University",
)
INSTITUTION_TAGLINE = os.environ.get(
    "INSTITUTION_TAGLINE",
    "Jnana Sangama, Belagavi - 590018, Karnataka",
)
INSTITUTION_OFFICE = os.environ.get(
    "INSTITUTION_OFFICE",
    "Office of the Registrar (Evaluation)",
)

SUBJECTS = ["Mathematics", "Science", "English", "History", "Computer"]

# ---------- SQLite storage ----------
DATABASE_PATH = os.environ.get("DATABASE_PATH", "database.db")


def get_db():
    """Return a per-request SQLite connection."""
    conn = getattr(g, "_database", None)
    if conn is None:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g._database = conn
    return conn


@app.teardown_appcontext
def close_db(exc):
    conn = getattr(g, "_database", None)
    if conn is not None:
        conn.close()


def init_db():
    """Create the students table if it does not already exist."""
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                id      TEXT PRIMARY KEY,
                name    TEXT NOT NULL,
                college TEXT NOT NULL DEFAULT '',
                marks   TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_record(row):
    if row is None:
        return None
    try:
        marks = json.loads(row["marks"]) if row["marks"] else {}
    except (TypeError, ValueError):
        marks = {}
    return {
        "id": row["id"],
        "name": row["name"],
        "college": row["college"] or "",
        "marks": marks,
    }


def get_student(student_id):
    sid = student_id.strip().upper()
    cur = get_db().execute(
        "SELECT id, name, college, marks FROM students WHERE id = ?", (sid,)
    )
    return _row_to_record(cur.fetchone())


def save_student(record):
    sid = record["id"].strip().upper()
    conn = get_db()
    conn.execute(
        """
        INSERT INTO students (id, name, college, marks)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            college = excluded.college,
            marks = excluded.marks
        """,
        (sid, record["name"], record.get("college", ""), json.dumps(record.get("marks", {}))),
    )
    conn.commit()


def delete_student(student_id):
    sid = student_id.strip().upper()
    conn = get_db()
    cur = conn.execute("DELETE FROM students WHERE id = ?", (sid,))
    conn.commit()
    return cur.rowcount > 0


def list_students():
    cur = get_db().execute(
        "SELECT id, name, college, marks FROM students ORDER BY id ASC"
    )
    return [_row_to_record(row) for row in cur.fetchall()]


def count_students():
    cur = get_db().execute("SELECT COUNT(*) AS n FROM students")
    return cur.fetchone()["n"]


def grade_for_marks(value):
    """VTU CBCS (2022 Scheme) letter grade for a single subject score out of 100."""
    if value >= 90:
        return "O"
    if value >= 80:
        return "A+"
    if value >= 70:
        return "A"
    if value >= 60:
        return "B+"
    if value >= 50:
        return "B"
    if value >= 45:
        return "C"
    if value >= 40:
        return "P"
    return "F"


def compute_stats(marks):
    values = [int(v) for v in marks.values()]
    total = sum(values)
    count = len(values) or 1
    average = round(total / count, 2)
    grade = grade_for_marks(average)
    passed = all(v >= 40 for v in values)
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
    college = form.get("college", "").strip()
    marks = {}
    errors = []
    if not student_id:
        errors.append("USN is required.")
    if not name:
        errors.append("Student name is required.")
    if not college:
        errors.append("College name is required.")
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
    return student_id, name, college, marks, errors


# ---------- Captcha ----------

def generate_captcha():
    a = random.randint(2, 12)
    b = random.randint(2, 12)
    op = random.choice(["+", "-"])
    answer = a + b if op == "+" else a - b
    question = f"What is {a} {op} {b}?"
    session["captcha_answer"] = str(answer)
    session["captcha_question"] = question
    return question


def verify_captcha(user_answer):
    expected = session.pop("captcha_answer", None)
    session.pop("captcha_question", None)
    if expected is None:
        return False
    return user_answer.strip() == expected


# ---------- Routes ----------

@app.route("/docs")
def docs():
    return render_template("docs.html")


@app.route("/")
def home():
    total_students = count_students()
    return render_template("index.html", total_students=total_students, subjects=SUBJECTS)


@app.route("/results", methods=["GET", "POST"])
def results():
    student = None
    stats = None
    form_data = {"student_id": "", "full_name": "", "captcha": ""}

    if request.method == "POST":
        form_data["student_id"] = request.form.get("student_id", "").strip().upper()
        form_data["full_name"] = request.form.get("full_name", "").strip()
        form_data["captcha"] = request.form.get("captcha", "").strip()

        # Verify captcha first (this consumes it regardless)
        captcha_ok = verify_captcha(form_data["captcha"])

        if not form_data["student_id"] or not form_data["full_name"]:
            flash("Please enter both your Student ID and full name.", "error")
        elif not captcha_ok:
            flash("Captcha answer was incorrect. Please try again.", "error")
        else:
            record = get_student(form_data["student_id"])
            if record is None or record.get("name", "").strip().lower() != form_data["full_name"].lower():
                # Do not reveal whether the ID exists — keep error generic for privacy
                flash(
                    "We could not find a result matching that Student ID and name. "
                    "Please double-check your details.",
                    "error",
                )
            else:
                student = record
                stats = compute_stats(student.get("marks", {}))
                # Issue a short-lived token so the same student can download a PDF
                session["pdf_token"] = {"id": student["id"], "name": student["name"]}

    captcha_question = generate_captcha()

    return render_template(
        "results.html",
        student=student,
        stats=stats,
        form_data=form_data,
        subjects=SUBJECTS,
        captcha_question=captcha_question,
        grade_for=grade_for_marks,
    )


@app.route("/results/pdf")
def results_pdf():
    token = session.get("pdf_token")
    if not token:
        flash("Please look up your result before downloading the PDF.", "error")
        return redirect(url_for("results"))

    student = get_student(token["id"])
    if student is None or student.get("name", "").strip().lower() != token["name"].strip().lower():
        flash("Result is no longer available. Please search again.", "error")
        return redirect(url_for("results"))

    stats = compute_stats(student.get("marks", {}))
    pdf_buffer = build_marks_card_pdf(student, stats)

    filename = f"marks_card_{student['id']}.pdf"
    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


def build_marks_card_pdf(student, stats):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Marks Card - {student['id']}",
        author=INSTITUTION_NAME,
    )

    styles = getSampleStyleSheet()
    primary = colors.HexColor("#1a2238")
    accent = colors.HexColor("#3b5bdb")
    muted = colors.HexColor("#5b6478")
    soft_bg = colors.HexColor("#eaf0ff")

    title_style = ParagraphStyle(
        "Title", parent=styles["Heading1"], alignment=TA_CENTER,
        fontSize=22, textColor=primary, spaceAfter=2, leading=26,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle", parent=styles["Normal"], alignment=TA_CENTER,
        fontSize=11, textColor=muted, spaceAfter=4,
    )
    eyebrow_style = ParagraphStyle(
        "Eyebrow", parent=styles["Normal"], alignment=TA_CENTER,
        fontSize=9, textColor=accent, spaceAfter=2,
        fontName="Helvetica-Bold", letterSpacing=2,
    )
    section_style = ParagraphStyle(
        "Section", parent=styles["Heading3"], fontSize=12,
        textColor=primary, spaceBefore=10, spaceAfter=6,
    )
    label_style = ParagraphStyle(
        "Label", parent=styles["Normal"], fontSize=9,
        textColor=muted, fontName="Helvetica",
    )
    value_style = ParagraphStyle(
        "Value", parent=styles["Normal"], fontSize=12,
        textColor=primary, fontName="Helvetica-Bold", spaceAfter=4,
    )
    footer_style = ParagraphStyle(
        "Footer", parent=styles["Normal"], fontSize=8,
        textColor=muted, alignment=TA_CENTER,
    )

    story = []

    # Header
    story.append(Paragraph(INSTITUTION_NAME.upper(), title_style))
    story.append(Paragraph(INSTITUTION_TAGLINE, subtitle_style))
    story.append(Paragraph(INSTITUTION_OFFICE, subtitle_style))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1.2, color=accent))
    story.append(Spacer(1, 6))
    story.append(Paragraph("OFFICIAL PROVISIONAL RESULT SHEET", eyebrow_style))
    story.append(Spacer(1, 14))

    # Student info block (two columns)
    issued_on = datetime.now().strftime("%d %b %Y")
    college = student.get("college", "—")
    info_data = [
        [Paragraph("USN (UNIVERSITY SEAT NUMBER)", label_style), Paragraph("STUDENT NAME", label_style)],
        [Paragraph(student["id"], value_style), Paragraph(student["name"], value_style)],
        [Paragraph("COLLEGE / INSTITUTE", label_style), Paragraph("SCHEME", label_style)],
        [Paragraph(college, value_style), Paragraph("CBCS — 2022 Scheme", value_style)],
        [Paragraph("DATE OF ISSUE", label_style), Paragraph("EXAMINATION", label_style)],
        [Paragraph(issued_on, value_style), Paragraph("Semester End Examination", value_style)],
    ]
    info_table = Table(info_data, colWidths=[85 * mm, 85 * mm])
    info_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e3e7f0")))

    # Marks table
    story.append(Paragraph("Subject-wise Marks", section_style))
    header = ["#", "Course / Subject", "Max", "Marks Obtained", "Grade", "Result"]
    rows = [header]
    for i, subject in enumerate(SUBJECTS, start=1):
        mark = int(student["marks"].get(subject, 0))
        rows.append([
            str(i),
            subject,
            "100",
            str(mark),
            grade_for_marks(mark),
            "P" if mark >= 40 else "F",
        ])
    rows.append(["", Paragraph("<b>TOTAL</b>", styles["Normal"]),
                 str(stats["max_total"]), str(stats["total"]), "", ""])

    marks_table = Table(rows, colWidths=[10 * mm, 65 * mm, 18 * mm, 30 * mm, 20 * mm, 22 * mm])
    marks_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), primary),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("ALIGN", (2, 1), (5, -1), "CENTER"),
        ("ALIGN", (0, 1), (0, -1), "CENTER"),
        ("FONTSIZE", (0, 1), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f7f9fd")]),
        ("BACKGROUND", (0, -1), (-1, -1), soft_bg),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d6dcea")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(marks_table)
    story.append(Spacer(1, 14))

    # Summary block
    summary_data = [
        [
            Paragraph("PERCENTAGE", label_style),
            Paragraph("FINAL GRADE", label_style),
            Paragraph("OVERALL RESULT", label_style),
        ],
        [
            Paragraph(f"<b>{stats['average']}%</b>", value_style),
            Paragraph(f"<b>{stats['grade']}</b>", value_style),
            Paragraph(f"<b>{stats['status']}</b>", value_style),
        ],
    ]
    summary_table = Table(summary_data, colWidths=[55 * mm, 55 * mm, 60 * mm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), soft_bg),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#c5d0ee")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c5d0ee")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 30))

    # Signatures
    sig_data = [
        ["", "", ""],
        [
            Paragraph("_____________________<br/>Class Teacher", footer_style),
            Paragraph("_____________________<br/>Examination Officer", footer_style),
            Paragraph("_____________________<br/>Registrar (Evaluation)", footer_style),
        ],
    ]
    sig_table = Table(sig_data, colWidths=[57 * mm, 57 * mm, 57 * mm])
    sig_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 24))
    story.append(HRFlowable(width="100%", thickness=0.4, color=colors.HexColor("#d6dcea")))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"This is a system-generated document issued by {INSTITUTION_NAME}. "
        "If any discrepancy is found, contact the examinations office.",
        footer_style,
    ))

    doc.build(story)
    buf.seek(0)
    return buf


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
    form_data = {"id": "", "name": "", "college": "", "marks": {s: "" for s in SUBJECTS}}
    if request.method == "POST":
        student_id, name, college, marks, errors = parse_form(request.form)
        form_data = {
            "id": student_id,
            "name": name,
            "college": college,
            "marks": {s: request.form.get(s, "") for s in SUBJECTS},
        }
        if not errors and get_student(student_id) is not None:
            errors.append(f"A student with USN '{student_id}' already exists.")
        if errors:
            for err in errors:
                flash(err, "error")
        else:
            save_student({"id": student_id, "name": name, "college": college, "marks": marks})
            flash(f"Student '{name}' (USN: {student_id}) added successfully.", "success")
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
        "college": student.get("college", ""),
        "marks": {s: str(student["marks"].get(s, "")) for s in SUBJECTS},
    }
    if request.method == "POST":
        new_id, name, college, marks, errors = parse_form(request.form)
        form_data = {
            "id": new_id,
            "name": name,
            "college": college,
            "marks": {s: request.form.get(s, "") for s in SUBJECTS},
        }
        if not errors and new_id != student["id"] and get_student(new_id) is not None:
            errors.append(f"A student with USN '{new_id}' already exists.")
        if errors:
            for err in errors:
                flash(err, "error")
        else:
            if new_id != student["id"]:
                delete_student(student["id"])
            save_student({"id": new_id, "name": name, "college": college, "marks": marks})
            flash(f"Student '{name}' (USN: {new_id}) updated successfully.", "success")
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


init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
