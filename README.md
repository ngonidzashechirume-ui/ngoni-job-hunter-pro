# Ngoni Job Hunter Pro

A Streamlit job-hunting assistant for Mauritius IT roles.

## What this version does
- Automatically scans supported public MyJob.mu IT listing pages.
- Deduplicates vacancies and scores them against Ngoni's profile.
- Penalises mandatory/French-heavy roles and excessive experience requirements.
- Generates application email and cover-letter drafts.
- Supports a human approval step before email sending.
- Can send an approved application email through SMTP when a public recipient email is available.
- For web applications, opens the official vacancy page and lets the user submit it. It does not bypass CAPTCHA, login, private LinkedIn data, or anti-bot controls.
- Tracks status, follow-up dates, contacts and analytics.
- Keeps CSV/manual import as a fallback.

## Run on Windows
Run `run_windows.bat` or:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud
Push this folder to a GitHub repository and deploy `app.py` from Streamlit Community Cloud.

If using SMTP, store credentials in Streamlit Secrets rather than committing them to Git. Example:

```toml
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = "your-email@example.com"
SMTP_FROM = "your-email@example.com"
```

Enter the SMTP app password in the app at send time, or extend the code to read it from secrets. Never commit passwords to GitHub.
