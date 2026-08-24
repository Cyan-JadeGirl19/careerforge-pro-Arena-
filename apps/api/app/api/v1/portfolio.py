"""Portfolio Builder routes.

Items are private until the candidate approves them (agreed rule:
approval before anything is published or attached). GitHub auto-pull is
user-directed, one public repo at a time, against GitHub's public API.
"""
import json
import re
import uuid
import urllib.parse
import urllib.request

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db import get_db
from ...models import PortfolioItem, Profile
from .profiles import get_profile_or_404

router = APIRouter(tags=["portfolio"])

TYPES = ("project", "github_repo", "writing_sample", "design", "link")


def _out(i: PortfolioItem) -> dict:
    return {
        "id": i.id,
        "profile_id": i.profile_id,
        "title": i.title,
        "type": i.type,
        "description": i.description,
        "url": i.url,
        "tech_tags": i.tech_tags,
        "featured": i.featured,
        "approved": i.approved,
        "created_at": i.created_at,
    }


@router.get("/profiles/{profile_id}/portfolio")
def list_portfolio(profile_id: str, db: Session = Depends(get_db)) -> list[dict]:
    get_profile_or_404(db, profile_id)
    rows = db.scalars(
        select(PortfolioItem)
        .where(PortfolioItem.profile_id == profile_id)
        .order_by(PortfolioItem.created_at.desc())
    ).all()
    return [_out(r) for r in rows]


@router.post("/profiles/{profile_id}/portfolio", status_code=201)
def add_portfolio_item(
    profile_id: str,
    body: dict,
    db: Session = Depends(get_db),
) -> dict:
    get_profile_or_404(db, profile_id)
    item_type = body.get("type", "project")
    if item_type not in TYPES:
        raise HTTPException(
            status_code=422,
            detail={"code": "BAD_TYPE", "message": f"type must be one of {TYPES}"},
        )
    title = (body.get("title") or "").strip()
    if not title:
        raise HTTPException(
            status_code=422,
            detail={"code": "TITLE_REQUIRED", "message": "title is required"},
        )
    row = PortfolioItem(
        id=str(uuid.uuid4()),
        profile_id=profile_id,
        title=title[:200],
        type=item_type,
        description=(body.get("description") or "")[:4000] or None,
        url=(body.get("url") or "")[:500] or None,
        tech_tags=(body.get("tech_tags") or "")[:300],
        featured=bool(body.get("featured")),
        approved=bool(body.get("approved")),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _out(row)


@router.patch("/portfolio/{item_id}")
def update_portfolio_item(
    item_id: str, body: dict, db: Session = Depends(get_db)
) -> dict:
    row = db.get(PortfolioItem, item_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "ITEM_NOT_FOUND", "message": "No item with that id."},
        )
    for field in ("title", "type", "description", "url", "tech_tags"):
        if field in body and body[field] is not None:
            setattr(row, field, str(body[field]))
    for field in ("featured", "approved"):
        if field in body:
            setattr(row, field, bool(body[field]))
    db.commit()
    db.refresh(row)
    return _out(row)


@router.delete("/portfolio/{item_id}", status_code=204)
def delete_portfolio_item(item_id: str, db: Session = Depends(get_db)) -> None:
    row = db.get(PortfolioItem, item_id)
    if row is not None:
        db.delete(row)
        db.commit()


