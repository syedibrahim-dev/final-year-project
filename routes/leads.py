"""
Lead management routes - CSV upload, scoring, and retrieval.
"""

import csv
import io
from datetime import datetime
from difflib import get_close_matches
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session

from utils.database import get_db
from utils.dependencies import get_current_user
from models.user import User
from models.lead import Lead, AutomatedOutreach
from services.lead_scoring_service import score_leads_batch
from services.outreach_service import process_bulk_outreach
from pydantic import BaseModel
from typing import List, Optional
from fastapi import BackgroundTasks

class AllocationUpdate(BaseModel):
    allocation: str

class BulkOutreachRequest(BaseModel):
    goal: str

router = APIRouter(prefix="/leads", tags=["Leads"])



# ---- Column mapping ----

# Canonical column names the system expects
CANONICAL_COLUMNS = {
    "company_name": ["company_name", "company", "business_name", "org_name", "organization", "account_name"],
    "email": ["email", "email_address", "contact_email", "e-mail", "e_mail"],
    "phone": ["phone", "phone_number", "telephone", "mobile", "contact_phone"],
    "decision_maker_job_title": ["decision_maker_job_title", "job_title", "title", "role", "position", "designation"],
    "industry": ["industry", "sector", "vertical", "business_type"],
    "country": ["country", "nation", "location_country"],
    "city": ["city", "location", "location_city", "town"],
    "employee_count": ["employee_count", "employees", "company_size", "num_employees", "headcount", "team_size"],
    "annual_revenue_range": ["annual_revenue_range", "revenue", "revenue_range", "annual_revenue", "arr"],
    "website": ["website", "url", "web", "company_url", "site"],
}


def build_column_map(csv_headers: list[str]) -> dict:
    """
    Map CSV column headers to our canonical column names using
    exact match, lowercase match, and fuzzy matching.

    Returns: {csv_header: canonical_name} for matched columns.
    """
    mapping = {}
    csv_lower = {h: h.lower().strip().replace(" ", "_") for h in csv_headers}

    # Build flat lookup: alias -> canonical
    alias_lookup = {}
    for canonical, aliases in CANONICAL_COLUMNS.items():
        for alias in aliases:
            alias_lookup[alias] = canonical

    matched_canonicals = set()

    for original_header, normalized in csv_lower.items():
        # Exact alias match
        if normalized in alias_lookup and alias_lookup[normalized] not in matched_canonicals:
            mapping[original_header] = alias_lookup[normalized]
            matched_canonicals.add(alias_lookup[normalized])
            continue

        # Fuzzy match against all known aliases
        all_aliases = list(alias_lookup.keys())
        close = get_close_matches(normalized, all_aliases, n=1, cutoff=0.7)
        if close and alias_lookup[close[0]] not in matched_canonicals:
            mapping[original_header] = alias_lookup[close[0]]
            matched_canonicals.add(alias_lookup[close[0]])

    return mapping


def normalize_employee_count(val: str) -> str:
    """Convert raw numbers or arbitrary strings to our standard buckets."""
    if not val:
        return None
    val = str(val).lower().replace(",", "").replace(" ", "")
    
    # Extract first number if it exists
    import re
    match = re.search(r'\d+', val)
    if not match:
        return "Unknown"
        
    num = int(match.group())
    
    # Special case: check if it's "k" for thousands
    if "k" in val[match.end():match.end()+1]:
        num *= 1000
        
    if num == 0:
        return "Unknown"
    elif num <= 50:
        return "1-50"
    elif num <= 200:
        return "51-200"
    elif num <= 1000:
        return "201-1000"
    else:
        return "1000+"


def normalize_revenue(val: str) -> str:
    """Convert raw numbers or arbitrary strings to our standard buckets."""
    if not val:
        return None
    val = str(val).lower().replace(",", "").replace(" ", "").replace("$", "")
    
    import re
    # Look for patterns like "10m", "5.5b", "500k", or just raw numbers
    match = re.search(r'(\d+(?:\.\d+)?)\s*([kmb]?)', val)
    if not match:
        return "Unknown"
        
    num = float(match.group(1))
    suffix = match.group(2)
    
    # Convert everything to millions for easier comparison
    if suffix == 'k':
        num_m = num / 1000
    elif suffix == 'b':
        num_m = num * 1000
    elif suffix == 'm':
        num_m = num
    else:
        # If no suffix, assume it's raw dollars
        num_m = num / 1000000
        
    if num_m == 0:
        return "Unknown"
    elif num_m < 1:
        return "<$1M"
    elif num_m <= 10:
        return "$1-10M"
    elif num_m <= 50:
        return "$10-50M"
    else:
        return ">$50M"


