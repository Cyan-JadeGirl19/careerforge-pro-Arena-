"""Live end-to-end smoke test against the running API (dev only)."""
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

s, p = req("POST", "/profiles", {"first_name": "Thando", "last_name": "Ndlovu"})
pid = p["id"]
for item in ("profile_processing", "job_matching"):
    req("POST", f"/profiles/{pid}/consents", {"item": item})
print("1. profile + consents:", s)

boundary = "cfbound123"
mp = (
    f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"cv.pdf\"\r\n"
    f"Content-Type: application/pdf\r\n\r\n"
).encode() + pdf + f"\r\n--{boundary}--\r\n".encode()
c = http.client.HTTPConnection("127.0.0.1", 8001)
c.request(
    "POST", f"{BASE}/profiles/{pid}/cvs/upload", mp,
    {"Content-Type": f"multipart/form-data; boundary={boundary}"},
)
r = c.getresponse()
up = json.loads(r.read())
cv_id = up["id"]
print(
    "2. uploaded PDF:", r.status,
    "| name:", up["parsed"]["name"],
    "| roles:", len(up["parsed"]["experience"]),
    "| skills:", len(up["parsed"]["skills"]),
    "| notes:", len(up["parsed"]["extraction_notes"]),
)

s, masters = req("POST", f"/cvs/{cv_id}/versions/build-masters", {"role_focus": "Customer Success Manager"})
print("3. masters:", [(m["kind"], m["title"]) for m in masters])

JD = (
    "Customer Success Manager - Remote (Africa). We need a Customer Success Manager to own "
    "onboarding and retention. Requirements: 5+ years customer success or customer service, "
    "strong data analysis with Excel, stakeholder management across time zones, "
    "communication skills, CRM tools, python automation a plus."
)
s, jd = req(
    "POST", f"/profiles/{pid}/job-descriptions",
    {"title": "Customer Success Manager", "company": "Acme Remote", "text": JD},
)
print("4. JD saved:", s)

s, tailored = req("POST", f"/cv-versions/{masters[1]['id']}/tailor", {"jd_id": jd["id"]})
rep = tailored["report"]
print(
    "5. tailored | coverage:", str(rep["coverage"]) + "%",
    "| gaps:", len(rep["gaps"]),
    "| surfaced:", rep["surfaced_keywords"][:3],
)

c = http.client.HTTPConnection("127.0.0.1", 8001)
c.request("GET", f"{BASE}/tailored/{tailored['id']}/export?format=docx")
docx = c.getresponse().read()
c.request("GET", f"{BASE}/tailored/{tailored['id']}/export?format=pdf")
pdf_out = c.getresponse().read()
print(
    "6. exports | docx:", len(docx), "bytes valid:", docx[:2] == b"PK",
    "| pdf:", len(pdf_out), "bytes valid:", pdf_out[:4] == b"%PDF",
)
print("LIVE PIPELINE OK")
