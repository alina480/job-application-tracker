"""
app.py - Flask web application for the Job Application Tracker.

Routes follow the same pattern for every table:
    /<table>                 list (Read)
    /<table>/<id>            detail view (Read)
    /<table>/add             form to create (Create)
    /<table>/<id>/edit       form to update (Update)
    /<table>/<id>/delete     POST only, after a confirmation prompt (Delete)
"""

import os
import re
from datetime import date

import mysql.connector
from flask import Flask, abort, flash, redirect, render_template, request, url_for

import database as db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

JOB_TYPES = ["Full-time", "Part-time", "Contract", "Internship"]
STATUSES = ["Applied", "Screening", "Interview", "Offer", "Rejected", "Withdrawn"]
INTERVIEW_TYPES = ["Phone", "Video", "On-site", "Technical", "Behavioral", "Panel"]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[0-9+()\-.\s]{7,20}$")


@app.template_global()
def v(record, key):
    """Template helper: value of a form/DB field, or '' instead of 'None'."""
    value = record.get(key) if record else None
    return "" if value is None else value


# ------------------------------------------------------------------
# Validation helpers
# ------------------------------------------------------------------
def clean(form, field):
    """Return a stripped form value, or None if it was left blank."""
    value = form.get(field, "").strip()
    return value or None


def check_length(errors, label, value, max_len):
    if value and len(value) > max_len:
        errors.append(f"{label} must be {max_len} characters or fewer.")


def check_url(errors, label, value):
    if value and not value.lower().startswith(("http://", "https://")):
        errors.append(f"{label} must start with http:// or https://")


def check_date(errors, label, value, required=False):
    if not value:
        if required:
            errors.append(f"{label} is required.")
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append(f"{label} must be a valid date (YYYY-MM-DD).")
        return None


def check_int(errors, label, value):
    if value is None:
        return None
    try:
        number = int(value)
    except ValueError:
        errors.append(f"{label} must be a whole number.")
        return None
    if number < 0:
        errors.append(f"{label} cannot be negative.")
    return number


def parse_skills(text):
    """Turn 'Python, SQL,  flask' into ['Python', 'SQL', 'flask'] (no duplicates)."""
    skills, seen = [], set()
    for part in (text or "").split(","):
        skill = part.strip()
        if skill and skill.lower() not in seen:
            seen.add(skill.lower())
            skills.append(skill)
    return skills


def validate_company(form, company_id=None):
    errors = []
    data = {f: clean(form, f) for f in
            ("company_name", "industry", "website", "city", "state", "notes")}
    if not data["company_name"]:
        errors.append("Company name is required.")
    elif db.company_name_exists(data["company_name"], exclude_id=company_id):
        errors.append(f"A company named '{data['company_name']}' already exists.")
    check_length(errors, "Company name", data["company_name"], 100)
    check_length(errors, "Industry", data["industry"], 50)
    check_length(errors, "Website", data["website"], 200)
    check_length(errors, "City", data["city"], 50)
    check_length(errors, "State", data["state"], 50)
    check_url(errors, "Website", data["website"])
    return data, errors


def validate_job(form):
    errors = []
    data = {f: clean(form, f) for f in
            ("company_id", "job_title", "job_type", "job_url", "date_posted")}
    if not data["company_id"] or not db.get_company(data["company_id"]):
        errors.append("Please choose a valid company.")
    if not data["job_title"]:
        errors.append("Job title is required.")
    check_length(errors, "Job title", data["job_title"], 100)
    if data["job_type"] and data["job_type"] not in JOB_TYPES:
        errors.append("Please choose a valid job type.")
    data["salary_min"] = check_int(errors, "Minimum salary", clean(form, "salary_min"))
    data["salary_max"] = check_int(errors, "Maximum salary", clean(form, "salary_max"))
    if (data["salary_min"] is not None and data["salary_max"] is not None
            and data["salary_min"] > data["salary_max"]):
        errors.append("Minimum salary cannot be greater than maximum salary.")
    check_length(errors, "Job URL", data["job_url"], 300)
    check_url(errors, "Job URL", data["job_url"])
    check_date(errors, "Date posted", data["date_posted"])
    data["requirements"] = parse_skills(form.get("requirements"))
    return data, errors


