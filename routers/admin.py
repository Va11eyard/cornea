import io
import csv
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
from database import get_db, hash_password

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="templates")


def require_admin(request: Request):
    user = request.session.get("user")
    if not user or user["role"] != "admin":
        return None
    return user


@router.get("", response_class=HTMLResponse)
async def admin_dashboard(request: Request, status: str = "", search: str = ""):
    user = require_admin(request)
    if not user:
        return RedirectResponse(url="/login")

    conn = get_db()
    query = """
        SELECT r.*, u.full_name as user_full_name, u.username
        FROM requests r
        JOIN users u ON r.user_id = u.id
        WHERE 1=1
    """
    params = []
    if status:
        query += " AND r.status = ?"
        params.append(status)
    if search:
        query += " AND (r.patient_code LIKE ? OR r.clinic LIKE ? OR r.doctor_name LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    query += " ORDER BY r.created_at DESC"
    requests = conn.execute(query, params).fetchall()
    conn.close()

    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "user": user,
        "requests": requests,
        "status_filter": status,
        "search": search,
    })


@router.get("/request/{request_id}", response_class=HTMLResponse)
async def view_request(request: Request, request_id: int):
    user = require_admin(request)
    if not user:
        return RedirectResponse(url="/login")

    conn = get_db()
    req = conn.execute(
        "SELECT r.*, u.full_name as user_full_name FROM requests r JOIN users u ON r.user_id = u.id WHERE r.id = ?",
        (request_id,)
    ).fetchone()
    conn.close()

    if not req:
        return RedirectResponse(url="/admin")

    return templates.TemplateResponse("admin/request_detail.html", {
        "request": request,
        "user": user,
        "req": req,
    })


@router.post("/request/{request_id}/status")
async def update_status(request: Request, request_id: int, status: str = Form(...)):
    user = require_admin(request)
    if not user:
        return RedirectResponse(url="/login")

    conn = get_db()
    conn.execute(
        "UPDATE requests SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, request_id)
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/admin/request/{request_id}?updated=1", status_code=303)


@router.post("/request/{request_id}/delete")
async def delete_request(request: Request, request_id: int):
    user = require_admin(request)
    if not user:
        return RedirectResponse(url="/login")

    conn = get_db()
    conn.execute("DELETE FROM requests WHERE id = ?", (request_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin?deleted=1", status_code=303)


@router.get("/export/excel")
async def export_excel(request: Request):
    user = require_admin(request)
    if not user:
        return RedirectResponse(url="/login")

    conn = get_db()
    rows = conn.execute("""
        SELECT r.id, r.created_at, u.full_name, r.clinic, r.patient_code,
               r.cornea_count, r.min_cell_count, r.max_donor_age, r.max_days_since_death,
               r.amphoterycin_b, r.tissue_processing, r.additional_processing,
               r.optical_diameter, r.needed_before, r.is_urgent, r.comments, r.status,
               r.doctor_name, r.doctor_email, r.doctor_phone
        FROM requests r
        JOIN users u ON r.user_id = u.id
        ORDER BY r.created_at DESC
    """).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow([
        'ID', 'Дата', 'Врач (аккаунт)', 'Клиника', 'Код пациента',
        'Кол-во роговиц', 'Мин. клеток', 'Макс. возраст донора', 'Макс. дней с момента смерти',
        'Амфотерицин B', 'Обработка ткани', 'Доп. обработка', 'Оптич. диаметр (мм)',
        'Ткань нужна до', 'Срочно', 'Комментарии', 'Статус',
        'ФИО врача', 'Email врача', 'Телефон врача'
    ])
    for row in rows:
        r = dict(row)
        writer.writerow([
            r['id'], r['created_at'], r['full_name'], r['clinic'], r['patient_code'],
            r['cornea_count'], r['min_cell_count'], r['max_donor_age'], r['max_days_since_death'],
            r['amphoterycin_b'], r['tissue_processing'], r['additional_processing'],
            r['optical_diameter'], r['needed_before'], 'Да' if r['is_urgent'] else 'Нет',
            r['comments'], r['status'],
            r['doctor_name'], r['doctor_email'], r['doctor_phone']
        ])

    output.seek(0)
    content = '\ufeff' + output.getvalue()  # BOM for Excel

    return StreamingResponse(
        iter([content.encode('utf-8')]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cornea_requests.csv"}
    )


@router.get("/users", response_class=HTMLResponse)
async def users_list(request: Request):
    user = require_admin(request)
    if not user:
        return RedirectResponse(url="/login")

    conn = get_db()
    users = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    conn.close()

    return templates.TemplateResponse("admin/users.html", {
        "request": request,
        "user": user,
        "users": users,
    })


@router.post("/users/create")
async def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    clinic: str = Form(""),
    role: str = Form("doctor"),
):
    user = require_admin(request)
    if not user:
        return RedirectResponse(url="/login")

    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO users (username, password_hash, role, full_name, email, phone, clinic)
            VALUES (?,?,?,?,?,?,?)
        """, (username, hash_password(password), role, full_name, email, phone, clinic))
        conn.commit()
    except Exception:
        pass
    conn.close()
    return RedirectResponse(url="/admin/users?created=1", status_code=303)


@router.post("/users/{user_id}/delete")
async def delete_user(request: Request, user_id: int):
    user = require_admin(request)
    if not user or user_id == user["id"]:
        return RedirectResponse(url="/admin/users")

    conn = get_db()
    conn.execute("DELETE FROM users WHERE id = ? AND role != 'admin'", (user_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/users?deleted=1", status_code=303)


@router.get("/options", response_class=HTMLResponse)
async def options_page(request: Request):
    user = require_admin(request)
    if not user:
        return RedirectResponse(url="/login")

    conn = get_db()
    options = conn.execute("SELECT * FROM tissue_processing_options ORDER BY id").fetchall()
    conn.close()

    return templates.TemplateResponse("admin/options.html", {
        "request": request,
        "user": user,
        "options": options,
    })


@router.post("/options/add")
async def add_option(request: Request, label: str = Form(...)):
    user = require_admin(request)
    if not user:
        return RedirectResponse(url="/login")
    conn = get_db()
    conn.execute("INSERT INTO tissue_processing_options (label) VALUES (?)", (label,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/options", status_code=303)


@router.post("/options/{opt_id}/delete")
async def delete_option(request: Request, opt_id: int):
    user = require_admin(request)
    if not user:
        return RedirectResponse(url="/login")
    conn = get_db()
    conn.execute("DELETE FROM tissue_processing_options WHERE id = ?", (opt_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/options", status_code=303)
