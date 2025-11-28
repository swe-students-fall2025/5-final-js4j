# code for website will go
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from .database import get_database

api_application = FastAPI(title="Medical Queue API")
"""
FastAPI application instance that exposes endpoints for the medical
queue backend.
"""


@api_application.get("/", response_class=HTMLResponse)
async def home_page():
    """
    Render a simple HTML home screen for the backend.

    The home page confirms that the API is running and attempts to list
    existing MongoDB collections as a basic connectivity check.

    Returns
    -------
    str
        HTML content for the home page.
    """
    database_instance = get_database()
    collection_names = await database_instance.list_collection_names()
    return f"""
    <html>
      <head><title>Medical Queue Home</title></head>
      <body>
        <h1>Medical Queue System</h1>
        <p>Backend is running and connected to MongoDB.</p>
        <p>Existing collections: {collection_names}</p>
      </body>
    </html>
    """


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