def validate_application(form):
    errors = []
    data = {f: clean(form, f) for f in
            ("job_id", "application_date", "status", "resume_version")}
    if not data["job_id"] or not db.get_job(data["job_id"]):
        errors.append("Please choose a valid job.")
    check_date(errors, "Application date", data["application_date"], required=True)
    if data["status"] not in STATUSES:
        errors.append("Please choose a valid status.")
    check_length(errors, "Resume version", data["resume_version"], 50)
    data["cover_letter_sent"] = form.get("cover_letter_sent") == "on"

    # Build the interview_data JSON object from the optional interview fields
    interview = {
        "interview_date": clean(form, "interview_date"),
        "interview_type": clean(form, "interview_type"),
        "interviewer": clean(form, "interviewer"),
        "round": check_int(errors, "Interview round", clean(form, "interview_round")),
        "notes": clean(form, "interview_notes"),
    }
    check_date(errors, "Interview date", interview["interview_date"])
    if interview["interview_type"] and interview["interview_type"] not in INTERVIEW_TYPES:
        errors.append("Please choose a valid interview type.")
    # Only store the keys that were actually filled in
    data["interview_data"] = {k: v for k, v in interview.items() if v not in (None, "")}
    return data, errors


def validate_contact(form):
    errors = []
    data = {f: clean(form, f) for f in
            ("company_id", "contact_name", "title", "email", "phone", "linkedin_url", "notes")}
    if data["company_id"] and not db.get_company(data["company_id"]):
        errors.append("Please choose a valid company.")
    if not data["contact_name"]:
        errors.append("Contact name is required.")
    check_length(errors, "Contact name", data["contact_name"], 100)
    check_length(errors, "Title", data["title"], 100)
    check_length(errors, "Email", data["email"], 100)
    check_length(errors, "LinkedIn URL", data["linkedin_url"], 200)
    if data["email"] and not EMAIL_RE.match(data["email"]):
        errors.append("Please enter a valid email address.")
    if data["phone"] and not PHONE_RE.match(data["phone"]):
        errors.append("Phone may contain only digits, spaces, and + ( ) - .")
    check_url(errors, "LinkedIn URL", data["linkedin_url"])
    return data, errors


# ------------------------------------------------------------------
# Job Match algorithm
# ------------------------------------------------------------------
def calculate_match(user_skills, required_skills):
    """
    Compare the user's skills to a job's required skills (case-insensitive).
    Returns matched skills, missing skills, and the match percentage
    = matched / required * 100, rounded to a whole number.
    """
    user_set = {s.lower() for s in user_skills}
    matched = [s for s in required_skills if s.lower() in user_set]
    missing = [s for s in required_skills if s.lower() not in user_set]
    percent = round(len(matched) / len(required_skills) * 100) if required_skills else 0
    return {"matched": matched, "missing": missing, "percent": percent}


def rank_jobs(user_skills, jobs):
    """Return jobs with requirements, sorted best match first."""
    results = []
    for job in jobs:
        if not job["requirements"]:
            continue  # nothing to match against
        match = calculate_match(user_skills, job["requirements"])
        results.append({"job": job, **match})
    # Highest % first; ties broken by number of matched skills, then title
    results.sort(key=lambda r: (-r["percent"], -len(r["matched"]), r["job"]["job_title"]))
    return results


# ------------------------------------------------------------------
# Error handling
# ------------------------------------------------------------------
@app.errorhandler(mysql.connector.Error)
def database_error(err):
    return render_template("error.html", error=err), 500


@app.errorhandler(404)
def not_found(err):
    return render_template("error.html", error="That record was not found."), 404


def get_or_404(record):
    if record is None:
        abort(404)
    return record


# ------------------------------------------------------------------
# Dashboard
# ------------------------------------------------------------------
@app.route("/")
def dashboard():
    return render_template("dashboard.html", stats=db.get_dashboard_stats())


# ------------------------------------------------------------------
# Companies
# ------------------------------------------------------------------
@app.route("/companies")
def companies():
    return render_template("companies.html", companies=db.get_companies())


