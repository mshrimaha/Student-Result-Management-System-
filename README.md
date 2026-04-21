# VTU Student Result Management System

A Python Flask web application that simulates the **Visvesvaraya Technological University
(VTU)** result management workflow. Administrators record per-subject marks for students
identified by their **USN (University Seat Number)**, and students retrieve their
**Official Provisional Result Sheet** as a branded, downloadable PDF.

> This system is designed to **simulate the VTU (Visvesvaraya Technological University)
> result management workflow**. It is not connected to the live VTU examination system —
> all data is stored in a local **SQLite** file (`database.db`) — but the identifiers,
> grading scheme, and PDF layout follow VTU conventions.

## Features

- **Public result lookup** — students authenticate with USN + full name and clear a math captcha.
- **Admin dashboard** — protected CRUD over student records (USN, name, college, marks).
- **VTU-style PDF marks card** — one-click download titled *"Official Provisional Result Sheet"*.
- **Per-college branding** — every student record carries its own affiliated college / institute.
- **Portable SQLite storage** — runs on any free Python host without an external database service.
- **Documentation page** built into the app at `/docs`.

## Tech Stack

- **Python 3.11** — runtime
- **Flask** — web framework, sessions, Jinja2 templates
- **SQLite** — file-based relational database via Python's built-in `sqlite3` module
- **ReportLab** — PDF generation
- **Vanilla HTML / CSS** — no frontend framework

## Data Storage (SQLite)

All student data is persisted to a single SQLite file named **`database.db`**, created
automatically the first time the app starts. The schema is intentionally minimal:

```sql
CREATE TABLE students (
    id      TEXT PRIMARY KEY,   -- USN, normalized to uppercase
    name    TEXT NOT NULL,
    college TEXT NOT NULL DEFAULT '',
    marks   TEXT NOT NULL       -- JSON blob of subject → marks
);
```

In Python, each row is exposed as a dictionary:

```json
{
  "id":      "1VT22CS001",
  "name":    "Jane Doe",
  "college": "RV College of Engineering, Bengaluru",
  "marks": {
    "Mathematics": 92,
    "Science":     88,
    "English":     76,
    "History":     81,
    "Computer":    95
  }
}
```

Storing the marks as a JSON column keeps the schema flexible — the list of subjects can
change without a migration.

### Hosting on a free platform

Because the database is just a file on disk, you can deploy this project on any free
Python host (Render, Railway, Fly.io, PythonAnywhere, a personal VPS, etc.) without
provisioning a separate database. Steps are typically:

1. Push this repository to GitHub.
2. Create a new **Web Service** on your chosen host, pointing it at the repo.
3. Use `pip install -r requirements.txt` (or rely on the `pyproject.toml`) as the build command.
4. Use `python main.py` as the start command. The host's `PORT` environment variable is honoured.
5. If your host gives you a persistent disk (e.g. Render's "Disk", Fly.io volumes), point
   `DATABASE_PATH` at a file inside that disk (e.g. `/data/database.db`) so the data
   survives restarts and re-deploys.

> A minimal `requirements.txt` for hosts that need it:
> ```
> flask>=3.1
> reportlab>=4.4
> ```

## Grading Criteria — VTU CBCS 2022 Scheme

Letter grades for each subject (and for the overall percentage) follow the **VTU Choice
Based Credit System — 2022 Scheme**:

| Marks (out of 100) | Grade | Description    |
|--------------------|-------|----------------|
| 90 – 100           | O     | Outstanding    |
| 80 – 89            | A+    | Excellent      |
| 70 – 79            | A     | Very Good      |
| 60 – 69            | B+    | Good           |
| 50 – 59            | B     | Above Average  |
| 45 – 49            | C     | Average        |
| 40 – 44            | P     | Pass           |
| Below 40           | F     | Fail           |

**Pass rule:** A student is marked **PASS** only if they score at least **40 / 100 in
every subject**. A score below 40 in any subject results in an overall **FAIL**,
regardless of the percentage.

**Percentage:** sum of marks ÷ number of subjects, rounded to two decimals.

## Institutional Branding

The application is pre-branded for VTU but the branding is environment-driven, not
hard-coded. The same code can issue marks cards for any institution by changing three
environment variables:

| Variable               | Default                                                | Where it appears                                           |
|------------------------|--------------------------------------------------------|------------------------------------------------------------|
| `INSTITUTION_NAME`     | `Visvesvaraya Technological University`                | Top heading of the PDF and the footer disclaimer.          |
| `INSTITUTION_TAGLINE`  | `Jnana Sangama, Belagavi - 590018, Karnataka`          | Address line directly under the university name.           |
| `INSTITUTION_OFFICE`   | `Office of the Registrar (Evaluation)`                 | Issuing-office line on the PDF, mirroring VTU's wording.   |

### How a university-specific PDF is generated

1. The student authenticates on `/results` with USN + name and the captcha — a one-time
   download token is stored in the session.
2. Clicking **Download as PDF** triggers `/results/pdf`, which re-validates the token
   against the stored record.
3. The handler calls `build_marks_card_pdf()` in `main.py`, which uses ReportLab's
   `SimpleDocTemplate`, `Paragraph`, and `Table` flowables to lay out an A4 page.
4. The header reads `INSTITUTION_NAME`, `INSTITUTION_TAGLINE`, and `INSTITUTION_OFFICE`
   from the environment, then prints the standard sub-title
   **"OFFICIAL PROVISIONAL RESULT SHEET"**.
5. The body table renders the student's USN, name, college / institute, the
   scheme (*CBCS — 2022 Scheme*), and a numbered subject-wise marks table whose grades
   are computed via `grade_for_marks()` using the VTU table above.
6. The finished PDF is streamed to the browser as `marks_card_<USN>.pdf`.

## Project Structure

```
main.py              # Flask app, routes, SQLite helpers, PDF builder
database.db          # SQLite database file (auto-created)
templates/           # Jinja2 HTML templates
  base.html          # Shared layout
  index.html         # Homepage
  results.html       # Public result lookup + result sheet
  login.html         # Admin login form
  admin.html         # Admin dashboard
  edit.html          # Add / edit student form
  docs.html          # In-app documentation
static/style.css     # All styling
README.md            # This file
```

## Running Locally

```
pip install flask reportlab
python main.py
```

The app listens on `http://localhost:5000`. Default admin credentials are
`admin` / `admin123` — change them by setting `ADMIN_USERNAME` and `ADMIN_PASSWORD`.

## Configuration Reference

| Variable               | Default                                                | Purpose                                          |
|------------------------|--------------------------------------------------------|--------------------------------------------------|
| `SESSION_SECRET`       | *(dev key)*                                            | Flask session signing key.                       |
| `DATABASE_PATH`        | `database.db`                                          | Path to the SQLite database file on disk.        |
| `ADMIN_USERNAME`       | `admin`                                                | Admin login username.                            |
| `ADMIN_PASSWORD`       | `admin123`                                             | Admin login password.                            |
| `INSTITUTION_NAME`     | `Visvesvaraya Technological University`                | University name on the PDF.                      |
| `INSTITUTION_TAGLINE`  | `Jnana Sangama, Belagavi - 590018, Karnataka`          | Address line on the PDF.                         |
| `INSTITUTION_OFFICE`   | `Office of the Registrar (Evaluation)`                 | Issuing-office line on the PDF.                  |
| `PORT`                 | `5000`                                                 | Port Flask listens on.                           |