@router.post("/profiles/{profile_id}/portfolio/github", status_code=201)
def pull_github_repo(
    profile_id: str, body: dict, db: Session = Depends(get_db)
) -> dict:
    """User-directed: pull metadata + README for ONE public repo."""
    get_profile_or_404(db, profile_id)
    repo = (body.get("repo") or "").strip()
    if not re.match(r"^[\w.-]+/[\w.-]+$", repo):
        raise HTTPException(
            status_code=422,
            detail={"code": "BAD_REPO", "message": "Use the format owner/repo-name"},
        )
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}",
            headers={"User-Agent": "CareerForgePro/1.0", "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            meta = json.loads(resp.read(500_000).decode("utf-8", errors="replace"))
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "REPO_FETCH_FAILED",
                "message": f"Could not read that repo (public?): {str(exc)[:120]}",
            },
        )
    readme = ""
    try:
        req2 = urllib.request.Request(
            f"https://raw.githubusercontent.com/{repo}/HEAD/README.md",
            headers={"User-Agent": "CareerForgePro/1.0"},
        )
        with urllib.request.urlopen(req2, timeout=15) as resp:
            readme = resp.read(40_000).decode("utf-8", errors="replace")
    except Exception:
        readme = ""
    readme_plain = re.sub(r"[#*`>_]", " ", readme)
    readme_plain = re.sub(r"\s+", " ", readme_plain).strip()[:1500]

    desc = (meta.get("description") or "").strip()
    row = PortfolioItem(
        id=str(uuid.uuid4()),
        profile_id=profile_id,
        title=(meta.get("full_name") or repo)[:200],
        type="github_repo",
        description=(desc + ("\n\n" + readme_plain if readme_plain else ""))[:4000] or None,
        url=meta.get("html_url"),
        tech_tags=(meta.get("language") or "")[:300],
        featured=False,
        approved=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    out = _out(row)
    out["stars"] = meta.get("stargazers_count", 0)
    return out


def _esc(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


@router.get("/portfolio-page/{profile_id}", response_class=HTMLResponse)
def portfolio_page(profile_id: str, db: Session = Depends(get_db)) -> HTMLResponse:
    """Public portfolio: APPROVED items only."""
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail={"code": "PROFILE_NOT_FOUND", "message": "No profile."})
    items = db.scalars(
        select(PortfolioItem).where(
            PortfolioItem.profile_id == profile_id, PortfolioItem.approved.is_(True)
        )
    ).all()
    name = " ".join(x for x in [profile.first_name, profile.last_name] if x) or "Portfolio"

    cards = []
    for it in items:
        tags = " ".join(
            f'<span class="tag">{_esc(t)}</span>'
            for t in (it.tech_tags or "").split(",")
            if t.strip()
        )
        cards.append(f"""
      <article class="card">
        <h2>{_esc(it.title)}{ ' <span class="feat">★ featured</span>' if it.featured else ''}</h2>
        {f'<p class="desc">{_esc(it.description)}</p>' if it.description else ''}
        <div class="tags">{tags}</div>
        {f'<a class="link" href="{_esc(it.url)}" target="_blank" rel="noopener">open project</a>' if it.url else ''}
      </article>""")

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(name)} — Portfolio</title>
<style>
body{{font:16px/1.6 Inter,system-ui,sans-serif;margin:0;background:#f6f8fb;color:#172033}}
.wrap{{max-width:860px;margin:0 auto;padding:48px 20px}}
h1{{font-size:34px;margin:0 0 6px}}
.sub{{color:#65708a;margin:0 0 30px}}
.card{{background:#fff;border:1px solid #e5e9f2;border-radius:14px;padding:22px;margin-bottom:16px;box-shadow:0 10px 30px #23345b0d}}
.card h2{{margin:0 0 8px;font-size:19px}}
.desc{{margin:0 0 10px;color:#39415a;white-space:pre-line}}
.tag{{display:inline-block;background:#efedff;color:#4e42bd;border-radius:999px;padding:3px 10px;font-size:12px;margin-right:6px}}
.link{{color:#5b4bdb;font-weight:700;font-size:14px}}
.feat{{color:#c87918;font-size:13px}}
.empty{{color:#65708a;text-align:center;padding:60px 10px}}
</style></head><body><div class="wrap">
<h1>{_esc(name)}</h1>
<p class="sub">Work samples &amp; projects</p>
{''.join(cards) if cards else '<div class="empty">Nothing published yet.</div>'}
</div></body></html>"""
    return HTMLResponse(html)
