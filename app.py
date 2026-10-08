import csv, io, re, sqlite3, smtplib, ssl, json
from datetime import datetime, timedelta
from pathlib import Path
from email.message import EmailMessage
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
import streamlit as st

DB = Path(__file__).with_name("job_hunter.db")

ROLE_KEYWORDS = {
    "it support": 15, "helpdesk": 14, "help desk": 14, "it technician": 14,
    "technical support": 13, "systems administrator": 13, "system administrator": 13,
    "network": 12, "infrastructure": 12, "cybersecurity": 12, "information security": 12,
    "security": 8, "windows": 8, "active directory": 10, "microsoft 365": 8, "m365": 8,
    "azure": 7, "entra": 7, "firewall": 7, "cloud": 5, "noc": 8, "soc": 8,
    "service desk": 13, "desktop support": 13, "system engineer": 10, "network engineer": 12,
}
BAD_TERMS = ["french required", "fluent french", "native french", "french mandatory", "bilingual french"]
EXPERIENCE_RE = re.compile(r"(\d+)\s*(?:\+|to|-)?\s*(\d+)?\s*years?", re.I)

SEARCH_QUERIES = [
    "IT Support Mauritius", "IT Technician Mauritius", "Technical Support Mauritius",
    "Network Engineer Mauritius", "Network Administrator Mauritius", "Infrastructure Mauritius",
    "Systems Administrator Mauritius", "Cybersecurity Mauritius", "SOC Analyst Mauritius",
    "Service Desk Mauritius", "Helpdesk Mauritius", "IT Support Officer Mauritius",
]
MYJOB_URLS = [
    "https://myjob.mu/jobs/information-technology",
    "https://myjob.mu/jobs?keyword=It-Technician",
    "https://myjob.mu/jobs?keyword=Technical-Support",
    "https://myjob.mu/jobs?keyword=It-Service-Desk",
    "https://myjob.mu/jobs?keyword=Informatique",
]


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init():
    c = db()
    c.execute("""CREATE TABLE IF NOT EXISTS profile(
      id INTEGER PRIMARY KEY CHECK(id=1), name TEXT, email TEXT, phone TEXT,
      linkedin TEXT, summary TEXT, skills TEXT, experience TEXT, education TEXT,
      preferred_roles TEXT, max_experience INTEGER DEFAULT 2, reject_french INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS jobs(
      id INTEGER PRIMARY KEY AUTOINCREMENT, company TEXT, title TEXT, location TEXT,
      url TEXT UNIQUE, description TEXT, score INTEGER DEFAULT 0, status TEXT DEFAULT 'New',
      contact_name TEXT, contact_email TEXT, notes TEXT, source TEXT,
      created_at TEXT, followup_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS applications(
      id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER, subject TEXT, email_body TEXT,
      cover_letter TEXT, approved INTEGER DEFAULT 0, sent INTEGER DEFAULT 0,
      sent_at TEXT, followup_sent INTEGER DEFAULT 0, followup_at TEXT,
      FOREIGN KEY(job_id) REFERENCES jobs(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS contacts(
      id INTEGER PRIMARY KEY AUTOINCREMENT, company TEXT, name TEXT, role TEXT,
      email TEXT, linkedin TEXT, source TEXT, notes TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS activity(
      id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER, event TEXT, created_at TEXT)""")
    c.execute("INSERT OR IGNORE INTO profile(id,name,max_experience,reject_french) VALUES(1,'Ngonidzaishe Chirume',2,1)")
    c.commit(); c.close()


def get_profile():
    c = db(); r = c.execute("SELECT * FROM profile WHERE id=1").fetchone(); c.close(); return r


def save_profile(v):
    c = db()
    c.execute("""UPDATE profile SET name=?,email=?,phone=?,linkedin=?,summary=?,skills=?,
      experience=?,education=?,preferred_roles=?,max_experience=?,reject_french=? WHERE id=1""",
      (v["name"],v["email"],v["phone"],v["linkedin"],v["summary"],v["skills"],
       v["experience"],v["education"],v["preferred_roles"],v["max_experience"],v["reject_french"]))
    c.commit(); c.close()


