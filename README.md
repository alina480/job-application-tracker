# Job Application Tracker

A full-stack web application for tracking a job search: companies, job postings, applications, and networking contacts — plus a **Job Match** feature that ranks jobs by how well your skills match their requirements.

Built for COP4751 (Advanced Database) with **MySQL**, **Python / Flask**, and **HTML / CSS**.

## Features

- **Dashboard** — totals for every table, response rate, applications-by-status chart, upcoming interviews, recent applications
- **Full CRUD on all four tables** — Companies, Jobs, Applications, Contacts (list, detail view, add, edit, delete with confirmation)
- **Server-side validation** — required fields, max lengths, valid URLs/emails/phones/dates, salary min ≤ max, duplicate company names, valid foreign keys
- **JSON columns**
  - `jobs.requirements` — a JSON array of required skills, e.g. `["Python", "SQL", "Flask"]`
  - `applications.interview_data` — a JSON object with interview date, type, interviewer, round, and notes
- **Job Match** — enter your skills; jobs are ranked by match percentage with matched and missing skills shown
- **Status filter** on the Applications page

## Project Structure

```
job-application-tracker/
├── app.py              # Flask routes, validation, Job Match algorithm
├── database.py         # MySQL connection + all SQL queries
├── schema.sql          # Creates the database, 4 tables, and sample data
├── requirements.txt    # Python dependencies
├── templates/          # Jinja2 HTML templates (base, dashboard, list/form/detail per table, job_match)
├── static/style.css    # Stylesheet
├── AI_USAGE.md         # GenAI documentation
└── README.md
```

## Database Design

| Table | Key columns | Relationships |
|---|---|---|
| `companies` | `company_id` PK, `company_name` (unique, required) | parent of jobs and contacts |
| `jobs` | `job_id` PK, `job_type` ENUM, `requirements` JSON | `company_id` FK → companies (ON DELETE CASCADE) |
| `applications` | `application_id` PK, `status` ENUM, `interview_data` JSON | `job_id` FK → jobs (ON DELETE CASCADE) |
| `contacts` | `contact_id` PK, `contact_name` (required) | `company_id` FK → companies (ON DELETE SET NULL) |

Deleting a company removes its jobs and their applications, but keeps its contacts (their company is cleared), because a contact is still useful after the company is removed.

## Setup Instructions

### 1. Prerequisites
- Python 3.9 or newer
- MySQL Server 8.0 or newer, running locally

### 2. Clone the repository
```bash
git clone https://github.com/alina480/job-application-tracker.git
cd job-application-tracker
```

### 3. Install Python dependencies
```bash
pip install -r requirements.txt
```
(Optional: create a virtual environment first with `python -m venv venv` and activate it.)

### 4. Create the database
> ⚠️ `schema.sql` drops and recreates the four project tables inside the `job_tracker` database.

```bash
mysql -u root -p < schema.sql
```
Or open `schema.sql` in MySQL Workbench and run the whole script (lightning-bolt icon).

### 5. Set your MySQL password
The app reads its connection settings from environment variables. Only `DB_PASSWORD` is normally needed.

| Variable | Default |
|---|---|
| `DB_HOST` | `localhost` |
| `DB_PORT` | `3306` |
| `DB_USER` | `root` |
| `DB_PASSWORD` | *(empty)* |
| `DB_NAME` | `job_tracker` |

**macOS / Linux**
```bash
export DB_PASSWORD="your_mysql_password"
```
**Windows PowerShell**
```powershell
$env:DB_PASSWORD="your_mysql_password"
```
**Windows Command Prompt**
```cmd
set DB_PASSWORD=your_mysql_password
```

### 6. Run the app
```bash
python app.py
```
Open **http://127.0.0.1:5000** in your browser.

### Troubleshooting
- **"Access denied for user 'root'"** — `DB_PASSWORD` is not set in the same terminal you ran `python app.py` from.
- **"Unknown database 'job_tracker'"** — run `schema.sql` first (step 4).
- **"Can't connect to MySQL server"** — start the MySQL service.

## Using Job Match

1. Open **Job Match** in the navigation bar.
2. Type your skills separated by commas, e.g. `Python, SQL, Flask`.
3. Jobs are ranked by **match % = matched required skills ÷ total required skills × 100**. Matching ignores upper/lower case. Each result lists the skills you have and the ones you're missing.

With the sample data, `Python, SQL, Flask` gives: Software Developer at TechCorp — 100% (3/3), Data Analyst at DataCo — 67% (2/3, missing Tableau), and so on.

## Demo Video

See `demo.mp4` in this repository for a recorded walkthrough of the client, server, and database.

## AI Usage

See [AI_USAGE.md](AI_USAGE.md).
