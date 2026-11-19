-- =============================================================
-- Job Application Tracker - Database Creation Script
-- COP4751 Course Project
--
-- Run with:  mysql -u root -p < schema.sql
--
-- WARNING: this drops and recreates the four project tables
-- inside the job_tracker database (any rows in them are lost).
-- =============================================================

CREATE DATABASE IF NOT EXISTS job_tracker;
USE job_tracker;

-- Drop in reverse dependency order (children before parents)
DROP TABLE IF EXISTS applications;
DROP TABLE IF EXISTS contacts;
DROP TABLE IF EXISTS jobs;
DROP TABLE IF EXISTS companies;

-- -------------------------------------------------------------
-- companies: organizations I am applying to
-- -------------------------------------------------------------
CREATE TABLE companies (
    company_id   INT PRIMARY KEY AUTO_INCREMENT,
    company_name VARCHAR(100) NOT NULL,
    industry     VARCHAR(50),
    website      VARCHAR(200),
    city         VARCHAR(50),
    state        VARCHAR(50),
    notes        TEXT,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_company_name UNIQUE (company_name)
);

-- -------------------------------------------------------------
-- jobs: specific postings at a company
-- requirements is a JSON array of skill strings,
--   e.g. ["Python", "SQL", "Flask"]
-- Deleting a company deletes its jobs (CASCADE).
-- -------------------------------------------------------------
CREATE TABLE jobs (
    job_id       INT PRIMARY KEY AUTO_INCREMENT,
    company_id   INT NOT NULL,
    job_title    VARCHAR(100) NOT NULL,
    job_type     ENUM('Full-time','Part-time','Contract','Internship'),
    salary_min   INT,
    salary_max   INT,
    job_url      VARCHAR(300),
    date_posted  DATE,
    requirements JSON,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_jobs_company
        FOREIGN KEY (company_id) REFERENCES companies(company_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT chk_salary_range
        CHECK (salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max)
);

-- -------------------------------------------------------------
-- applications: my submission for a job
-- interview_data is a JSON object, e.g.
--   {"interview_date": "2026-11-20", "interview_type": "Phone",
--    "interviewer": "Jane Doe", "round": 1, "notes": "..."}
-- Deleting a job deletes its applications (CASCADE).
-- -------------------------------------------------------------
CREATE TABLE applications (
    application_id    INT PRIMARY KEY AUTO_INCREMENT,
    job_id            INT NOT NULL,
    application_date  DATE NOT NULL,
    status            ENUM('Applied','Screening','Interview','Offer','Rejected','Withdrawn')
                      NOT NULL DEFAULT 'Applied',
    resume_version    VARCHAR(50),
    cover_letter_sent BOOLEAN DEFAULT FALSE,
    interview_data    JSON,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_applications_job
        FOREIGN KEY (job_id) REFERENCES jobs(job_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

-- -------------------------------------------------------------
-- contacts: people I know at a company (recruiters, referrals)
-- Deleting a company keeps the contact but clears the link (SET NULL).
-- -------------------------------------------------------------
CREATE TABLE contacts (
    contact_id   INT PRIMARY KEY AUTO_INCREMENT,
    company_id   INT,
    contact_name VARCHAR(100) NOT NULL,
    title        VARCHAR(100),
    email        VARCHAR(100),
    phone        VARCHAR(20),
    linkedin_url VARCHAR(200),
    notes        TEXT,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_contacts_company
        FOREIGN KEY (company_id) REFERENCES companies(company_id)
        ON DELETE SET NULL ON UPDATE CASCADE
);

-- Indexes on foreign keys / common filters
CREATE INDEX idx_jobs_company        ON jobs(company_id);
CREATE INDEX idx_applications_job    ON applications(job_id);
CREATE INDEX idx_applications_status ON applications(status);
CREATE INDEX idx_contacts_company    ON contacts(company_id);

-- =============================================================
-- Sample data
-- =============================================================
INSERT INTO companies (company_name, industry, website, city, state, notes) VALUES
('TechCorp',          'Software',       'https://www.techcorp.example',   'Miami',         'FL', 'Mid-size SaaS company, strong mentorship program.'),
('DataCo',            'Analytics',      'https://www.dataco.example',     'Fort Lauderdale','FL', 'Hybrid schedule, heavy on BI tools.'),
('LexGuard Legal Tech','Legal Technology','https://www.lexguard.example', 'Coral Gables',  'FL', 'Builds privacy-compliance software for law firms.'),
('HealthBridge AI',   'Healthcare',     'https://www.healthbridge.example','Doral',        'FL', 'AI tools for clinics; HIPAA-focused.'),
('CloudNine Systems', 'Cloud Services', 'https://www.cloudnine.example',  'New York',      'NY', 'Large company, long hiring process.');

INSERT INTO jobs (company_id, job_title, job_type, salary_min, salary_max, job_url, date_posted, requirements) VALUES
(1, 'Software Developer',        'Full-time',  70000, 90000, 'https://www.techcorp.example/careers/101',   '2026-10-01', JSON_ARRAY('Python', 'SQL', 'Flask')),
(2, 'Data Analyst',              'Full-time',  60000, 75000, 'https://www.dataco.example/jobs/22',         '2026-10-05', JSON_ARRAY('SQL', 'Python', 'Tableau')),
(3, 'Privacy Compliance Analyst','Internship', 20000, 30000, 'https://www.lexguard.example/careers/intern', '2026-10-12', JSON_ARRAY('HIPAA', 'Risk Assessment', 'SQL', 'Technical Writing')),
(4, 'IT Support Specialist',     'Part-time',  30000, 40000, 'https://www.healthbridge.example/jobs/7',    '2026-10-20', JSON_ARRAY('Networking', 'Active Directory', 'Troubleshooting', 'HIPAA')),
(5, 'Cloud Engineer Intern',     'Internship', 25000, 35000, 'https://www.cloudnine.example/jobs/intern',  '2026-11-01', JSON_ARRAY('AWS', 'Linux', 'Python', 'Networking')),
(1, 'QA Tester',                 'Contract',   45000, 55000, 'https://www.techcorp.example/careers/115',   '2026-11-03', JSON_ARRAY('Testing', 'SQL', 'JIRA'));

INSERT INTO applications (job_id, application_date, status, resume_version, cover_letter_sent, interview_data) VALUES
(1, '2026-10-03', 'Interview', 'v3-software', TRUE,
    JSON_OBJECT('interview_date', '2026-11-20', 'interview_type', 'Technical', 'interviewer', 'Maria Lopez', 'round', 2, 'notes', 'Prepare SQL joins and Flask routing questions.')),
(2, '2026-10-08', 'Screening', 'v3-data', FALSE, NULL),
(3, '2026-10-14', 'Offer', 'v4-legal-tech', TRUE,
    JSON_OBJECT('interview_date', '2026-10-28', 'interview_type', 'Video', 'interviewer', 'David Chen', 'round', 1, 'notes', 'Asked about HIPAA and AI privacy risks.')),
(4, '2026-10-22', 'Rejected', 'v3-support', FALSE, NULL),
(5, '2026-11-04', 'Applied', 'v4-cloud', TRUE, NULL);

INSERT INTO contacts (company_id, contact_name, title, email, phone, linkedin_url, notes) VALUES
(1, 'Maria Lopez',  'Engineering Manager', 'maria.lopez@techcorp.example', '305-555-0101', 'https://www.linkedin.com/in/example-maria', 'Met at FIU career fair.'),
(3, 'David Chen',   'Talent Acquisition',  'dchen@lexguard.example',       '786-555-0142', 'https://www.linkedin.com/in/example-david', 'Very responsive over email.'),
(4, 'Priya Patel',  'IT Director',         'ppatel@healthbridge.example',  '305-555-0177', NULL, 'Referral from INIT event.'),
(5, 'Sam Rivera',   'Recruiter',           'srivera@cloudnine.example',    '212-555-0199', 'https://www.linkedin.com/in/example-sam', NULL);