def score_job(j,p):
    text=(j.get("title","")+" "+(j.get("description","") or "")).lower()
    score=10
    for k,v in ROLE_KEYWORDS.items():
        if k in text: score += v
    if any(x in text for x in ["junior","trainee","entry level","entry-level","graduate","0-1 year","1 year","fresh graduate"]): score += 12
    if p["reject_french"] and any(x in text for x in BAD_TERMS): score -= 45
    years=[]
    for m in EXPERIENCE_RE.finditer(text):
        try: years.append(int(m.group(1)))
        except Exception: pass
    if years and max(years) > int(p["max_experience"] or 2): score -= 25
    if "mauritius" in text or "plaines wilhems" in text or "moka" in text or "port louis" in text: score += 4
    return max(0,min(100,score))


def add_job(v):
    p=get_profile(); score=score_job(v,p)
    c=db()
    try:
        c.execute("""INSERT INTO jobs(company,title,location,url,description,score,status,
          contact_name,contact_email,notes,source,created_at,followup_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (v["company"],v["title"],v["location"],v["url"],v["description"],score,"New",
           v.get("contact_name",""),v.get("contact_email",""),v.get("notes",""),v.get("source",""),
           datetime.now().isoformat(timespec="minutes"),None))
        c.commit(); inserted=True
    except sqlite3.IntegrityError:
        inserted=False
    c.close(); return inserted


def get_jobs():
    c=db(); r=c.execute("SELECT * FROM jobs ORDER BY score DESC, id DESC").fetchall(); c.close(); return r


def update_status(jid,status):
    c=db(); c.execute("UPDATE jobs SET status=? WHERE id=?",(status,jid)); c.commit(); c.close()


def log(jid,event):
    c=db(); c.execute("INSERT INTO activity(job_id,event,created_at) VALUES(?,?,?)",(jid,event,datetime.now().isoformat(timespec="minutes"))); c.commit(); c.close()


def draft_email(p,j):
    subject=f"Application – {j['title']} – {j['company']}"
    body=f"""Dear Hiring Manager,

I am writing to apply for the {j['title']} position at {j['company']}. I recently completed a First Class Honours degree in IT and Cybersecurity and have practical IT support and networking experience.

My background includes Windows and Microsoft 365 support, user access, troubleshooting, networking fundamentals, and practical exposure to routers, ONTs, Wi-Fi and FTTH/GPON. I have also worked with Active Directory, Microsoft Entra ID and cybersecurity projects during my studies.

I would welcome the opportunity to discuss how my background could fit the role.

Kind regards,
{p['name']}
{p['phone'] or ''}
{p['email'] or ''}"""
    return subject,body


def draft_letter(p,j):
    return f"""Dear Hiring Manager,

I am pleased to submit my application for the {j['title']} position at {j['company']}. I recently completed a First Class Honours degree in IT and Cybersecurity and am seeking a junior opportunity in IT support, infrastructure, networking or cybersecurity.

I bring practical experience supporting Windows devices, Microsoft 365, user access, hardware, Wi-Fi and troubleshooting, as well as networking exposure from my Network Technician internship at Mauritius Telecom involving FTTH/GPON, router and ONT configuration, connectivity troubleshooting and fibre work. My academic work also included Active Directory, Microsoft Entra ID, Windows Server, networking and cybersecurity projects.

I am comfortable learning new technologies, following documentation, troubleshooting methodically and escalating issues with clear information when necessary. I am looking for an environment where I can contribute immediately while developing into a stronger technical professional.

I would welcome the opportunity to discuss my suitability for the role.

Kind regards,
{p['name']}
"""


def followup(p,j):
    return f"""Subject: Follow-up – {j['title']} application

Dear Hiring Manager,

I wanted to follow up on my application for the {j['title']} position submitted recently. I remain very interested in the opportunity and would be grateful for any update regarding the recruitment process.

Kind regards,
{p['name']}"""


def fetch(url):
    headers={"User-Agent":"Mozilla/5.0 (compatible; NgoniJobHunter/1.0; +https://streamlit.io)"}
    r=requests.get(url,headers=headers,timeout=20)
    r.raise_for_status()
    return r.text


def parse_jsonld(soup, base_url):
    found=[]
    for tag in soup.find_all("script", attrs={"type":"application/ld+json"}):
        try: data=json.loads(tag.string or tag.get_text())
        except Exception: continue
        items=data if isinstance(data,list) else [data]
        for x in items:
            if isinstance(x,dict) and x.get("@type") in ("JobPosting",["JobPosting"]):
                found.append({
                    "company": (x.get("hiringOrganization") or {}).get("name","") if isinstance(x.get("hiringOrganization"),dict) else str(x.get("hiringOrganization", "")),
                    "title": x.get("title","") or x.get("name",""),
                    "location": str(((x.get("jobLocation") or {}).get("address") or {}).get("addressLocality", "Mauritius")) if isinstance(x.get("jobLocation"),dict) else "Mauritius",
                    "url": x.get("url") or base_url,
                    "description": BeautifulSoup(str(x.get("description","")),"html.parser").get_text(" ",strip=True),
                    "source": urlparse(base_url).netloc,
                })
    return found


def parse_myjob(html, base_url):
    soup=BeautifulSoup(html,"html.parser")
    found=parse_jsonld(soup,base_url)
    # Fallback: identify cards containing a "View Details" link and infer nearby text.
    for a in soup.find_all("a", href=True):
        txt=a.get_text(" ",strip=True)
        if "view details" not in txt.lower(): continue
        card=a
        for _ in range(5):
            if card.parent: card=card.parent
            if len(card.get_text(" ",strip=True))>80: break
        text=card.get_text(" ",strip=True)
        href=urljoin(base_url,a["href"])
        title=""
        for tag in card.find_all(["h1","h2","h3","h4","h5","strong"]):
            t=tag.get_text(" ",strip=True)
            if t and "view details" not in t.lower(): title=t; break
        if not title:
            bits=[b.strip() for b in re.split(r"\s{2,}|\|",text) if b.strip()]
            title=bits[0] if bits else ""
        if not title or len(title)>160: continue
        company=""
        # Common card layout places company after title; choose a plausible short line.
        lines=[x.strip() for x in card.stripped_strings if x.strip()]
        for line in lines[1:8]:
            if line not in ("Full-time","Part-time","Internship") and len(line)<100 and not line.lower().startswith(("posted","closing","rs ")):
                company=line; break
        found.append({"company":company,"title":title,"location":"Mauritius","url":href,"description":text,"source":urlparse(base_url).netloc})
    # Deduplicate
    out=[]; seen=set()
    for x in found:
        key=(x.get("url") or "",x.get("title","").lower(),x.get("company","").lower())
        if key in seen: continue
        seen.add(key); out.append(x)
    return out


def discover_myjob():
    all_jobs=[]; errors=[]
    for u in MYJOB_URLS:
        try:
            html=fetch(u); all_jobs.extend(parse_myjob(html,u))
        except Exception as e: errors.append(f"{u}: {e}")
    unique=[]; seen=set()
    for j in all_jobs:
        key=(j.get("url") or "",j.get("title","" ).lower())
        if key in seen: continue
        seen.add(key); unique.append(j)
    return unique,errors


def import_csv(data):
    rows=csv.DictReader(io.StringIO(data.decode("utf-8-sig"))); n=0
    for r in rows:
        if r.get("company") and r.get("title"):
            if add_job({"company":r.get("company",""),"title":r.get("title",""),"location":r.get("location","Mauritius"),"url":r.get("url",""),"description":r.get("description",""),"contact_name":r.get("contact_name",""),"contact_email":r.get("contact_email",""),"notes":r.get("notes",""),"source":r.get("source","CSV import")}): n+=1
    return n


def send_email_smtp(to_email, subject, body, settings):
    msg=EmailMessage(); msg["From"]=settings["from_email"]; msg["To"]=to_email; msg["Subject"]=subject; msg.set_content(body)
    context=ssl.create_default_context()
    with smtplib.SMTP(settings["host"],settings["port"],timeout=25) as server:
        server.starttls(context=context); server.login(settings["username"],settings["password"]); server.send_message(msg)


init()
st.set_page_config(page_title="Ngoni Job Hunter Pro", page_icon="🎯", layout="wide")
st.title("🎯 Ngoni Job Hunter Pro")
st.caption("Mauritius IT search • discover → match → tailor → approve → apply → follow up → track")
p=get_profile(); jobs=get_jobs()

tabs=st.tabs(["🎯 Matches","🔎 Find Jobs","📥 Import Jobs","👤 Profile","✉️ Applications","📇 Contacts","📊 Analytics"])

with tabs[0]:
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Jobs",len(jobs)); c2.metric("Strong matches",sum(x["score"]>=70 for x in jobs)); c3.metric("Applied",sum(x["status"]=="Applied" for x in jobs)); c4.metric("Interviews",sum(x["status"]=="Interview" for x in jobs))
    st.divider(); minscore=st.slider("Minimum match score",0,100,55); status=st.selectbox("Status",["All","New","Ready","Applied","Follow-up","Interview","Rejected","Offer"])
    for j in [x for x in jobs if x["score"]>=minscore and (status=="All" or x["status"]==status)]:
        with st.expander(f"**{j['score']}%** — {j['title']} | {j['company']} | {j['location']}"):
            st.write(j["description"][:1400] if j["description"] else "No description stored.")
            if j["url"]: st.markdown(f"[Open vacancy]({j['url']})")
            st.caption(f"Source: {j['source'] or 'Manual'}")
            new=st.selectbox("Status",["New","Ready","Applied","Follow-up","Interview","Rejected","Offer"],index=["New","Ready","Applied","Follow-up","Interview","Rejected","Offer"].index(j["status"]),key=f"st{j['id']}")
            if st.button("Save status",key=f"save{j['id']}"): update_status(j["id"],new); log(j["id"],f"Status → {new}"); st.rerun()

with tabs[1]:
    st.markdown("### 🔎 Automatic vacancy discovery")
    st.write("Searches public job listings from supported sources. It does not bypass CAPTCHAs, private accounts, or anti-bot controls.")
    c1,c2=st.columns(2)
    with c1:
        if st.button("🚀 Scan MyJob.mu now",type="primary"):
            with st.spinner("Scanning public IT listings…"):
                discovered,errors=discover_myjob()
            added=0
            for j in discovered:
                if j.get("title") and add_job({**j,"contact_name":"","contact_email":"","notes":"Automatically discovered; review before applying."}): added+=1
            st.success(f"Found {len(discovered)} public listings; added {added} new jobs.")
            if errors:
                st.warning("Some sources could not be reached: " + " | ".join(errors[:2]))
    with c2:
        threshold=st.slider("Auto-queue score",50,95,70)
        if st.button("⭐ Mark strong matches Ready"):
            c=db(); c.execute("UPDATE jobs SET status='Ready' WHERE score>=? AND status='New'",(threshold,)); c.commit(); c.close(); st.success("Strong matches moved to Ready.")
    st.info("Current supported automatic discovery is MyJob public listings. The source page currently contains Mauritius IT roles such as IT Support, Cloud & Security, Technical Support L1 and Systems/Network roles. The app will re-check the source when you click Scan.")

with tabs[2]:
    st.markdown("### Import jobs from CSV")
    st.write("Columns: company,title,location,url,description,contact_name,contact_email,notes,source")
    uploaded=st.file_uploader("CSV file",type=["csv"])
    if uploaded and st.button("Import and score"): st.success(f"Imported {import_csv(uploaded.getvalue())} new jobs and scored them.")
    st.markdown("### Manual job")
    with st.form("manual"):
        v={"company":st.text_input("Company"),"title":st.text_input("Role"),"location":st.text_input("Location","Mauritius"),"url":st.text_input("URL"),"description":st.text_area("Description"),"contact_name":st.text_input("Contact"),"contact_email":st.text_input("Email"),"notes":st.text_area("Notes"),"source":st.text_input("Source","Manual")}
        if st.form_submit_button("Add & score"):
            if v["company"] and v["title"]: st.success("Added and scored.") if add_job(v) else st.info("That vacancy is already in your tracker.")
            else: st.error("Company and role required.")

with tabs[3]:
    with st.form("prof"):
        v={"name":st.text_input("Name",p["name"] or ""),"email":st.text_input("Email",p["email"] or ""),"phone":st.text_input("Phone",p["phone"] or ""),"linkedin":st.text_input("LinkedIn",p["linkedin"] or ""),"summary":st.text_area("Summary",p["summary"] or ""),"skills":st.text_area("Skills",p["skills"] or ""),"experience":st.text_area("Experience",p["experience"] or ""),"education":st.text_area("Education",p["education"] or ""),"preferred_roles":st.text_input("Preferred roles",p["preferred_roles"] or "IT Support, IT Technician, Network, Infrastructure, Systems, Cybersecurity"),"max_experience":st.number_input("Maximum experience requirement you want to accept",0,10,int(p["max_experience"] or 2)),"reject_french":st.checkbox("Strongly penalise jobs requiring French",bool(p["reject_french"]))}
        if st.form_submit_button("Save profile"): save_profile(v); st.success("Profile saved.")

with tabs[4]:
    st.markdown("### Application centre")
    st.caption("Automatic submission is limited to actions the vacancy actually supports. Email applications can be sent after approval; web forms open for you to complete, so the app never bypasses CAPTCHA or login/anti-bot protections.")
    for j in jobs:
        if j["status"] in ["Rejected","Offer"]: continue
        with st.expander(f"{j['score']}% — {j['company']} — {j['title']}"):
            subject,body=draft_email(p,j); letter=draft_letter(p,j)
            if j["status"] in ["New","Ready"]:
                st.text_input("Subject",subject,key=f"sub{j['id']}")
                st.text_area("Recruiter email",body,key=f"em{j['id']}",height=220)
                st.text_area("Cover letter",letter,key=f"cl{j['id']}",height=300)
            if j["contact_email"]:
                st.caption(f"Public/contact email available: {j['contact_email']}")
            else:
                st.caption("No recruiter email stored. Use the vacancy page to apply or add a public recruiter email in Contacts/Job data.")
            if j["url"]:
                st.link_button("🌐 Open application page",j["url"])
            if j["status"]=="New" and st.button("Mark Ready",key=f"ready{j['id']}"): update_status(j["id"],"Ready"); log(j["id"],"Application prepared"); st.rerun()
            if j["status"]=="Ready":
                st.warning("Approval required. Check the job, CV/letter and recipient before sending.")
                if j["contact_email"]:
                    with st.form(f"send{j['id']}"):
                        approve=st.checkbox("I approve sending this application email",key=f"approve{j['id']}")
                        host=st.text_input("SMTP host",st.secrets.get("SMTP_HOST", "smtp.gmail.com"),key=f"host{j['id']}")
                        port=st.number_input("SMTP port",1,65535,int(st.secrets.get("SMTP_PORT",587)),key=f"port{j['id']}")
                        user=st.text_input("SMTP username",st.secrets.get("SMTP_USERNAME",p["email"] or ""),key=f"user{j['id']}")
                        pwd=st.text_input("SMTP password / app password",type="password",key=f"pwd{j['id']}")
                        frm=st.text_input("From email",st.secrets.get("SMTP_FROM",p["email"] or ""),key=f"from{j['id']}")
                        if st.form_submit_button("📨 Approve & send email"):
                            if not approve: st.error("Tick the approval box first.")
                            elif not j["contact_email"]: st.error("No recipient email.")
                            else:
                                try:
                                    send_email_smtp(j["contact_email"],subject,body,{"host":host,"port":port,"username":user,"password":pwd,"from_email":frm})
                                    update_status(j["id"],"Applied"); c=db(); c.execute("UPDATE jobs SET followup_at=? WHERE id=?",((datetime.now()+timedelta(days=7)).date().isoformat(),j["id"])); c.commit(); c.close(); log(j["id"],"Application email sent after approval"); st.success("Application email sent."); st.rerun()
                                except Exception as e: st.error(f"Email failed: {e}")
                else:
                    if st.button("✅ I applied on the website",key=f"webapp{j['id']}"):
                        update_status(j["id"],"Applied"); c=db(); c.execute("UPDATE jobs SET followup_at=? WHERE id=?",((datetime.now()+timedelta(days=7)).date().isoformat(),j["id"])); c.commit(); c.close(); log(j["id"],"User confirmed web application submitted"); st.rerun()
            if j["status"]=="Applied":
                st.success(f"Applied. Follow-up target: {j['followup_at'] or (datetime.now()+timedelta(days=7)).date().isoformat()}")
                if st.button("✉️ Draft follow-up",key=f"fu{j['id']}"): st.text_area("Follow-up",followup(p,j),height=180,key=f"fut{j['id']}")

with tabs[5]:
    st.write("Store recruiter/hiring-manager contacts discovered from permitted public sources.")
    with st.form("contact"):
        vals=[st.text_input(x) for x in ["Company","Name","Role","Email","LinkedIn","Source","Notes"]]
        if st.form_submit_button("Save contact"):
            c=db(); c.execute("INSERT INTO contacts(company,name,role,email,linkedin,source,notes) VALUES(?,?,?,?,?,?,?)",vals); c.commit(); c.close(); st.success("Saved.")
    c=db(); contacts=c.execute("SELECT * FROM contacts ORDER BY id DESC").fetchall(); c.close()
    if contacts: st.dataframe([dict(x) for x in contacts],use_container_width=True)

with tabs[6]:
    rows=get_jobs()
    if rows:
        counts={}
        for x in rows: counts[x["status"]]=counts.get(x["status"],0)+1
        st.bar_chart(counts); st.write("Average match score:",round(sum(x["score"] for x in rows)/len(rows),1))
    else: st.info("Add or discover jobs to see analytics.")

st.divider(); st.caption("Safety/quality: public-source discovery + human approval. No CAPTCHA bypass, private LinkedIn scraping, impersonation, or blind auto-submission.")
