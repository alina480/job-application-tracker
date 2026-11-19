"""
database.py - MySQL connection and data-access functions for the
Job Application Tracker.

All SQL lives in this file so app.py only deals with web requests.
Every query uses %s placeholders (parameterized queries) to prevent
SQL injection.
"""

import json
import os

import mysql.connector

# Connection settings. Override any of these with environment variables
# (see README.md) instead of editing the code.
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "3306")),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "job_tracker"),
}


# ------------------------------------------------------------------
# Generic helpers
# ------------------------------------------------------------------
def get_db():
    """Open a new connection to the job_tracker database."""
    return mysql.connector.connect(**DB_CONFIG)


def query_all(sql, params=()):
    """Run a SELECT and return every row as a list of dicts."""
    conn = get_db()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        conn.close()


def query_one(sql, params=()):
    """Run a SELECT and return the first row as a dict (or None)."""
    rows = query_all(sql, params)
    return rows[0] if rows else None


def execute(sql, params=()):
    """Run an INSERT/UPDATE/DELETE, commit, and return the new row id."""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def parse_json(value, default):
    """MySQL returns JSON columns as strings; convert them to Python objects."""
    if value is None or value == "":
        return default
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


# ------------------------------------------------------------------
# Companies
# ------------------------------------------------------------------
def get_companies():
    return query_all(
        """SELECT c.*,
                  (SELECT COUNT(*) FROM jobs j WHERE j.company_id = c.company_id) AS job_count,
                  (SELECT COUNT(*) FROM contacts ct WHERE ct.company_id = c.company_id) AS contact_count
           FROM companies c
           ORDER BY c.company_name"""
    )


def get_company(company_id):
    return query_one("SELECT * FROM companies WHERE company_id = %s", (company_id,))


def company_name_exists(name, exclude_id=None):
    sql = "SELECT company_id FROM companies WHERE LOWER(company_name) = LOWER(%s)"
    params = [name]
    if exclude_id:
        sql += " AND company_id <> %s"
        params.append(exclude_id)
    return query_one(sql, tuple(params)) is not None


def add_company(data):
    return execute(
        """INSERT INTO companies (company_name, industry, website, city, state, notes)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (data["company_name"], data["industry"], data["website"],
         data["city"], data["state"], data["notes"]),
    )


def update_company(company_id, data):
    execute(
        """UPDATE companies
           SET company_name = %s, industry = %s, website = %s,
               city = %s, state = %s, notes = %s
           WHERE company_id = %s""",
        (data["company_name"], data["industry"], data["website"],
         data["city"], data["state"], data["notes"], company_id),
    )


def delete_company(company_id):
    execute("DELETE FROM companies WHERE company_id = %s", (company_id,))


# ------------------------------------------------------------------
# Jobs
# ------------------------------------------------------------------
def _jobs_with_skills(rows):
    for row in rows:
        row["requirements"] = parse_json(row.get("requirements"), [])
    return rows


def get_jobs(company_id=None):
    sql = """SELECT j.*, c.company_name,
                    (SELECT COUNT(*) FROM applications a WHERE a.job_id = j.job_id) AS application_count
             FROM jobs j
             JOIN companies c ON j.company_id = c.company_id"""
    params = ()
    if company_id:
        sql += " WHERE j.company_id = %s"
        params = (company_id,)
    sql += " ORDER BY j.date_posted DESC, j.job_id DESC"
    return _jobs_with_skills(query_all(sql, params))


def get_job(job_id):
    row = query_one(
        """SELECT j.*, c.company_name
           FROM jobs j JOIN companies c ON j.company_id = c.company_id
           WHERE j.job_id = %s""",
        (job_id,),
    )
    return _jobs_with_skills([row])[0] if row else None


def add_job(data):
    return execute(
        """INSERT INTO jobs (company_id, job_title, job_type, salary_min, salary_max,
                             job_url, date_posted, requirements)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (data["company_id"], data["job_title"], data["job_type"], data["salary_min"],
         data["salary_max"], data["job_url"], data["date_posted"],
         json.dumps(data["requirements"])),
    )


def update_job(job_id, data):
    execute(
        """UPDATE jobs
           SET company_id = %s, job_title = %s, job_type = %s, salary_min = %s,
               salary_max = %s, job_url = %s, date_posted = %s, requirements = %s
           WHERE job_id = %s""",
        (data["company_id"], data["job_title"], data["job_type"], data["salary_min"],
         data["salary_max"], data["job_url"], data["date_posted"],
         json.dumps(data["requirements"]), job_id),
    )


def delete_job(job_id):
    execute("DELETE FROM jobs WHERE job_id = %s", (job_id,))


