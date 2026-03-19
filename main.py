from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from database import init_db
from routers import auth, doctor, admin

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()  
    ]
)
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

app.add_middleware(SessionMiddleware, secret_key="cornea-secret-key-change-in-prod-2024")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(auth.router)
app.include_router(doctor.router)
app.include_router(admin.router)


@app.on_event("startup")
async def startup():
    init_db()


@app.get("/")
async def root(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/login")
    if user["role"] == "admin":
        return RedirectResponse(url="/admin")
    return RedirectResponse(url="/doctor/dashboard")
