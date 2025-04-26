# LLM Interviewer System 🤖💼

## Overview ✨

LLM Interviewer is a web application designed to streamline the technical interview process. It leverages Large Language Models (LLMs), specifically Google Gemini, to dynamically generate relevant interview questions based on job roles and required technical skills. The system supports multiple user roles (Candidate, HR, Admin) with distinct functionalities for each.

## Features ✅

### 1. 👤 Role-Based Access Control
Distinct interfaces and permissions for Candidates, HR personnel, and Administrators.

### 2. ❓ Dynamic Question Generation
Utilizes Google Gemini API to generate technical interview questions tailored to specific roles and tech stacks. Includes fallback to default questions if the LLM service fails.

### 3. 🗓️ Interview Scheduling (HR)
HR users can schedule interviews for candidates, specifying the role and tech stack.

### 4. 📝 Interview Conduction (Candidate)
Candidates can take scheduled interviews, answering questions sequentially.

### 5. 📤 Response Submission
Candidates submit their answers through the interface.

### 6. 📊 Result Viewing (HR/Admin)
HR and Admin users can view interview results (placeholder scoring/feedback logic currently).

### 7. 📄 Resume Upload (Candidate)
Candidates can upload their resumes.

### 8. 🔑 Authentication
Secure user registration and login using JWT (JSON Web Tokens).

### 9. ⚙️ Admin Management (Partial)
Includes infrastructure for admin users and potential future system management features.

## Tech Stack 💻

### Backend:
- Framework: FastAPI 🐍
- Language: Python 3
- Database: MongoDB 💾
- ODM/Driver: Motor (Async)
- Authentication: JWT (python-jose)
- LLM Integration: Google Gemini API 🧠
- Validation: Pydantic

### Frontend:
- Framework/Library: React ⚛️
- Build Tool: Vite ⚡
- Styling: Tailwind CSS 🍃
- API Client: Axios

### Containerization:
- Docker, Docker Compose 🐳


## Prerequisites 🛠️

1. Node.js and npm 
2. Python 3.9+ and pip
3. Docker and Docker Compose
4. Access to Google Gemini API (API Key)
5. MongoDB instance (local or cloud)

## Setup & Installation ⚙️

### 1. Clone the Repository:
```bash
git clone <repository-url>
cd LLM_interviewer
```

### 2. Backend Setup (Server) 🛠:

#### 2.1. Navigate to the server directory:
```bash
cd server
```

#### 2.2. Environment Variables (.env) 🧪:
Create a .env file and configure it like this:
```
# MongoDB Connection
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB=llm_interview_db

# JWT Configuration
JWT_SECRET_KEY=your_strong_secret_key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Google Gemini API
GEMINI_API_KEY=your_google_gemini_api_key

# Optional: Default Admin Seeding
DEFAULT_ADMIN_EMAIL=admin@example.com
DEFAULT_ADMIN_USERNAME=adminuser
DEFAULT_ADMIN_PASSWORD=your_admin_password
```

#### 2.3. Virtual Environment Setup (Python) 🐍:
Create and activate a virtual environment:
```bash
python -m venv venv

# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

#### 2.4. Install Dependencies 📦:
```bash
pip install -r requirements.txt
```

#### 2.5. Run the Server 🚀:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The server will start 🚀, connect to MongoDB, and seed the default admin user if configured and not already present.

### 3. Frontend Setup (Client):

#### 3.1. Navigate to Client:
```bash
cd ../client # From the server directory, or `cd client` from root
```

#### 3.2. Create Environment File:
Create a .env file in the client directory:
```
VITE_API_BASE_URL=http://localhost:8000 # URL of your running backend
```

#### 3.3. Install Dependencies:
```bash
npm install # or yarn install
```

#### 3.4. Run Client (Development):
```bash
npm run dev # or yarn dev
```

The client development server will start 🚀, typically on port 3000 or 5173 (check console output).

### 4. Docker Setup (Alternative) 🐳:

#### 4.1. Ensure Docker and Docker Compose are running.
#### 4.2. Create the .env file inside the server directory as described in step 2.2.
#### 4.3. From the LLM_interviewer/server directory, run:
```bash
docker-compose up --build
```

This will build the backend image, start the backend service, and start a MongoDB container. The client needs to be run separately using the steps in section 3.

## Usage 👉

1. Open your browser and navigate to the client URL (e.g., http://localhost:5173).
2. Register a new user (Candidate or HR) or log in 🖱️.
3. HR Users: Navigate to the HR dashboard to schedule interviews for candidates.
4. Candidate Users: Navigate to the Candidate dashboard to view scheduled interviews, upload a resume, and take interviews.
5. Admin Users: Access the Admin dashboard (currently placeholder) for potential future user/system management.

## API Documentation 📚

When the backend server is running, automatic interactive API documentation is available at:

1. Swagger UI: http://localhost:8000/docs 🔗
2. ReDoc: http://localhost:8000/redoc