def parse_csv_to_leads(file_content: str) -> tuple[list[dict], dict, list[str]]:
    """
    Parse a CSV string into a list of lead dicts with mapped column names.

    Returns:
        (leads, column_mapping, warnings)
    """
    warnings = []

    reader = csv.DictReader(io.StringIO(file_content))
    if not reader.fieldnames:
        raise ValueError("CSV file is empty or has no headers")

    column_map = build_column_map(list(reader.fieldnames))

    if "company_name" not in column_map.values():
        # Check if any row has data we can use as company_name
        warnings.append("No 'Company_Name' column found. Leads will use 'Unknown Company'.")

    has_email = "email" in column_map.values()
    has_phone = "phone" in column_map.values()
    if not has_email and not has_phone:
        warnings.append("No 'Email' or 'Phone' column found. Leads will have no contact info.")

    leads = []
    for row_num, row in enumerate(reader, start=2):  # row 1 is header
        lead = {}
        for csv_col, value in row.items():
            canonical = column_map.get(csv_col)
            if canonical:
                val = value.strip() if value else None
                if canonical == "employee_count":
                    val = normalize_employee_count(val)
                elif canonical == "annual_revenue_range":
                    val = normalize_revenue(val)
                lead[canonical] = val

        # Ensure company_name exists
        if not lead.get("company_name"):
            lead["company_name"] = f"Unknown Company (Row {row_num})"

        leads.append(lead)

    if not leads:
        raise ValueError("CSV contains no data rows")

    return leads, column_map, warnings


def send_initial_email(lead_id: int, email: str, company_name: str):
    """
    Placeholder for async email sending via SMTP.
    In production this would use smtplib to send a personalized outreach email.
    """
    print(f"[EMAIL] Would send initial outreach to {email} at {company_name} (lead_id={lead_id})")


# ---- Endpoints ----

