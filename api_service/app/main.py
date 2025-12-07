from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.hash import bcrypt
from .database import get_database, get_mongo_client, close_mongo_client
from bson import ObjectId
from contextlib import asynccontextmanager
import html
import re

from .services.queue_service import create_appointment_for_patient

@asynccontextmanager
async def lifespan(app):
    """Manage MongoDB connection across startup and shutdown."""
    get_mongo_client()
    yield
    close_mongo_client()

api_application = FastAPI(lifespan=lifespan, title="Medical Queue API")
api_application.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@api_application.middleware("http")
async def auth_middleware(request: Request, call_next):
    """
    Middleware to enforce that non-public routes can only be accessed
    when a user_id cookie is present. Public routes include login,
    registration, and static files. All other routes redirect to /login
    if the user is not authenticated.
    """
    open_paths = [
        "/login",
        "/register",
        "/register/patient",
        "/register/doctor",
        "/static",
    ]
    if any(request.url.path.startswith(p) for p in open_paths):
        return await call_next(request)
    if request.url.path == "/":
        return await call_next(request)
    if not request.cookies.get("user_id"):
        return RedirectResponse("/login")
    return await call_next(request)


@api_application.get("/", response_class=HTMLResponse)
async def root_redirect():
    """Redirect the root path to the login page."""
    return RedirectResponse("/login")


