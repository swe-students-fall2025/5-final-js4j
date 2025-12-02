# code for website will go
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.hash import bcrypt
from .database import get_database
from bson import ObjectId


api_application = FastAPI(title="Medical Queue API")

api_application.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")
"""
FastAPI application instance that exposes endpoints for the medical
queue backend.
"""


@api_application.middleware("http")
async def auth_middleware(request: Request, call_next):
    open_paths = ["/login", "/register", "/register/patient", "/register/doctor", "/static"]

    # allow static files + public routes
    if any(request.url.path.startswith(p) for p in open_paths):
        return await call_next(request)

    # allow root page
    if request.url.path == "/":
        return await call_next(request)

    # session check
    if not request.cookies.get("user_id"):
        return RedirectResponse("/login")

    return await call_next(request)

@api_application.get("/", response_class=HTMLResponse)
async def root_redirect():
    return RedirectResponse("/login")

@api_application.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@api_application.post("/login")
async def login(request: Request):
    form = await request.form()
    email = form["email"]
    password = form["password"]
    role = form["role"]

    db = get_database()
    collection = db["patients"] if role == "patient" else db["doctors"]

    user = await collection.find_one({"email": email})
    if not user:
        return RedirectResponse("/login", status_code=302)

    if not bcrypt.verify(password, user["password_hash"]):
        return RedirectResponse("/login", status_code=302)

    # login OK
    response = RedirectResponse(
        "/patient/dashboard" if role == "patient" else "/doctor/dashboard",
        status_code=302
    )
    response.set_cookie("user_id", str(user["_id"]))
    response.set_cookie("role", role)
    return response


@api_application.get("/register/patient", response_class=HTMLResponse)
async def register_patient_page(request: Request):
    return templates.TemplateResponse("register_patient.html", {"request": request})

@api_application.post("/register/patient")
async def register_patient(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    print("PASSWORD RECEIVED:", repr(password))
    db = get_database()
    hashed = bcrypt.hash(password)

    patient_id = (await db["patients"].insert_one({
        "name": name,
        "email": email,
        "password_hash": hashed,
        "symptoms": []
    })).inserted_id

    response = RedirectResponse("/onboarding/symptoms", status_code=302)
    response.set_cookie("user_id", str(patient_id))
    response.set_cookie("role", "patient")
    return response

@api_application.get("/register/doctor", response_class=HTMLResponse)
async def register_doctor_page(request: Request):
    return templates.TemplateResponse("register_doctor.html", {"request": request})

@api_application.post("/register/doctor")
async def register_doctor(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    db = get_database()
    hashed = bcrypt.hash(password)

    doctor_id = (await db["doctors"].insert_one({
        "name": name,
        "email": email,
        "password_hash": hashed
    })).inserted_id

    response = RedirectResponse("/doctor/dashboard", status_code=302)
    response.set_cookie("user_id", str(doctor_id))
    response.set_cookie("role", "doctor")
    return response

@api_application.get("/onboarding/symptoms", response_class=HTMLResponse)
async def symptoms_page(request: Request):
    return templates.TemplateResponse("patient_onboarding.html", {"request": request})

@api_application.post("/onboarding/symptoms")
async def symptoms_submit(request: Request):
    form = await request.form()
    symptoms = form.getlist("symptoms")

    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/login")

    db = get_database()
    await db["patients"].update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"symptoms": symptoms}}
    )

    return RedirectResponse("/patient/dashboard", status_code=302)

@api_application.get("/patient/dashboard", response_class=HTMLResponse)
async def patient_dashboard(request: Request):
    return templates.TemplateResponse("patient_dashboard.html", {"request": request})

@api_application.get("/doctor/dashboard", response_class=HTMLResponse)
async def doctor_dashboard(request: Request):
    return templates.TemplateResponse("doctor_dashboard.html", {"request": request})


#logout route for future logout implementation
@api_application.get("/logout")
async def logout():
    response = RedirectResponse("/login")
    response.delete_cookie("user_id")
    response.delete_cookie("role")
    return response




@api_application.get("/health")
async def health_check():
    """
    Health-check endpoint for uptime monitoring and CI tests.

    Returns
    -------
    dict
        A dictionary containing a simple `"status": "ok"` message.
    """
    return {"status": "ok"}
