from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
from database import get_db
from datetime import date
from phone_validation import normalize_kz_ru_phone

router = APIRouter(prefix="/doctor")
templates = Jinja2Templates(directory="templates")


def require_doctor(request: Request):
    user = request.session.get("user")
    if not user or user["role"] not in ("doctor", "admin"):
        return None
    return user


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = require_doctor(request)
    if not user:
        return RedirectResponse(url="/login")

    conn = get_db()
    requests = conn.execute(
        "SELECT * FROM requests WHERE user_id = ? ORDER BY created_at DESC",
        (user["id"],)
    ).fetchall()
    conn.close()

    return templates.TemplateResponse("doctor/dashboard.html", {
        "request": request,
        "user": user,
        "requests": requests,
    })


@router.get("/new-request", response_class=HTMLResponse)
async def new_request_page(request: Request):
    user = require_doctor(request)
    if not user:
        return RedirectResponse(url="/login")

    conn = get_db()
    processing_options = conn.execute(
        "SELECT * FROM tissue_processing_options WHERE is_active = 1"
    ).fetchall()
    conn.close()

    return templates.TemplateResponse("doctor/request_form.html", {
        "request": request,
        "user": user,
        "processing_options": processing_options,
        "today": date.today().isoformat(),
        "error": None,
        "form_data": {},
    })


@router.post("/new-request", response_class=HTMLResponse)
async def create_request(
    request: Request,
    patient_code: str = Form(""),
    clinic: str = Form(""),
    doctor_name: str = Form(""),
    doctor_email: str = Form(""),
    doctor_phone: str = Form(""),
    cornea_count: int = Form(...),
    min_cell_count: int = Form(2000),
    max_donor_age: Optional[int] = Form(None),
    max_days_since_death: Optional[int] = Form(None),
    amphoterycin_b: str = Form("Нет"),
    tissue_processing: str = Form(""),
    additional_processing: str = Form(""),
    optical_diameter: Optional[float] = Form(None),
    needed_before: str = Form(""),
    is_urgent: int = Form(0),
    comments: str = Form(""),
):
    user = require_doctor(request)
    if not user:
        return RedirectResponse(url="/login")

    conn = get_db()
    processing_options = conn.execute(
        "SELECT * FROM tissue_processing_options WHERE is_active = 1"
    ).fetchall()

    form_data = {
        "patient_code": patient_code, "clinic": clinic, "doctor_name": doctor_name,
        "doctor_email": doctor_email, "doctor_phone": doctor_phone,
        "cornea_count": cornea_count, "min_cell_count": min_cell_count,
        "max_donor_age": max_donor_age, "max_days_since_death": max_days_since_death,
        "amphoterycin_b": amphoterycin_b, "tissue_processing": tissue_processing,
        "additional_processing": additional_processing, "optical_diameter": optical_diameter,
        "needed_before": needed_before, "is_urgent": is_urgent, "comments": comments,
    }

    errors = []
    if cornea_count <= 0:
        errors.append("Количество роговиц должно быть больше 0")
    if min_cell_count < 2000:
        errors.append("Минимальное количество клеток не может быть меньше 2000")

    doctor_phone_db, phone_err = normalize_kz_ru_phone(doctor_phone)
    if phone_err:
        errors.append(phone_err)
    if optical_diameter is not None and optical_diameter < 6.0:
        errors.append("Оптически ясный диаметр не может быть меньше 6 мм")
    if needed_before and not is_urgent:
        try:
            op_date = date.fromisoformat(needed_before)
            if op_date < date.today():
                errors.append("Дата операции не может быть в прошлом")
        except ValueError:
            errors.append("Некорректный формат даты операции")

    if errors:
        conn.close()
        return templates.TemplateResponse("doctor/request_form.html", {
            "request": request,
            "user": user,
            "processing_options": processing_options,
            "today": date.today().isoformat(),
            "error": "; ".join(errors),
            "form_data": form_data,
        })

    conn.execute("""
        INSERT INTO requests (
            user_id, patient_code, clinic, doctor_name, doctor_email, doctor_phone,
            cornea_count, min_cell_count, max_donor_age, max_days_since_death,
            amphoterycin_b, tissue_processing, additional_processing, optical_diameter,
            needed_before, is_urgent, comments
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        user["id"], patient_code, clinic, doctor_name, doctor_email, doctor_phone_db,
        cornea_count, min_cell_count, max_donor_age, max_days_since_death,
        amphoterycin_b, tissue_processing, additional_processing, optical_diameter,
        needed_before if needed_before else None, is_urgent, comments
    ))
    conn.commit()
    conn.close()

    return RedirectResponse(url="/doctor/dashboard?success=1", status_code=303)


@router.get("/request/{request_id}", response_class=HTMLResponse)
async def view_request(request: Request, request_id: int):
    user = require_doctor(request)
    if not user:
        return RedirectResponse(url="/login")

    conn = get_db()
    req = conn.execute(
        "SELECT * FROM requests WHERE id = ? AND user_id = ?",
        (request_id, user["id"])
    ).fetchone()
    conn.close()

    if not req:
        return RedirectResponse(url="/doctor/dashboard")

    return templates.TemplateResponse("doctor/request_detail.html", {
        "request": request,
        "user": user,
        "req": req,
    })
