# VTU Student Result Management System

A Python Flask web application that simulates the **Visvesvaraya Technological University
(VTU)** result management workflow. Administrators record per-subject marks for students
identified by their **USN (University Seat Number)**, and students retrieve their
**Official Provisional Result Sheet** as a branded, downloadable PDF.

> This system is designed to **simulate the VTU (Visvesvaraya Technological University)
> result management workflow**. It is not connected to the live VTU examination system —
> all data is stored locally in Replit Database — but the identifiers, grading scheme,
> and PDF layout follow VTU conventions.

## Features

- **Public result lookup** — students authenticate with USN + full name and clear a math captcha.
- **Admin dashboard** — protected CRUD over student records (USN, name, college, marks).
- **VTU-style PDF marks card** — one-click download titled *"Official Provisional Result Sheet"*.
- **Per-college branding** — every student record carries its own affiliated college / institute.
- **Documentation page** built into the app at `/docs`.

## Tech Stack

- **Python 3.11** — runtime
- **Flask** — web framework, sessions, Jinja2 templates
- **Replit Database** — key-value persistence via the `replit` Python package
- **ReportLab** — PDF generation
- **Vanilla HTML / CSS** — no frontend framework

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

Because the **college / institute** field lives on each student record, a single
deployment of the app can issue branded VTU result sheets for students from many
different affiliated colleges with no code changes.

## Project Structure

```
main.py              # Flask app, routes, storage helpers, PDF builder
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

## Data Model

Each student is stored under the key `student:<UPPERCASE_USN>`:

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

## Running Locally

The workflow `Start application` runs `python main.py` on port 5000.

Default admin credentials are `admin` / `admin123` — change them by setting
`ADMIN_USERNAME` and `ADMIN_PASSWORD`.

## Configuration Reference

| Variable               | Default                                                | Purpose                                       |
|------------------------|--------------------------------------------------------|-----------------------------------------------|
| `SESSION_SECRET`       | *(dev key)*                                            | Flask session signing key.                    |
| `ADMIN_USERNAME`       | `admin`                                                | Admin login username.                         |
| `ADMIN_PASSWORD`       | `admin123`                                             | Admin login password.                         |
| `INSTITUTION_NAME`     | `Visvesvaraya Technological University`                | University name on the PDF.                   |
| `INSTITUTION_TAGLINE`  | `Jnana Sangama, Belagavi - 590018, Karnataka`          | Address line on the PDF.                      |
| `INSTITUTION_OFFICE`   | `Office of the Registrar (Evaluation)`                 | Issuing-office line on the PDF.               |
| `PORT`                 | `5000`                                                 | Port Flask listens on.                        |
