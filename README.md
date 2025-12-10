# Final Project

[![API Service CI](https://github.com/swe-students-fall2025/5-final-js4j/actions/workflows/api_service-ci.yml/badge.svg)](https://github.com/swe-students-fall2025/5-final-js4j/actions/workflows/api_service-ci.yml)
[![ML Service CI](https://github.com/swe-students-fall2025/5-final-js4j/actions/workflows/ml_service-ci.yml/badge.svg)](https://github.com/swe-students-fall2025/5-final-js4j/actions/workflows/ml_service-ci.yml)
[![Linting CI](https://github.com/swe-students-fall2025/5-final-js4j/actions/workflows/lint.yml/badge.svg)](https://github.com/swe-students-fall2025/5-final-js4j/actions/workflows/lint.yml)

### MedQT

AI-powered, symptom-based triage and queue management for modern clinics.
Built as a distributed microservice system with machine-learning prediction, audit logging, and a rich interactive UI.

---

# Docker Images
Service	DockerHub Link
- API	https://hub.docker.com/r/ct04/medqueue-api
- ML Predictor	https://hub.docker.com/r/ct04/medqueue-ml

# Team Members

- Conor Tiernan - https://github.com/ct-04
- Sean Tang - https://github.com/plant445

---

# System Architecture

- MedQueue consists of 3 interconnected microservices:

# API Service (FastAPI)

Hosts patient and doctor dashboards

Implements triage logic

Communicates with the ML predictor

Sends audit events to the Logger

Stores data in MongoDB

# ML Predictor Service

Flask service hosting a trained regression model

Predicts estimated wait times

Used by API for patient ETA calculations

# Mongo DB Service

Mongo DB database hosted by the droplet

---

### Configuring and Running the System (All Platforms)

This project is containerised, so the simplest and recommended way to run everything (API, ML service, MongoDB, seed data) is with Docker Compose.

# 1. Prerequisites

- Install:

Git

Docker

Windows/macOS: install Docker Desktop

Linux: install docker and the Compose plugin (docker compose)

Python 3.11+ (only needed if you want to run services without Docker)

Verify:

git --version
docker --version
docker compose version

# 2. Clone the Repository
git clone https://github.com/swe-students-fall2025/5-final-js4j.git
cd 5-final-js4j

# 3. Create the .env File

sent in private chat with submission


Then edit .env and update any passwords or secrets as described in the section “Secret configuration files (.env and env.example)” below.

# 4. Run the Full System in Development

From the project root:

docker compose up --build


This will start:

MongoDB (with initial collections and seed data from database/init)

API service (FastAPI)

ML service (wait-time predictor)

Once the containers are healthy, visit:

API & web UI (local Dev): http://localhost:8000/

The deployed project is available at:

Production URL: http://104.131.184.246:8000/

### Required GitHub Secrets

The following secrets must be configured in the GitHub repository:

- `DOCKERHUB_USERNAME` – Your DockerHub account username
- `DOCKERHUB_TOKEN` – A DockerHub Personal Access Token with write permission
- `DO_SSH_KEY` – The private key used by CI/CD to deploy to the droplet
- `D0_SSH_HOST` – The IP address of the droplet
- `D0_SSH_USER` – The SSH username (usually "root")
- `D0_SSH_PORT` – Port required

These must be added under:

GitHub → Settings → Secrets and variables → Actions → New Repository Secret


An exercise to put to practice software development teamwork, subsystem communication, containers, deployment, and CI/CD pipelines. See [instructions](./instructions.md) for details.