@app.route("/companies/<int:company_id>")
def company_detail(company_id):
    company = get_or_404(db.get_company(company_id))
    return render_template("company_detail.html", company=company,
                           jobs=db.get_jobs(company_id=company_id),
                           contacts=db.get_contacts(company_id=company_id))


@app.route("/companies/add", methods=["GET", "POST"])
def add_company():
    if request.method == "POST":
        data, errors = validate_company(request.form)
        if not errors:
            db.add_company(data)
            flash(f"Company '{data['company_name']}' added.", "success")
            return redirect(url_for("companies"))
        for e in errors:
            flash(e, "error")
        return render_template("company_form.html", company=request.form, action="Add")
    return render_template("company_form.html", company={}, action="Add")


@app.route("/companies/<int:company_id>/edit", methods=["GET", "POST"])
def edit_company(company_id):
    company = get_or_404(db.get_company(company_id))
    if request.method == "POST":
        data, errors = validate_company(request.form, company_id=company_id)
        if not errors:
            db.update_company(company_id, data)
            flash(f"Company '{data['company_name']}' updated.", "success")
            return redirect(url_for("company_detail", company_id=company_id))
        for e in errors:
            flash(e, "error")
        return render_template("company_form.html", company=request.form, action="Edit")
    return render_template("company_form.html", company=company, action="Edit")


@app.route("/companies/<int:company_id>/delete", methods=["POST"])
def delete_company(company_id):
    company = get_or_404(db.get_company(company_id))
    db.delete_company(company_id)
    flash(f"Company '{company['company_name']}' and its jobs/applications were deleted.", "success")
    return redirect(url_for("companies"))


# ------------------------------------------------------------------
# Jobs
# ------------------------------------------------------------------
@app.route("/jobs")
def jobs():
    return render_template("jobs.html", jobs=db.get_jobs())


@app.route("/jobs/<int:job_id>")
def job_detail(job_id):
    job = get_or_404(db.get_job(job_id))
    return render_template("job_detail.html", job=job,
                           applications=db.get_applications(job_id=job_id))


def job_form(job, action):
    return render_template("job_form.html", job=job, action=action,
                           companies=db.get_companies(), job_types=JOB_TYPES)


@app.route("/jobs/add", methods=["GET", "POST"])
def add_job():
    if request.method == "POST":
        data, errors = validate_job(request.form)
        if not errors:
            db.add_job(data)
            flash(f"Job '{data['job_title']}' added.", "success")
            return redirect(url_for("jobs"))
        for e in errors:
            flash(e, "error")
        return job_form(request.form, "Add")
    # Allow pre-selecting a company: /jobs/add?company_id=3
    return job_form({"company_id": request.args.get("company_id", "")}, "Add")


@app.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
def edit_job(job_id):
    job = get_or_404(db.get_job(job_id))
    if request.method == "POST":
        data, errors = validate_job(request.form)
        if not errors:
            db.update_job(job_id, data)
            flash(f"Job '{data['job_title']}' updated.", "success")
            return redirect(url_for("job_detail", job_id=job_id))
        for e in errors:
            flash(e, "error")
        return job_form(request.form, "Edit")
    job = dict(job, requirements=", ".join(job["requirements"]))
    return job_form(job, "Edit")


@app.route("/jobs/<int:job_id>/delete", methods=["POST"])
def delete_job(job_id):
    job = get_or_404(db.get_job(job_id))
    db.delete_job(job_id)
    flash(f"Job '{job['job_title']}' and its applications were deleted.", "success")
    return redirect(url_for("jobs"))


# ------------------------------------------------------------------
# Applications
# ------------------------------------------------------------------
@app.route("/applications")
def applications():
    status = request.args.get("status") or None
    if status and status not in STATUSES:
        status = None
    return render_template("applications.html", statuses=STATUSES, current_status=status,
                           applications=db.get_applications(status=status))


@app.route("/applications/<int:application_id>")
def application_detail(application_id):
    application = get_or_404(db.get_application(application_id))
    return render_template("application_detail.html", app_row=application)


def application_form(app_row, action):
    return render_template("application_form.html", app_row=app_row, action=action,
                           jobs=db.get_jobs(), statuses=STATUSES,
                           interview_types=INTERVIEW_TYPES)


