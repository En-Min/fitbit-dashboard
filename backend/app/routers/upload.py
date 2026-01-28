import os
import tempfile
from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.parsers.export_parser import parse_export_zip

router = APIRouter(tags=["upload"])


@router.post("/upload")
async def upload_export(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a Fitbit data export ZIP and parse all data into the database."""
    if not file.filename or not file.filename.endswith(".zip"):
        return {"error": "Please upload a ZIP file"}

    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        summary = parse_export_zip(tmp_path, db)
        return {"status": "success", "summary": summary}
    finally:
        os.unlink(tmp_path)
