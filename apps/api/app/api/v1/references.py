"""Reference Manager routes.

Private by default: references are hidden from CVs, shared only for
applications the candidate selects, and every share path requires
permission confirmation + approval. Documents are stored privately.
"""
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...consents import require_consent
from ...db import get_db
from ...models import Application, Profile, Reference, ReferenceDocument
from ...references import parse_list, store
from ...schemas import (
    AttachReferencesIn,
    ApplicationOut,
    ReferenceCreate,
    ReferenceDocumentOut,
    ReferenceOut,
    ReferenceUpdate,
)
from .applications_internal import app_out
from .profiles import get_profile_or_404

router = APIRouter(tags=["references"])


def _doc_out(d: ReferenceDocument) -> ReferenceDocumentOut:
    return ReferenceDocumentOut(
        id=d.id,
        reference_id=d.reference_id,
        filename=d.filename,
        content_type=d.content_type,
        size=d.size,
        created_at=d.created_at,
    )


def _ref_out(r: Reference, db: Session) -> ReferenceOut:
    docs = db.scalars(
        select(ReferenceDocument).where(ReferenceDocument.reference_id == r.id)
    ).all()
    return ReferenceOut(
        id=r.id,
        profile_id=r.profile_id,
        name=r.name,
        title=r.title,
        relationship=r.relationship,
        company=r.company,
        email=r.email,
        phone=r.phone,
        type=r.type,
        notes=r.notes,
        permission_confirmed=r.permission_confirmed,
        permission_confirmed_at=r.permission_confirmed_at,
        approved=r.approved,
        include_by_default=r.include_by_default,
        suppressed=r.suppressed,
        documents=[_doc_out(d) for d in docs],
        created_at=r.created_at,
    )


def get_ref_or_404(db: Session, ref_id: str) -> Reference:
    r = db.get(Reference, ref_id)
    if r is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "REFERENCE_NOT_FOUND", "message": "No reference with that id."},
        )
    return r


def get_app_or_404(db: Session, app_id: str) -> Application:
    a = db.get(Application, app_id)
    if a is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "APPLICATION_NOT_FOUND", "message": "No application with that id."},
        )
    return a


# --- CRUD ---------------------------------------------------------------------