@router.post("/columns")
async def analyze_csv_columns(file: UploadFile = File(...)):
    """
    Read the CSV headers and return our suggested column mapping.
    This allows the frontend to show a mapping UI before final upload.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")
        
    try:
        raw = await file.read()
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            content = raw.decode("latin-1")
        except Exception:
            raise HTTPException(status_code=400, detail="Could not decode CSV file.")

    reader = csv.reader(io.StringIO(content))
    try:
        headers = next(reader)
    except StopIteration:
        raise HTTPException(status_code=400, detail="CSV file is empty")
        
    suggested_map = build_column_map(headers)
    
    return {
        "headers": headers,
        "suggested_mapping": suggested_map,
        "canonical_fields": list(CANONICAL_COLUMNS.keys())
    }


@router.post("/upload")
async def upload_leads(
    file: UploadFile = File(...),
    mapping: str = None, # JSON string of user-confirmed mapping
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a CSV of leads, score each with the ML model,
    and save to the database with allocation decisions.
    """
    org_id = current_user.organization_id

    # Validate file type
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported"
        )

    # Read file content
    try:
        raw = await file.read()
        content = raw.decode("utf-8-sig")  # handles BOM
    except UnicodeDecodeError:
        try:
            content = raw.decode("latin-1")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not decode CSV file. Ensure it is UTF-8 or Latin-1 encoded."
            )

    # Parse CSV with the provided manual mapping
    try:
        warnings = []
        reader = csv.DictReader(io.StringIO(content))
        if not reader.fieldnames:
            raise ValueError("CSV file is empty or has no headers")

        import json
        column_map = json.loads(mapping) if mapping else build_column_map(list(reader.fieldnames))

        if "company_name" not in column_map.values():
            warnings.append("No 'Company_Name' column mapped. Leads will use 'Unknown Company'.")

        has_email = "email" in column_map.values()
        has_phone = "phone" in column_map.values()
        if not has_email and not has_phone:
            warnings.append("No 'Email' or 'Phone' column mapped. Leads will have no contact info.")

        leads_data = []
        for row_num, row in enumerate(reader, start=2):
            lead = {}
            for csv_col, value in row.items():
                canonical = column_map.get(csv_col)
                if canonical:
                    val = value.strip() if value else None
                    if canonical == "employee_count":
                        val = normalize_employee_count(val)
                    elif canonical == "annual_revenue_range":
                        val = normalize_revenue(val)
                    lead[canonical] = val

            if not lead.get("company_name"):
                lead["company_name"] = f"Unknown Company (Row {row_num})"
            leads_data.append(lead)

        if not leads_data:
            raise ValueError("CSV contains no data rows")

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Map lead dicts to model feature names for scoring
    feature_map = {
        "decision_maker_job_title": "Decision_Maker_Job_Title",
        "industry": "Industry",
        "country": "Country",
        "city": "City",
        "employee_count": "Employee_Count",
        "annual_revenue_range": "Annual_Revenue_Range",
    }

    scoring_inputs = []
    for lead in leads_data:
        model_input = {}
        for db_col, model_col in feature_map.items():
            model_input[model_col] = lead.get(db_col)
        scoring_inputs.append(model_input)

    # Batch score all leads
    scores = score_leads_batch(scoring_inputs)

    # Build a set of existing leads for duplicate detection (email+company_name)
    existing_leads = db.query(Lead.email, Lead.company_name).filter(
        Lead.organization_id == org_id
    ).all()
    existing_keys = set()
    for e, c in existing_leads:
        key = (str(e or "").strip().lower(), str(c or "").strip().lower())
        existing_keys.add(key)

    # Save to database, skipping duplicates
    saved_leads = []
    skipped = 0
    for lead_data, score in zip(leads_data, scores):
        dup_key = (
            str(lead_data.get("email") or "").strip().lower(),
            str(lead_data.get("company_name") or "").strip().lower(),
        )
        if dup_key in existing_keys:
            skipped += 1
            continue

        existing_keys.add(dup_key)  # prevent intra-batch duplicates too

        db_lead = Lead(
            organization_id=org_id,
            company_name=lead_data.get("company_name", "Unknown"),
            email=lead_data.get("email"),
            phone=lead_data.get("phone"),
            decision_maker_job_title=lead_data.get("decision_maker_job_title"),
            industry=lead_data.get("industry"),
            country=lead_data.get("country"),
            city=lead_data.get("city"),
            employee_count=lead_data.get("employee_count"),
            annual_revenue_range=lead_data.get("annual_revenue_range"),
            website=lead_data.get("website"),
            win_probability=score["win_probability"],
            allocation_decision=score["allocation_decision"],
            status="PENDING",
        )
        db.add(db_lead)
        saved_leads.append((db_lead, lead_data, score))

    db.commit()

    # We no longer auto-queue emails or create AutomatedOutreach rows on upload.
    # This is handled by the Bulk Outreach button in the UI.

    if skipped > 0:
        warnings.append(f"{skipped} duplicate lead(s) skipped (already exist in database)")

    # Build summary (counts from newly added leads only)
    new_scores = [s for (_, _, s) in saved_leads]
    ai_outreach = sum(1 for s in new_scores if s["allocation_decision"] == "AI_OUTREACH")
    manual_review = sum(1 for s in new_scores if s["allocation_decision"] == "MANUAL_REVIEW")
    nurture = sum(1 for s in new_scores if s["allocation_decision"] == "NURTURE_CAMPAIGN")
    avg_score = sum(s["win_probability"] for s in new_scores) / len(new_scores) if new_scores else 0

    return {
        "status": "success",
        "summary": {
            "total_leads": len(leads_data),
            "new_leads": len(saved_leads),
            "skipped_duplicates": skipped,
            "ai_outreach": ai_outreach,
            "manual_review": manual_review,
            "nurture_campaign": nurture,
            "average_win_probability": round(avg_score, 4),
        },
        "column_mapping": column_map,
        "warnings": warnings,
    }


