"""Live autonomous-pipeline demo: upload CV -> program does the rest.

Upload CV -> parse -> recommend roles -> for each job:
  build masters, tailor CV, cover letter, 60s + 180s video scripts.
Nothing is sent; everything lands as a reviewable package.
"""
import http.client
import io
import json

BASE = "/api/v1"


def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"} if data else {}
    c = http.client.HTTPConnection("127.0.0.1", 8001)
    c.request(method, BASE + path, data, h)
    r = c.getresponse()
    b = r.read()
    return r.status, (json.loads(b) if b else None)


CV = """Thando Ndlovu
thando.ndlovu@example.com
+27 82 123 4567
Johannesburg, South Africa

Summary
Customer operations professional with 6 years of experience supporting remote SaaS teams.

Experience
Support Team Lead, Luno (2022 - present)
- Led a remote team of 4 support agents; raised CSAT from 82% to 91%
- Handled 40+ tickets per day across email and chat
- Reduced repeat tickets by 22% with a new knowledge base
Support Agent, PayFast (2019 - 2022)
- Resolved 25+ customer issues daily while meeting SLA targets

Education
BCom, University of Pretoria (2015 - 2018)

Skills
Project management, data analysis, communication, stakeholder management, Excel, customer success
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate

buf = io.BytesIO()
SimpleDocTemplate(buf, pagesize=A4).build(
    [Paragraph(l.replace("&", "&amp;"), getSampleStyleSheet()["Normal"]) for l in CV.splitlines()]
)
pdf = buf.getvalue()

# 1. profile + full consent set
s, p = req("POST", "/profiles", {"first_name": "Thando", "last_name": "Ndlovu"})
pid = p["id"]
for item in ("profile_processing", "job_matching", "video_recording", "media_use"):
    req("POST", f"/profiles/{pid}/consents", {"item": item})
print("1. profile + 4 consents granted:", s)

# 2. upload CV (PDF)
boundary = "cfbound123"
mp = (
    f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"cv.pdf\"\r\n"
    f"Content-Type: application/pdf\r\n\r\n"
).encode() + pdf + f"\r\n--{boundary}--\r\n".encode()
c = http.client.HTTPConnection("127.0.0.1", 8001)
c.request("POST", f"{BASE}/profiles/{pid}/cvs/upload", mp,
          {"Content-Type": f"multipart/form-data; boundary={boundary}"})
r = c.getresponse()
up = json.loads(r.read())
cv_id = up["id"]
print(f"2. CV parsed | {up['parsed']['name']} | {len(up['parsed']['experience'])} roles | "
      f"{len(up['parsed']['skills'])} skills")

# 3. program recommends target roles
s, rec = req("POST", f"/profiles/{pid}/roles/recommend")
print("3. recommended target roles:")
for x in rec:
    print(f"     {x['match_pct']:>5}%  {x['role']}  (matched: {', '.join(x['matched'][:3])})")

# 4. two jobs
JD1 = ("Customer Success Manager - Remote (Africa). We need a Customer Success Manager to own "
       "onboarding and retention. Requirements: 5+ years customer success or customer service, "
       "strong data analysis with Excel, stakeholder management across time zones, "
       "communication skills, CRM tools, python automation a plus.")
JD2 = ("Operations Analyst - Remote (UTC+2 friendly). Build operational reports in Excel, "
       "analyse process data, present findings to stakeholders, track key metrics, "
       "coordinate with cross-functional teams.")
j1 = req("POST", f"/profiles/{pid}/job-descriptions",
         {"title": "Customer Success Manager", "company": "Acme Remote", "text": JD1})[1]
j2 = req("POST", f"/profiles/{pid}/job-descriptions",
         {"title": "Operations Analyst", "company": "BuildCo", "text": JD2})[1]
print("4. two jobs saved")

# 5. THE autonomous pipeline: one call, program does the rest
s, out = req("POST", f"/profiles/{pid}/auto-pipeline",
             {"cv_id": cv_id, "jd_ids": [j1["id"], j2["id"]]})
print(f"5. auto-pipeline -> {len(out['applications'])} application packages:")
first = out["applications"][0]
for a in out["applications"]:
    v = a["videos"][0]
    import re
    wc = len(re.findall(r"\b\w+\b", v["script_text"]))
    print(f"   - {a['jd_title']} @ {a['jd_company']} | tailored CV: yes | "
          f"letter: {len(a['letter']['text'].split())} words | "
          f"video script: {wc} words ({v['target_seconds']}s target)")
print()
print("--- Sample 60s video script (first job) ---")
print(first["videos"][0]["script_text"])
print()
print("--- Sample cover letter opening (first job) ---")
print("\n".join(first["letter"]["text"].split("\n\n")[:2]))
print()
print(f"skipped: {out['skipped']}")
print("AUTONOMOUS PIPELINE OK - candidate reviews & approves, nothing is sent")
