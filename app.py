
import csv, io, re, sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import streamlit as st

DB = Path(__file__).with_name("job_hunter.db")

ROLE_KEYWORDS = {
    "it support": 15, "helpdesk": 14, "help desk": 14, "it technician": 14,
    "technical support": 13, "systems administrator": 13, "system administrator": 13,
    "network": 12, "infrastructure": 12, "cybersecurity": 12, "security": 9,
    "windows": 8, "active directory": 10, "microsoft 365": 8, "m365": 8,
    "azure": 7, "entra": 7, "firewall": 7, "cloud": 5, "noc": 8, "soc": 8
}
BAD = {"french": -35, "fluent french": -45, "native french": -50}
EXPERIENCE_PATTERNS = [
    (re.compile(r'(\d+)\s*\+?\s*years?', re.I), 1),
    (re.compile(r'(\d+)\s*-\s*(\d+)\s*years?', re.I), 1),
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
      url TEXT, description TEXT, score INTEGER DEFAULT 0, status TEXT DEFAULT 'New',
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
    c=db(); r=c.execute("SELECT * FROM profile WHERE id=1").fetchone(); c.close(); return r

def save_profile(v):
    c=db()
    c.execute("""UPDATE profile SET name=?,email=?,phone=?,linkedin=?,summary=?,skills=?,
      experience=?,education=?,preferred_roles=?,max_experience=?,reject_french=? WHERE id=1""",
      (v["name"],v["email"],v["phone"],v["linkedin"],v["summary"],v["skills"],
       v["experience"],v["education"],v["preferred_roles"],v["max_experience"],v["reject_french"]))
    c.commit(); c.close()

def score_job(j,p):
    text=(j["title"]+" "+(j["description"] or "")).lower()
    score=20
    for k,v in ROLE_KEYWORDS.items():
        if k in text: score += v
    if any(x in text for x in ["junior","trainee","entry level","entry-level","graduate","0-1 year","1 year"]): score += 12
    if p["reject_french"] and any(x in text for x in BAD): score += min(BAD[x] for x in BAD if x in text)
    years=[]
    for pat,_ in EXPERIENCE_PATTERNS:
        for m in pat.finditer(text):
            try: years.append(int(m.group(1)))
            except: pass
    if years and max(years) > int(p["max_experience"] or 2): score -= 20
    return max(0,min(100,score))

def add_job(v):
    c=db()
    score=score_job(v,get_profile())
    c.execute("""INSERT INTO jobs(company,title,location,url,description,score,status,
      contact_name,contact_email,notes,source,created_at,followup_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (v["company"],v["title"],v["location"],v["url"],v["description"],score,"New",
       v["contact_name"],v["contact_email"],v["notes"],v["source"],
       datetime.now().isoformat(timespec="minutes"),None))
    c.commit(); c.close()

def get_jobs():
    c=db(); r=c.execute("SELECT * FROM jobs ORDER BY score DESC, id DESC").fetchall(); c.close(); return r

def get_job(jid):
    c=db(); r=c.execute("SELECT * FROM jobs WHERE id=?",(jid,)).fetchone(); c.close(); return r

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

def import_csv(data):
    rows=csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    n=0
    for r in rows:
        if r.get("company") and r.get("title"):
            add_job({
                "company":r.get("company",""),"title":r.get("title",""),
                "location":r.get("location","Mauritius"),"url":r.get("url",""),
                "description":r.get("description",""),"contact_name":r.get("contact_name",""),
                "contact_email":r.get("contact_email",""),"notes":r.get("notes",""),
                "source":r.get("source","CSV import")
            }); n+=1
    return n

init()
st.set_page_config(page_title="Ngoni Job Hunter Pro", page_icon="🎯", layout="wide")
st.title("🎯 Ngoni Job Hunter Pro")
st.caption("Mauritius IT search • match → tailor → approve → send → follow up → track")

p=get_profile()
jobs=get_jobs()

tabs=st.tabs(["🎯 Matches","📥 Import Jobs","👤 Profile","✉️ Applications","📇 Contacts","📊 Analytics"])

with tabs[0]:
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Jobs",len(jobs))
    c2.metric("Strong matches",sum(x["score"]>=70 for x in jobs))
    c3.metric("Applications",sum(x["status"]=="Applied" for x in jobs))
    c4.metric("Interviews",sum(x["status"]=="Interview" for x in jobs))
    st.divider()
    minscore=st.slider("Minimum match score",0,100,55)
    status=st.selectbox("Status",["All","New","Ready","Applied","Follow-up","Interview","Rejected","Offer"])
    for j in [x for x in jobs if x["score"]>=minscore and (status=="All" or x["status"]==status)]:
        with st.expander(f"**{j['score']}%** — {j['title']} | {j['company']} | {j['location']}"):
            st.write(j["description"][:1200] if j["description"] else "No description stored.")
            if j["url"]: st.write(j["url"])
            st.caption(f"Source: {j['source'] or 'Manual'}")
            new=st.selectbox("Status",["New","Ready","Applied","Follow-up","Interview","Rejected","Offer"],index=["New","Ready","Applied","Follow-up","Interview","Rejected","Offer"].index(j["status"]),key=f"st{j['id']}")
            if st.button("Save status",key=f"save{j['id']}"):
                update_status(j["id"],new); log(j["id"],f"Status → {new}"); st.rerun()

with tabs[1]:
    st.markdown("### Import jobs from CSV")
    st.write("Use columns: company,title,location,url,description,contact_name,contact_email,notes,source")
    uploaded=st.file_uploader("CSV file",type=["csv"])
    if uploaded and st.button("Import and score"):
        n=import_csv(uploaded.getvalue()); st.success(f"Imported {n} jobs and scored them.")
    st.markdown("### Manual job")
    with st.form("manual"):
        v={
            "company":st.text_input("Company"),"title":st.text_input("Role"),
            "location":st.text_input("Location","Mauritius"),"url":st.text_input("URL"),
            "description":st.text_area("Description"),"contact_name":st.text_input("Contact"),
            "contact_email":st.text_input("Email"),"notes":st.text_area("Notes"),
            "source":st.text_input("Source","Manual")
        }
        if st.form_submit_button("Add & score"):
            if v["company"] and v["title"]: add_job(v); st.success("Added and scored.")
            else: st.error("Company and role required.")

with tabs[2]:
    with st.form("prof"):
        v={
            "name":st.text_input("Name",p["name"] or ""),
            "email":st.text_input("Email",p["email"] or ""),
            "phone":st.text_input("Phone",p["phone"] or ""),
            "linkedin":st.text_input("LinkedIn",p["linkedin"] or ""),
            "summary":st.text_area("Summary",p["summary"] or ""),
            "skills":st.text_area("Skills",p["skills"] or ""),
            "experience":st.text_area("Experience",p["experience"] or ""),
            "education":st.text_area("Education",p["education"] or ""),
            "preferred_roles":st.text_input("Preferred roles","IT Support, IT Technician, Network, Infrastructure, Systems, Cybersecurity"),
            "max_experience":st.number_input("Maximum experience requirement you want to accept",0,10,int(p["max_experience"] or 2)),
            "reject_french":st.checkbox("Strongly penalise jobs requiring French",bool(p["reject_french"]))
        }
        if st.form_submit_button("Save profile"):
            save_profile(v); st.success("Profile saved.")

with tabs[3]:
    for j in jobs:
        if j["status"] in ["Rejected","Offer"]: continue
        with st.expander(f"{j['company']} — {j['title']} ({j['score']}%)"):
            subject,body=draft_email(p,j)
            st.text_input("Subject",subject,key=f"sub{j['id']}")
            st.text_area("Email",body,key=f"em{j['id']}",height=220)
            st.text_area("Cover letter",draft_letter(p,j),key=f"cl{j['id']}",height=320)
            if j["status"]=="New":
                if st.button("Mark Ready",key=f"ready{j['id']}"):
                    update_status(j["id"],"Ready"); log(j["id"],"Application draft reviewed"); st.rerun()
            if j["status"]=="Ready":
                st.warning("Human approval required before sending. Connect your mail provider in the next version.")
                if st.button("Mark Applied",key=f"app{j['id']}"):
                    update_status(j["id"],"Applied")
                    c=db(); c.execute("UPDATE jobs SET followup_at=? WHERE id=?",
                                      ((datetime.now()+timedelta(days=7)).date().isoformat(),j["id"])); c.commit(); c.close()
                    log(j["id"],"Application approved/sent externally"); st.rerun()
            if j["status"]=="Applied":
                st.success(f"Follow-up target: {(datetime.now()+timedelta(days=7)).date().isoformat()}")

with tabs[4]:
    st.write("Store recruiter/hiring-manager contacts discovered from permitted public sources.")
    with st.form("contact"):
        vals=[st.text_input(x) for x in ["Company","Name","Role","Email","LinkedIn","Source","Notes"]]
        if st.form_submit_button("Save contact"):
            c=db(); c.execute("INSERT INTO contacts(company,name,role,email,linkedin,source,notes) VALUES(?,?,?,?,?,?,?)",vals); c.commit(); c.close(); st.success("Saved.")
    c=db(); contacts=c.execute("SELECT * FROM contacts ORDER BY id DESC").fetchall(); c.close()
    if contacts: st.dataframe([dict(x) for x in contacts],use_container_width=True)

with tabs[5]:
    rows=get_jobs()
    if rows:
        st.write("Status breakdown")
        counts={}
        for x in rows: counts[x["status"]]=counts.get(x["status"],0)+1
        st.bar_chart(counts)
        st.write("Average match score:",round(sum(x["score"] for x in rows)/len(rows),1))
    else: st.info("Add jobs to see analytics.")

st.divider()
st.caption("Safety/quality: this version does not bypass CAPTCHAs, scrape private LinkedIn data, impersonate recruiters, or auto-submit without approval.")
