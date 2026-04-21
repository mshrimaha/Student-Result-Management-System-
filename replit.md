# Student Result Management System

## Overview

A Python Flask web application for managing student academic records. Records are persisted in Replit Database. Includes a public results-lookup page and a password-protected admin dashboard for CRUD on student records.

## Stack

- **Language**: Python 3.11
- **Framework**: Flask
- **Storage**: Replit Database (`replit` package)
- **Server**: Flask dev server on port 5000

## Project Structure

```
main.py              # Flask app, routes, and storage helpers
templates/           # Jinja2 HTML templates
  base.html
  index.html
  results.html
  login.html
  admin.html
  edit.html
static/style.css     # Styling
```

## Features

- Public homepage with overview
- Public "View Results" page — search by Student ID
- Admin login (defaults: `admin` / `admin123`)
- Admin dashboard listing all students
- Add / edit / delete student records (Name, ID, marks for 5 subjects)
- Auto-computed total, average, grade, and pass/fail status

## Configuration

Environment variables:

- `SESSION_SECRET` — Flask session secret (already set)
- `ADMIN_USERNAME` — admin login username (default `admin`)
- `ADMIN_PASSWORD` — admin login password (default `admin123`)
- `PORT` — port to listen on (default `5000`)

## Running

The workflow `Start application` runs `python main.py` on port 5000.
