# ICAI Backend

Backend service for the ICAI platform, built with Django and Django REST Framework.

This service manages users, interview sessions, questions, answers, and evaluation results. AI-driven generation and evaluation are delegated to an external interview engine.

## Features

- User registration and authentication (JWT)
- User profile management
- Interview session lifecycle
- Question and answer storage
- Guest and authenticated interview support
- Integration with external interview engine
- Token-based access for guest sessions

## Tech Stack

- Python
- Django
- Django REST Framework
- Simple JWT
- PostgreSQL (recommended)

## Requirements

- Python 3.9+
- pip / virtualenv
- Database (PostgreSQL or SQLite for development)

## Setup

```bash
git clone <repository-url>
cd ICAI-backend-app

python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

pip install -r requirements.txt
python manage.py migrate
```

### (Optional) Create Superuser

```bash
python manage.py createsuperuser
```

### Run the Server

```bash
python manage.py runserver
```

## Configuration

The backend expects an external interview engine to be available.

### Required Environment Variables

- `FASTAPI_BASE_URL=http://127.0.0.1:8001`

Additional limits and defaults can be configured via environment variables.

## Authentication

- **JWT-based authentication** for registered users
- **Guest interview sessions** supported via public token
- Guest token must be provided via `X-Interview-Token` header or `?t=` query param

## API Overview

The API provides endpoints for:

- Authentication (register, login, refresh)
- User profile management
- Interview session creation and listing
- Question generation and answering
- Interview evaluation

API schema and examples are available via the browsable API.

## Development Notes

- Interview sessions may belong to a user or be guest-based
- Guest sessions generate a public access token automatically
- Questions are ordered per session
- Evaluation results are stored per question and per session
- Session status reflects interview progress

## Running Tests

```bash
python manage.py test
```