@router.post("/profiles/{profile_id}/references", response_model=ReferenceOut, status_code=201)
def create_reference(
    profile_id: str, payload: ReferenceCreate, db: Session = Depends(get_db)
) -> ReferenceOut:
    profile = get_profile_or_404(db, profile_id)
    require_consent(db, profile.id, "reference_sharing")
    r = Reference(
        id=str(uuid.uuid4()),
        profile_id=profile.id,
        name=payload.name.strip(),
        title=payload.title,
        relationship=payload.relationship,
        company=payload.company,
        email=payload.email,
        phone=payload.phone,
        type=payload.type,
        notes=payload.notes,
        permission_confirmed=payload.permission_confirmed,
        permission_confirmed_at=datetime.now(timezone.utc)
        if payload.permission_confirmed
        else None,
        include_by_default=payload.include_by_default,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return _ref_out(r, db)


@router.get("/profiles/{profile_id}/references", response_model=list[ReferenceOut])
def list_references(
    profile_id: str,
    include_suppressed: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[ReferenceOut]:
    get_profile_or_404(db, profile_id)
    stmt = select(Reference).where(Reference.profile_id == profile_id)
    if not include_suppressed:
        stmt = stmt.where(Reference.suppressed.is_(False))
    rows = db.scalars(stmt.order_by(Reference.created_at.desc())).all()
    return [_ref_out(r, db) for r in rows]


@router.get("/references/{ref_id}", response_model=ReferenceOut)
def get_reference(ref_id: str, db: Session = Depends(get_db)) -> ReferenceOut:
    return _ref_out(get_ref_or_404(db, ref_id), db)


@router.patch("/references/{ref_id}", response_model=ReferenceOut)
def update_reference(
    ref_id: str, payload: ReferenceUpdate, db: Session = Depends(get_db)
) -> ReferenceOut:
    r = get_ref_or_404(db, ref_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "permission_confirmed":
            # keep the timestamp honest: set on confirm, cleared on revoke
            r.permission_confirmed_at = (
                datetime.now(timezone.utc) if value is True else None
            )
        setattr(r, field, value)
    db.commit()
    db.refresh(r)
    return _ref_out(r, db)


@router.delete("/references/{ref_id}", status_code=204)
def delete_reference(ref_id: str, db: Session = Depends(get_db)) -> None:
    r = get_ref_or_404(db, ref_id)
    for d in db.scalars(
        select(ReferenceDocument).where(ReferenceDocument.reference_id == r.id)
    ).all():
        db.delete(d)
    db.delete(r)
    db.commit()


# --- documents (letters / lists) ------------------------------------------------


@router.post(
    "/references/{ref_id}/documents",
    response_model=ReferenceDocumentOut,
    status_code=201,
)
async def upload_reference_document(
    ref_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)
) -> ReferenceDocumentOut:
    r = get_ref_or_404(db, ref_id)
    require_consent(db, r.profile_id, "reference_sharing")
    data = await file.read()
    try:
        store.validate_document(file.filename or "reference.pdf", data)
    except ValueError as exc:
        raise HTTPException(status_code=415, detail={"code": "UNSUPPORTED_FILE", "message": str(exc)})
    ctype = store.content_type_for(file.filename or "reference.pdf")
    d = ReferenceDocument(
        id=str(uuid.uuid4()),
        reference_id=r.id,
        profile_id=r.profile_id,
        filename=(file.filename or "reference")[:300],
        content_type=ctype,
        size=len(data),
        data=data,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return _doc_out(d)


@router.get("/references/{ref_id}/documents", response_model=list[ReferenceDocumentOut])
def list_reference_documents(
    ref_id: str, db: Session = Depends(get_db)
) -> list[ReferenceDocumentOut]:
    r = get_ref_or_404(db, ref_id)
    docs = db.scalars(
        select(ReferenceDocument).where(ReferenceDocument.reference_id == r.id)
    ).all()
    return [_doc_out(d) for d in docs]


def get_doc_or_404(db: Session, doc_id: str) -> ReferenceDocument:
    d = db.get(ReferenceDocument, doc_id)
    if d is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "DOCUMENT_NOT_FOUND", "message": "No document with that id."},
        )
    return d


@router.get("/documents/{doc_id}/download", response_class=Response)
def download_reference_document(
    doc_id: str, db: Session = Depends(get_db)
) -> Response:
    d = get_doc_or_404(db, doc_id)
    require_consent(db, d.profile_id, "reference_sharing")
    return Response(
        content=d.data,
        media_type=d.content_type,
        headers={"Content-Disposition": f'attachment; filename="{d.filename}"'},
    )


@router.delete("/documents/{doc_id}", status_code=204)
def delete_reference_document(doc_id: str, db: Session = Depends(get_db)) -> None:
    d = get_doc_or_404(db, doc_id)
    db.delete(d)
    db.commit()


# --- reference list parsing ------------------------------------------------------


@router.post(
    "/profiles/{profile_id}/references/parse-list",
    response_model=list[ReferenceOut],
    status_code=201,
)
async def parse_reference_list(
    profile_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)
) -> list[ReferenceOut]:
    """Upload a reference list (PDF/DOCX/TXT); parse names + contacts.
    Every parsed reference starts with permission UNCONFIRMED."""
    profile = get_profile_or_404(db, profile_id)
    require_consent(db, profile.id, "reference_sharing")
    data = await file.read()
    try:
        text = parse_list.extract_text(file.filename or "", data)
    except ValueError as exc:
        raise HTTPException(status_code=415, detail={"code": "UNSUPPORTED_FILE", "message": str(exc)})
    except Exception:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "PARSE_FAILED",
                "message": "Could not read that file. Try a text-based PDF or DOCX.",
            },
        )
    found = parse_list.parse_reference_list(text)
    out = []
    for f in found:
        r = Reference(
            id=str(uuid.uuid4()),
            profile_id=profile.id,
            **f,
        )
        db.add(r)
        out.append(r)
    db.commit()
    for r in out:
        db.refresh(r)
    return [_ref_out(r, db) for r in out]


# --- application integration -----------------------------------------------------


@router.post("/applications/{app_id}/references", response_model=ApplicationOut)
def attach_references(
    app_id: str, payload: AttachReferencesIn, db: Session = Depends(get_db)
) -> ApplicationOut:
    """Select which approved references go with this application.

    Only references that are approved AND permission-confirmed can be
    attached; others are rejected with a reason.
    """
    app = get_app_or_404(db, app_id)
    require_consent(db, app.profile_id, "reference_sharing")

    selected = []
    for rid in payload.reference_ids:
        r = get_ref_or_404(db, rid)
        if r.profile_id != app.profile_id:
            continue
        if not r.approved:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "REFERENCE_NOT_APPROVED",
                    "message": f"'{r.name}' is not approved for sharing.",
                },
            )
        if not r.permission_confirmed:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "PERMISSION_NOT_CONFIRMED",
                    "message": f"You have not confirmed you may share '{r.name}''s details.",
                },
            )
        selected.append(rid)

    app.references_requested = payload.references_requested
    app.selected_reference_ids = json.dumps(selected)
    db.commit()
    db.refresh(app)
    return app_out(db, app)


@router.get("/applications/{app_id}/references/summary")
def reference_summary(app_id: str, db: Session = Depends(get_db)) -> Response:
    """Plain-text reference sheet for attaching to the application."""
    app = get_app_or_404(db, app_id)
    refs = json.loads(app.selected_reference_ids or "[]")
    lines = ["References", "=" * 40, ""]
    for i, rid in enumerate(refs, 1):
        r = db.get(Reference, rid)
        if r is None:
            continue
        lines.append(f"{i}. {r.name}" + (f" - {r.title}" if r.title else ""))
        if r.company:
            lines.append(f"   Company: {r.company}")
        if r.relationship:
            lines.append(f"   Relationship: {r.relationship}")
        if r.phone:
            lines.append(f"   Phone: {r.phone}")
        if r.email:
            lines.append(f"   Email: {r.email}")
        lines.append("")
    lines.append("The candidate confirms they have permission to share these details.")
    return Response(content="\n".join(lines), media_type="text/plain; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="references.txt"'})
