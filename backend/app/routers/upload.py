import os
import tempfile
from io import StringIO
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.parsers.export_parser import parse_export_zip, parse_cgm_csv
from app.models import GlucoseReading

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


@router.post("/upload/cgm")
async def upload_cgm(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload CGM data from CSV export."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    content = await file.read()
    text = content.decode("utf-8")

    readings = parse_cgm_csv(StringIO(text))

    if not readings:
        raise HTTPException(status_code=400, detail="No glucose measurements found in file")

    # Upsert readings (avoid duplicates by timestamp)
    imported = 0
    for r in readings:
        existing = db.query(GlucoseReading).filter(
            GlucoseReading.timestamp == r["timestamp"]
        ).first()

        if not existing:
            db.add(GlucoseReading(**r))
            imported += 1

    db.commit()

    return {
        "readings_imported": imported,
        "total_in_file": len(readings),
        "source": "csv_import"
    }
