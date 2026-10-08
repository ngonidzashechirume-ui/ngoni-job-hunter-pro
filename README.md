# Ngoni Job Hunter Pro

A local Streamlit job-search assistant designed around a Mauritius IT/Cybersecurity search.

## Features
- Match scoring for IT Support, Helpdesk, IT Technician, Network, Infrastructure, Systems and Cybersecurity roles.
- Strong penalty for French requirements.
- Penalty for excessive experience requirements.
- Junior/graduate bonus.
- CSV bulk import.
- Profile storage.
- Application email and cover-letter drafts.
- Recruiter/contact database.
- Status pipeline: New → Ready → Applied → Follow-up → Interview → Offer/Rejected.
- Follow-up date set 7 days after an application is marked Applied.
- Dashboard and basic analytics.

## Run
Windows:
1. Install Python 3.10+.
2. Open Command Prompt in this folder.
3. `pip install -r requirements.txt`
4. `streamlit run app.py`

## Job discovery
Use CSV exports or permitted/public job feeds/APIs. Do not bypass CAPTCHAs, authentication, LinkedIn restrictions, robots/terms, or anti-bot systems.

## Email
The current version prepares emails and requires you to approve/mark them as applied. The next integration can use Gmail/Microsoft OAuth so the software can send approved messages without storing your password.
