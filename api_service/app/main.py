"""Main FastAPI application defining routes, authentication, and lifecycle
for the Medical Queue API.
"""

import html
import re
from contextlib import asynccontextmanager

from bson import ObjectId
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.hash import bcrypt

from .database import get_database, get_mongo_client, close_mongo_client
from .services.queue_service import (
    create_appointment_for_patient,
    recalculate_wait_times_for_waiting_appointments,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan: connect and disconnect MongoDB client."""
    get_mongo_client()
    yield
    close_mongo_client()


api_application = FastAPI(lifespan=lifespan, title="Medical Queue API")
api_application.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@api_application.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Enforce authentication for non-public routes."""
    open_paths = [
        "/login",
        "/register",
        "/register/patient",
        "/register/doctor",
        "/static",
    ]
    if (
        any(request.url.path.startswith(p) for p in open_paths)
        or request.url.path == "/"
    ):
        return await call_next(request)
    if not request.cookies.get("user_id"):
        return RedirectResponse("/login")
    return await call_next(request)


@api_application.get("/", response_class=HTMLResponse)
async def root_redirect(_request: Request):
    """Redirect root URL to login page."""
    return RedirectResponse("/login")


@api_application.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render the login page template."""
    return templates.TemplateResponse("login.html", {"request": request})


@api_application.post("/login")
async def login(request: Request):
    """Process login form and set authentication cookies."""
    form = await request.form()
    email = form.get("email")
    password = form.get("password")
    role = form.get("role")

    db = get_database()
    collection = db["patients"] if role == "patient" else db["doctors"]
    user = await collection.find_one({"email": email})

    if not user or not bcrypt.verify(password, user["password_hash"]):
        return RedirectResponse("/login?error=invalid", status_code=302)

    redirect_url = "/patient/dashboard" if role == "patient" else "/doctor/dashboard"
    response = RedirectResponse(redirect_url, status_code=302)
    response.set_cookie("user_id", str(user["_id"]))
    response.set_cookie("role", role)
    return response


@api_application.get("/register/patient", response_class=HTMLResponse)
async def register_patient_page(request: Request):
    """Render patient registration page."""
    return templates.TemplateResponse("register_patient.html", {"request": request})


@api_application.post("/register/patient")
async def register_patient(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    """Register a new patient and set authentication cookies."""
    db = get_database()
    existing = await db["patients"].find_one({"email": email})
    if existing:
        return HTMLResponse(
            "<h3>Email already registered. Please login.</h3>", status_code=400
        )

    hashed = bcrypt.hash(password)
    patient_doc = {
        "name": name,
        "email": email,
        "password_hash": hashed,
        "symptoms": [],
    }
    patient_id = (await db["patients"].insert_one(patient_doc)).inserted_id

    response = RedirectResponse("/onboarding/symptoms", status_code=302)
    response.set_cookie("user_id", str(patient_id))
    response.set_cookie("role", "patient")
    return response


@api_application.get("/register/doctor", response_class=HTMLResponse)
async def register_doctor_page(request: Request):
    """Render doctor registration page."""
    return templates.TemplateResponse("register_doctor.html", {"request": request})


@api_application.post("/register/doctor")
async def register_doctor(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    """Register a new doctor and set authentication cookies."""
    db = get_database()
    existing = await db["doctors"].find_one({"email": email})
    if existing:
        return HTMLResponse(
            "<h3>Email already registered. Please login.</h3>", status_code=400
        )

    hashed = bcrypt.hash(password)
    doctor_doc = {"name": name, "email": email, "password_hash": hashed}
    doctor_id = (await db["doctors"].insert_one(doctor_doc)).inserted_id

    response = RedirectResponse("/doctor/dashboard", status_code=302)
    response.set_cookie("user_id", str(doctor_id))
    response.set_cookie("role", "doctor")
    return response


@api_application.get("/onboarding/symptoms", response_class=HTMLResponse)
async def symptoms_page(request: Request):
    """Render symptom selection form for patients."""
    return templates.TemplateResponse("patient_onboarding.html", {"request": request})


@api_application.post("/onboarding/symptoms")
async def symptoms_submit(request: Request):
    """Process submitted symptoms and create appointment."""
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
    cleaned_other = (
        html.escape(other)
        if other and re.fullmatch(r"[A-Za-z0-9 ,.'-]{1,80}", other)
        else None
    )
    final_symptoms = symptoms.copy()
    if cleaned_other and "other" not in final_symptoms:
        final_symptoms.append("other")

    db = get_database()
    await db["patients"].update_one(
        {"_id": ObjectId(user_id)}, {"$set": {"symptoms": final_symptoms}}
    )
    await create_appointment_for_patient(
        patient_id=ObjectId(user_id), symptom_names=final_symptoms
    )

    return RedirectResponse("/patient/dashboard", status_code=302)


@api_application.get("/patient/dashboard", response_class=HTMLResponse)
async def patient_dashboard(request: Request):
    """Render patient dashboard with queue and ETA info."""
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/login")

    db = get_database()
    patient = await db["patients"].find_one({"_id": ObjectId(user_id)})
    appointment = await db["appointments"].find_one(
        {"patient_id": ObjectId(user_id), "status": "waiting"}
    )

    queue_number = appointment.get("queue_number") if appointment else None
    eta = (
        int(appointment.get("predicted_wait_minutes"))
        if appointment and appointment.get("predicted_wait_minutes")
        else None
    )

    return templates.TemplateResponse(
        "patient_dashboard.html",
        {
            "request": request,
            "queue_number": queue_number,
            "eta": eta,
            "symptoms": patient.get("symptoms", []) if patient else [],
        },
    )


@api_application.get("/doctor/dashboard", response_class=HTMLResponse)
async def doctor_dashboard(request: Request):
    """Render doctor dashboard showing the current patient queue."""
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/login")

    db = get_database()
    waiting_appointments = (
        await db["appointments"]
        .find({"status": "waiting"})
        .sort("queue_number", 1)
        .to_list(length=1000)
    )

    queue_data = []
    for appt in waiting_appointments:
        patient_doc = await db["patients"].find_one({"_id": appt["patient_id"]})
        queue_data.append(
            {
                "appointment_id": str(appt["_id"]),
                "patient_id": str(appt["patient_id"]),
                "patient_name": patient_doc.get("name") if patient_doc else "Unknown",
                "queue_number": appt.get("queue_number"),
                "eta": (
                    int(appt.get("predicted_wait_minutes"))
                    if appt.get("predicted_wait_minutes")
                    else None
                ),
                "symptoms": appt.get("symptoms", []),
            }
        )

    return templates.TemplateResponse(
        "doctor_dashboard.html", {"request": request, "queue": queue_data}
    )


@api_application.post("/doctor/complete/{appointment_id}")
async def doctor_complete_appointment(appointment_id: str):
    """Mark appointment completed and reorder the queue."""
    db = get_database()
    appointment_object_id = ObjectId(appointment_id)
    appointment_document = await db["appointments"].find_one(
        {"_id": appointment_object_id}
    )
    if not appointment_document:
        return HTMLResponse("Appointment not found", status_code=404)

    await db["appointments"].update_one(
        {"_id": appointment_object_id}, {"$set": {"status": "completed"}}
    )

    queue_number = appointment_document.get("queue_number")
    if queue_number is not None:
        await db["appointments"].update_many(
            {"status": "waiting", "queue_number": {"$gt": queue_number}},
            {"$inc": {"queue_number": -1}},
        )

    # recomputes ETA fter completing of appointment
    await recalculate_wait_times_for_waiting_appointments()

    return RedirectResponse("/doctor/dashboard", status_code=302)


@api_application.get("/doctor/patient/{patient_id}", response_class=HTMLResponse)
async def doctor_view_patient(request: Request, patient_id: str):
    """Show patient details and appointment history to doctor."""
    db = get_database()
    patient_obj_id = ObjectId(patient_id)
    patient = await db["patients"].find_one({"_id": patient_obj_id})
    if not patient:
        return HTMLResponse("Patient not found", status_code=404)

    appointments = (
        await db["appointments"]
        .find({"patient_id": patient_obj_id})
        .sort("queue_number", 1)
        .to_list(length=1000)
    )

    converted_appointments = [
        {
            "id": str(appt["_id"]),
            "status": appt.get("status"),
            "queue_number": appt.get("queue_number"),
            "predicted_wait_minutes": appt.get("predicted_wait_minutes"),
            "symptoms": appt.get("symptoms", []),
        }
        for appt in appointments
    ]

    return templates.TemplateResponse(
        "doctor_patient.html",
        {
            "request": request,
            "patient": {
                "id": str(patient["_id"]),
                "name": patient.get("name"),
                "email": patient.get("email"),
            },
            "appointments": converted_appointments,
        },
    )


@api_application.get("/logout")
async def logout():
    """Clear authentication cookies and redirect to login."""
    response = RedirectResponse("/login")
    response.delete_cookie("user_id")
    response.delete_cookie("role")
    return response