def flatten_application(app_row):
    """Copy interview_data JSON keys into flat form-field names for the edit form."""
    interview = app_row.get("interview_data") or {}
    flat = dict(app_row)
    flat.update({
        "interview_date": interview.get("interview_date", ""),
        "interview_type": interview.get("interview_type", ""),
        "interviewer": interview.get("interviewer", ""),
        "interview_round": interview.get("round", ""),
        "interview_notes": interview.get("notes", ""),
        "cover_letter_sent": "on" if app_row.get("cover_letter_sent") else "",
    })
    return flat


@app.route("/applications/add", methods=["GET", "POST"])
def add_application():
    if request.method == "POST":
        data, errors = validate_application(request.form)
        if not errors:
            db.add_application(data)
            flash("Application added.", "success")
            return redirect(url_for("applications"))
        for e in errors:
            flash(e, "error")
        return application_form(request.form, "Add")
    defaults = {"job_id": request.args.get("job_id", ""),
                "application_date": date.today().isoformat(), "status": "Applied"}
    return application_form(defaults, "Add")


@app.route("/applications/<int:application_id>/edit", methods=["GET", "POST"])
def edit_application(application_id):
    application = get_or_404(db.get_application(application_id))
    if request.method == "POST":
        data, errors = validate_application(request.form)
        if not errors:
            db.update_application(application_id, data)
            flash("Application updated.", "success")
            return redirect(url_for("application_detail", application_id=application_id))
        for e in errors:
            flash(e, "error")
        return application_form(request.form, "Edit")
    return application_form(flatten_application(application), "Edit")


@app.route("/applications/<int:application_id>/delete", methods=["POST"])
def delete_application(application_id):
    get_or_404(db.get_application(application_id))
    db.delete_application(application_id)
    flash("Application deleted.", "success")
    return redirect(url_for("applications"))


# ------------------------------------------------------------------
# Contacts
# ------------------------------------------------------------------
@app.route("/contacts")
def contacts():
    return render_template("contacts.html", contacts=db.get_contacts())


@app.route("/contacts/<int:contact_id>")
def contact_detail(contact_id):
    return render_template("contact_detail.html",
                           contact=get_or_404(db.get_contact(contact_id)))


def contact_form(contact, action):
    return render_template("contact_form.html", contact=contact, action=action,
                           companies=db.get_companies())


@app.route("/contacts/add", methods=["GET", "POST"])
def add_contact():
    if request.method == "POST":
        data, errors = validate_contact(request.form)
        if not errors:
            db.add_contact(data)
            flash(f"Contact '{data['contact_name']}' added.", "success")
            return redirect(url_for("contacts"))
        for e in errors:
            flash(e, "error")
        return contact_form(request.form, "Add")
    return contact_form({"company_id": request.args.get("company_id", "")}, "Add")


@app.route("/contacts/<int:contact_id>/edit", methods=["GET", "POST"])
def edit_contact(contact_id):
    contact = get_or_404(db.get_contact(contact_id))
    if request.method == "POST":
        data, errors = validate_contact(request.form)
        if not errors:
            db.update_contact(contact_id, data)
            flash(f"Contact '{data['contact_name']}' updated.", "success")
            return redirect(url_for("contact_detail", contact_id=contact_id))
        for e in errors:
            flash(e, "error")
        return contact_form(request.form, "Edit")
    return contact_form(contact, "Edit")


@app.route("/contacts/<int:contact_id>/delete", methods=["POST"])
def delete_contact(contact_id):
    contact = get_or_404(db.get_contact(contact_id))
    db.delete_contact(contact_id)
    flash(f"Contact '{contact['contact_name']}' deleted.", "success")
    return redirect(url_for("contacts"))


# ------------------------------------------------------------------
# Job Match
# ------------------------------------------------------------------
@app.route("/job-match")
def job_match():
    skills_text = request.args.get("skills", "")
    user_skills = parse_skills(skills_text)
    results = rank_jobs(user_skills, db.get_jobs()) if user_skills else None
    return render_template("job_match.html", skills_text=skills_text,
                           user_skills=user_skills, results=results)


if __name__ == "__main__":
    app.run(debug=True)
