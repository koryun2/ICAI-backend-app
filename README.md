# ICAI-backend-app

ICAI Backend App built with Django

# ICAI-backend-app

ICAI Backend App built with Django.

---

## Overview

This project is a backend application for the ICAI system, built using Django and Django REST Framework (DRF). It provides user authentication, profile management, and other API endpoints for the ICAI system.

---

## Requirements

### Python Version

- Python 3.9 or higher

### Django Version

- Django 4.2 or higher

### Additional Dependencies

- Django REST Framework
- Django REST Framework Simple JWT

---

## Installation

Follow these steps to set up the project on your local machine:

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd ICAI-backend-app## Requirements
   ```

### Python Version

- Python 3.9 or higher

### Django Version

- Django 4.2 or higher

### Additional Dependencies

- Django REST Framework
- Django REST Framework Simple JWT

---

## Installation

Follow these steps to set up the project on your local machine:

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd ICAI-backend-app
   ```
2. **Set Up a Virtual Environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```
4. **Apply Migrations**
   ```bash
   python manage.py migrate
   ```
5. **Create a Superuser (Optional)**
   ```bash
   python manage.py createsuperuser
   ```

## API Endpoints

- **Register**: `/api/register/`  
  Allows new users to register.  
  **Method**: POST  
  **Request Body**:

  ```json
  {
    "email": "user@example.com",
    "password": "password123"
  }
  ```

- **Login**: `/api/token/`  
  Allows users to log in and retrieve access and refresh tokens.  
  **Method**: POST  
  **Request Body**:

  ```json
  {
    "email": "user@example.com",
    "password": "password123"
  }
  ```

- **User Profile**: `/api/me/`  
  Allows authenticated users to retrieve or update their profile.  
  **Methods**: GET, PUT, PATCH

---

## Build and Deployment

### Collect Static Files

Before deploying, collect static files:

```bash
python manage.py collectstatic
```

### Deployment

You can deploy this project using any WSGI-compatible server (e.g., Gunicorn, uWSGI) or a platform like Heroku, AWS, or Docker.

---

## Testing

To run tests:

```bash
python manage.py test
```