# ------------------------------------------------------------------
# Applications
# ------------------------------------------------------------------
def _apps_with_interview(rows):
    for row in rows:
        row["interview_data"] = parse_json(row.get("interview_data"), {})
    return rows


APPLICATION_SELECT = """SELECT a.*, j.job_title, c.company_name, c.company_id
                        FROM applications a
                        JOIN jobs j ON a.job_id = j.job_id
                        JOIN companies c ON j.company_id = c.company_id"""


def get_applications(status=None, job_id=None):
    sql = APPLICATION_SELECT
    conditions, params = [], []
    if status:
        conditions.append("a.status = %s")
        params.append(status)
    if job_id:
        conditions.append("a.job_id = %s")
        params.append(job_id)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY a.application_date DESC, a.application_id DESC"
    return _apps_with_interview(query_all(sql, tuple(params)))


def get_application(application_id):
    row = query_one(APPLICATION_SELECT + " WHERE a.application_id = %s", (application_id,))
    return _apps_with_interview([row])[0] if row else None


def add_application(data):
    return execute(
        """INSERT INTO applications (job_id, application_date, status, resume_version,
                                     cover_letter_sent, interview_data)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (data["job_id"], data["application_date"], data["status"], data["resume_version"],
         data["cover_letter_sent"],
         json.dumps(data["interview_data"]) if data["interview_data"] else None),
    )


def update_application(application_id, data):
    execute(
        """UPDATE applications
           SET job_id = %s, application_date = %s, status = %s, resume_version = %s,
               cover_letter_sent = %s, interview_data = %s
           WHERE application_id = %s""",
        (data["job_id"], data["application_date"], data["status"], data["resume_version"],
         data["cover_letter_sent"],
         json.dumps(data["interview_data"]) if data["interview_data"] else None,
         application_id),
    )


def delete_application(application_id):
    execute("DELETE FROM applications WHERE application_id = %s", (application_id,))


# ------------------------------------------------------------------
# Contacts
# ------------------------------------------------------------------
CONTACT_SELECT = """SELECT ct.*, c.company_name
                    FROM contacts ct
                    LEFT JOIN companies c ON ct.company_id = c.company_id"""


def get_contacts(company_id=None):
    sql = CONTACT_SELECT
    params = ()
    if company_id:
        sql += " WHERE ct.company_id = %s"
        params = (company_id,)
    sql += " ORDER BY ct.contact_name"
    return query_all(sql, params)


def get_contact(contact_id):
    return query_one(CONTACT_SELECT + " WHERE ct.contact_id = %s", (contact_id,))


def add_contact(data):
    return execute(
        """INSERT INTO contacts (company_id, contact_name, title, email, phone, linkedin_url, notes)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (data["company_id"], data["contact_name"], data["title"], data["email"],
         data["phone"], data["linkedin_url"], data["notes"]),
    )


def update_contact(contact_id, data):
    execute(
        """UPDATE contacts
           SET company_id = %s, contact_name = %s, title = %s, email = %s,
               phone = %s, linkedin_url = %s, notes = %s
           WHERE contact_id = %s""",
        (data["company_id"], data["contact_name"], data["title"], data["email"],
         data["phone"], data["linkedin_url"], data["notes"], contact_id),
    )


def delete_contact(contact_id):
    execute("DELETE FROM contacts WHERE contact_id = %s", (contact_id,))


# ------------------------------------------------------------------
# Dashboard statistics
# ------------------------------------------------------------------
def get_dashboard_stats():
    counts = query_one(
        """SELECT (SELECT COUNT(*) FROM companies)    AS companies,
                  (SELECT COUNT(*) FROM jobs)         AS jobs,
                  (SELECT COUNT(*) FROM applications) AS applications,
                  (SELECT COUNT(*) FROM contacts)     AS contacts"""
    )
    by_status = query_all(
        """SELECT status, COUNT(*) AS total
           FROM applications GROUP BY status ORDER BY total DESC"""
    )
    # "Response rate" = applications that moved past 'Applied'
    responded = query_one(
        """SELECT COUNT(*) AS total FROM applications
           WHERE status IN ('Screening','Interview','Offer','Rejected')"""
    )["total"]
    recent = get_applications()[:5]
    upcoming = [
        a for a in get_applications()
        if a["interview_data"].get("interview_date") and a["status"] in ("Screening", "Interview")
    ]
    upcoming.sort(key=lambda a: a["interview_data"]["interview_date"])
    return {
        "counts": counts,
        "by_status": by_status,
        "response_rate": round(responded / counts["applications"] * 100) if counts["applications"] else 0,
        "recent": recent,
        "upcoming": upcoming,
    }