@router.get("/")
def get_leads(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status_filter: str = None,
    sort_by: str = "win_probability",
    limit: int = 100,
    offset: int = 0,
):
    """Get all leads for the current organization, sorted by score."""
    org_id = current_user.organization_id
    query = db.query(Lead).filter(Lead.organization_id == org_id)

    if status_filter:
        query = query.filter(Lead.allocation_decision == status_filter.upper())

    if sort_by == "win_probability":
        query = query.order_by(Lead.win_probability.desc())
    elif sort_by == "created_at":
        query = query.order_by(Lead.created_at.desc())
    else:
        query = query.order_by(Lead.win_probability.desc())

    total = query.count()
    leads = query.offset(offset).limit(limit).all()

    return {
        "total": total,
        "leads": [
            {
                "id": l.id,
                "company_name": l.company_name,
                "email": l.email,
                "phone": l.phone,
                "job_title": l.decision_maker_job_title,
                "industry": l.industry,
                "country": l.country,
                "city": l.city,
                "employee_count": l.employee_count,
                "revenue_range": l.annual_revenue_range,
                "win_probability": l.win_probability,
                "allocation": l.allocation_decision,
                "status": l.status,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in leads
        ],
    }


@router.get("/{lead_id}")
def get_lead_detail(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get detailed info for a single lead including outreach state."""
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == current_user.organization_id
    ).first()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    outreach_data = None
    if lead.outreach:
        outreach_data = {
            "conversation_state": lead.outreach.conversation_state,
            "escalated": lead.outreach.escalated,
            "outcome": lead.outreach.outcome,
            "last_message_at": lead.outreach.last_message_at.isoformat() if lead.outreach.last_message_at else None,
        }

    return {
        "id": lead.id,
        "company_name": lead.company_name,
        "email": lead.email,
        "phone": lead.phone,
        "job_title": lead.decision_maker_job_title,
        "industry": lead.industry,
        "country": lead.country,
        "city": lead.city,
        "employee_count": lead.employee_count,
        "revenue_range": lead.annual_revenue_range,
        "website": lead.website,
        "win_probability": lead.win_probability,
        "allocation": lead.allocation_decision,
        "status": lead.status,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
        "outreach": outreach_data,
    }


@router.patch("/{lead_id}/allocation")
def update_lead_allocation(
    lead_id: int,
    payload: AllocationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually override a lead's allocation decision."""
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == current_user.organization_id
    ).first()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
        
    valid = ["AI_OUTREACH", "MANUAL_REVIEW", "NURTURE_CAMPAIGN"]
    new_alloc = payload.allocation.upper()
    if new_alloc not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid allocation. Must be one of {valid}")
        
    lead.allocation_decision = new_alloc
    
    # Also update the status accordingly
    if new_alloc == "AI_OUTREACH":
        lead.status = "AI_ACTIVE"
    else:
        lead.status = "PENDING"
        
    db.commit()
    
    return {"status": "success", "allocation": lead.allocation_decision, "lead_status": lead.status}


@router.post("/bulk-outreach")
def trigger_bulk_outreach(
    payload: BulkOutreachRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Triggers the AI Outreach generation for all AI_OUTREACH leads
    that have an email and aren't already active.
    """
    leads_to_process = db.query(Lead).filter(
        Lead.organization_id == current_user.organization_id,
        Lead.allocation_decision == "AI_OUTREACH",
        Lead.status == "PENDING",
        Lead.email.isnot(None),
        Lead.email != ""
    ).all()
    
    if not leads_to_process:
        return {"status": "success", "message": "No eligible leads found for outreach.", "count": 0}
        
    lead_ids = [l.id for l in leads_to_process]
    
    # Mark them as DRAFTING immediately
    for l in leads_to_process:
        l.status = "DRAFTING_OUTREACH"
        
    db.commit()
    
    # Queue the background task
    background_tasks.add_task(
        process_bulk_outreach,
        org_id=current_user.organization_id,
        goal=payload.goal,
        lead_ids=lead_ids
    )
    
    return {
        "status": "success", 
        "message": f"Started generating outreach for {len(lead_ids)} leads.", 
        "count": len(lead_ids)
    }


@router.delete("/")
def delete_all_leads(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete all leads for the current organization."""
    org_id = current_user.organization_id
    deleted_count = db.query(Lead).filter(Lead.organization_id == org_id).delete()
    db.commit()
    
    return {"status": "success", "message": f"Deleted {deleted_count} leads"}