@api_application.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render the login page."""
    return templates.TemplateResponse("login.html", {"request": request})


@api_application.post("/login")
async def login(request: Request):
    """Process login form submission and set cookies upon success."""
    form = await request.form()
    email = form["email"]
    password = form["password"]
    role = form["role"]
    db = get_database()
    collection = db["patients"] if role == "patient" else db["doctors"]
    user = await collection.find_one({"email": email})
    if not user or not bcrypt.verify(password, user["password_hash"]):
        return RedirectResponse("/login?error=invalid", status_code=302)
    response = RedirectResponse(
        "/patient/dashboard" if role == "patient" else "/doctor/dashboard",
        status_code=302,
    )
    response.set_cookie("user_id", str(user["_id"]))
    response.set_cookie("role", role)
    return response


@api_application.get("/register/patient", response_class=HTMLResponse)
async def register_patient_page(request: Request):
    """Render the patient registration page."""
    return templates.TemplateResponse("register_patient.html", {"request": request})


@api_application.post("/register/patient")
async def register_patient(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    db = get_database()
    existing = await db["patients"].find_one({"email": email})
    if existing:
        return HTMLResponse("<h3>Email already registered. Please login.</h3>", status_code=400)
    hashed = bcrypt.hash(password)
    patient_id = (await db["patients"].insert_one({"name": name, "email": email, "password_hash": hashed, "symptoms": []})).inserted_id
    response = RedirectResponse("/onboarding/symptoms", status_code=302)
    response.set_cookie("user_id", str(patient_id))
    response.set_cookie("role", "patient")
    return response


@api_application.get("/register/doctor", response_class=HTMLResponse)
async def register_doctor_page(request: Request):
    """Render the doctor registration page."""
    return templates.TemplateResponse("register_doctor.html", {"request": request})


@api_application.post("/register/doctor")
async def register_doctor(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    db = get_database()
    existing = await db["doctors"].find_one({"email": email})
    if existing:
        return HTMLResponse("<h3>Email already registered. Please login.</h3>", status_code=400)
    hashed = bcrypt.hash(password)
    doctor_id = (await db["doctors"].insert_one({"name": name, "email": email, "password_hash": hashed})).inserted_id
    response = RedirectResponse("/doctor/dashboard", status_code=302)
    response.set_cookie("user_id", str(doctor_id))
    response.set_cookie("role", "doctor")
    return response


@api_application.get("/onboarding/symptoms", response_class=HTMLResponse)
async def symptoms_page(request: Request):
    """Render the symptom questionnaire page for patients."""
    return templates.TemplateResponse("patient_onboarding.html", {"request": request})


@api_application.post("/onboarding/symptoms")
async def symptoms_submit(request: Request):
    """Process symptom selection form and create an appointment."""
    form = await request.form()
    symptoms = form.getlist("symptoms")
    other = form.get("other_symptom", "").strip()
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/login")
    allowed = {
        "fever",
        "cough",
        "fatigue",
        "nausea",
        "headache",
        "sore_throat",
        "shortness_of_breath",
        "chest_pain",
        "congestion",
        "vomiting",
        "diarrhea",
        "other",
    }
    symptoms = [s for s in symptoms if s in allowed]
    cleaned_other = None
    if other:
        safe_other = html.escape(other)
        if re.fullmatch(r"[A-Za-z0-9 ,.'-]{1,80}", other):
            cleaned_other = safe_other
    final_symptoms = symptoms.copy()
    if cleaned_other:
        if "other" not in final_symptoms:
            final_symptoms.append("other")
    db = get_database()
    await db["patients"].update_one({"_id": ObjectId(user_id)}, {"$set": {"symptoms": final_symptoms}})
    # call the queue service to create appointment and compute wait time
    await create_appointment_for_patient(patient_id=ObjectId(user_id), symptom_names=final_symptoms)
    return RedirectResponse("/patient/dashboard", status_code=302)


@api_application.get("/patient/dashboard", response_class=HTMLResponse)
async def patient_dashboard(request: Request):
    """Display queue position and wait time for the logged-in patient."""
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/login")
    db = get_database()
    patient = await db["patients"].find_one({"_id": ObjectId(user_id)})
    appointment = await db["appointments"].find_one({"patient_id": ObjectId(user_id), "status": "waiting"})
    queue_number = None
    eta = None
    if appointment:
        queue_number = appointment.get("queue_number")
        predicted_wait_minutes = appointment.get("predicted_wait_minutes")
        if predicted_wait_minutes is not None:
            eta = int(predicted_wait_minutes)
    context = {
        "request": request,
        "queue_number": queue_number,
        "eta": eta,
        "symptoms": patient.get("symptoms", []) if patient else [],
    }
    return templates.TemplateResponse("patient_dashboard.html", context)


@api_application.get("/doctor/dashboard", response_class=HTMLResponse)
async def doctor_dashboard(request: Request):
    """Render a dashboard for doctors showing the current queue."""
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/login")
    db = get_database()
    waiting_appointments = await db["appointments"].find({"status": "waiting"}).sort("queue_number", 1).to_list(length=1000)
    queue_data = []
    for appt in waiting_appointments:
        patient_doc = await db["patients"].find_one({"_id": appt["patient_id"]})
        queue_data.append({
            "appointment_id": str(appt["_id"]),
            "patient_id": str(appt["patient_id"]),
            "patient_name": patient_doc.get("name") if patient_doc else "Unknown",
            "queue_number": appt.get("queue_number"),
            "eta": int(appt.get("predicted_wait_minutes")) if appt.get("predicted_wait_minutes") is not None else None,
            "symptoms": appt.get("symptoms", []),
        })
    return templates.TemplateResponse("doctor_dashboard.html", {"request": request, "queue": queue_data})


@api_application.post("/doctor/complete/{appointment_id}")
async def doctor_complete_appointment(appointment_id: str):
    """Mark an appointment as completed and update the queue."""
    db = get_database()
    appt_id = ObjectId(appointment_id)
    appt = await db["appointments"].find_one({"_id": appt_id})
    if appt is None:
        return HTMLResponse("Appointment not found", status_code=404)
    await db["appointments"].update_one({"_id": appt_id}, {"$set": {"status": "completed"}})
    queue_num = appt.get("queue_number")
    if queue_num is not None:
        await db["appointments"].update_many({"status": "waiting", "queue_number": {"$gt": queue_num}}, {"$inc": {"queue_number": -1}})
    return RedirectResponse("/doctor/dashboard", status_code=302)


@api_application.get("/doctor/patient/{patient_id}", response_class=HTMLResponse)
async def doctor_view_patient(request: Request, patient_id: str):
    """Show a patient's profile and appointment history to the doctor."""
    db = get_database()
    patient_obj_id = ObjectId(patient_id)
    patient = await db["patients"].find_one({"_id": patient_obj_id})
    if patient is None:
        return HTMLResponse("Patient not found", status_code=404)
    appointments = await db["appointments"].find({"patient_id": patient_obj_id}).sort("queue_number", 1).to_list(length=1000)
    converted_appointments = []
    for appt in appointments:
        converted_appointments.append({
            "id": str(appt["_id"]),
            "status": appt.get("status"),
            "queue_number": appt.get("queue_number"),
            "predicted_wait_minutes": appt.get("predicted_wait_minutes"),
            "symptoms": appt.get("symptoms", []),
        })
    return templates.TemplateResponse("doctor_patient.html", {
        "request": request,
        "patient": {
            "id": str(patient["_id"]),
            "name": patient.get("name"),
            "email": patient.get("email"),
        },
        "appointments": converted_appointments,
    })


@api_application.get("/logout")
async def logout():
    """Log the user out by clearing cookies."""
    response = RedirectResponse("/login")
    response.delete_cookie("user_id")
    response.delete_cookie("role")
    return response
