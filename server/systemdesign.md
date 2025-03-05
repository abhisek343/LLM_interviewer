# LLM Interviewer Backend System Design

## 1. Introduction

### 1.1. Project Purpose
The LLM Interviewer backend is a server-side application built with FastAPI and Python. Its primary purpose is to provide the necessary API endpoints and business logic to support a React-based frontend application for managing technical interviews, candidate evaluation, and HR processes, leveraging Google's Gemini LLM for AI-driven tasks. The system aims to automate and enhance various stages of the recruitment process, from candidate sourcing and initial screening (via resume analysis) to dynamic interview question generation and AI-assisted evaluation.

### 1.2. Scope
This document provides an extensive and detailed system design for the LLM Interviewer backend. It covers the architecture, data models, API specifications, service logic, security measures, deployment considerations, testing strategies, and operational aspects. The focus is exclusively on the backend components and their interactions with the database and external services. The design and implementation of the frontend application are outside the scope of this document.

### 1.3. Goals and Key Features
The primary goals of the LLM Interviewer backend are to be robust, scalable, secure, and maintainable while providing the following key features:

*   **Role-Based Access Control (RBAC):** Implement a granular permission system to differentiate functionalities and data access for three distinct user roles: Candidates, HR Personnel, and Administrators.
*   **Comprehensive User Management:** Provide secure mechanisms for user registration (self-service for Candidates and HR, potentially admin-created for Admins), authentication using industry-standard JWTs, and detailed user profile management including role-specific attributes.
*   **Seamless LLM Integration:** Integrate deeply with the Google Gemini API to dynamically generate relevant and varied interview questions based on specific job roles, descriptions, and candidate profiles. Additionally, leverage the LLM for AI-assisted evaluation of candidate responses, providing scores and feedback.
*   **Structured HR-Admin Workflow:** Define and manage a clear workflow for mapping HR personnel to supervising Administrators, enabling oversight and management of the HR team's activities. This includes application and request processes with acceptance/rejection flows.
*   **End-to-End Candidate Lifecycle Management:** Support the entire candidate journey within the system, from initial sourcing and searching (based on profile data and resume analysis) to invitation, assignment to an HR representative, interview scheduling, conduction, and final evaluation.
*   **Robust Resume Handling and Analysis:** Allow candidates and HR personnel to upload resumes in common formats (PDF, DOCX). Implement automated parsing to extract raw text and perform structured analysis using NLP techniques to identify key skills, estimate years of experience, and potentially extract work history and education.
*   **Streamlined Interview Process Management:** Facilitate the scheduling of interviews by assigned HR personnel (or Admins). Manage the interview session state, deliver generated questions to candidates, record and store candidate responses, and provide tools for both manual and AI-assisted evaluation.
*   **Integrated Messaging System:** Provide a basic internal messaging system to enable communication between users, primarily for HR personnel to send interview invitations or other relevant messages to candidates.
*   **Administrative Oversight:** Equip Administrators with tools to manage all users (excluding other Admins), view system-wide statistics, manage HR-Admin mappings, and oversee the candidate pipeline.

### 1.4. Non-Goals
The following functionalities and aspects are explicitly outside the scope of this backend system design document:

*   Detailed design or implementation of the frontend (React) application.
*   Real-time communication features such as video conferencing, audio calls, or live chat for conducting interviews. The focus is on an asynchronous, question-and-answer based interview format leveraging the LLM.
*   Development of highly advanced, complex AI-driven candidate ranking algorithms beyond the initial search and basic relevance scoring based on extracted resume data. While planned for future iterations, the current scope includes basic filtering and sorting.
*   Implementation of billing, subscription management, or payment processing functionalities.
*   Integration with external HRIS (Human Resources Information Systems) or ATS (Applicant Tracking Systems) for candidate data synchronization (though the API is designed to potentially support this in the future).
*   Advanced reporting and analytics dashboards beyond the basic statistics provided to administrators.

### 1.5. Target Audience
This document is intended for a broad technical audience involved with the LLM Interviewer project, including:

*   **Backend Developers:** To understand the architecture, component design, service logic, and implementation details.
*   **Frontend Developers:** To understand the available API endpoints, request/response formats, and interaction patterns.
*   **Software Architects:** To review the overall system structure, design patterns, and technology choices.
*   **DevOps Engineers:** To understand the deployment strategy, infrastructure requirements, monitoring, and logging setup.
*   **Quality Assurance (QA) Engineers:** To understand the system's functionality and design test cases.
*   **Technical Project Managers:** To understand the scope, features, and technical complexities of the backend.

### 1.6. Document Conventions
This document adheres to the following conventions:

*   Markdown format is used for structure and readability.
*   Code examples and snippets are provided in Python or JSON format within code blocks (` ```python `, ` ```json `).
*   API endpoints are described using their HTTP method (GET, POST, PUT, DELETE), path, and relevant details like request/response schemas and status codes.
*   Key terms are defined in the Glossary (Section 14).
*   Internal components and services are referred to using their module or class names (e.g., `GeminiService`, `app/api/routes/auth.py`).

## 2. System Architecture

### 2.1. High-Level Overview & Diagram
The LLM Interviewer system follows a client-server architecture. The frontend, a single-page application (SPA) built with React, interacts with the backend API. The backend, implemented using FastAPI, serves as the central hub, orchestrating interactions between the frontend, the MongoDB database for data persistence, and the Google Gemini API for AI capabilities.

```mermaid
graph TD
    A[Frontend (React)] -->|HTTP Requests| B(FastAPI Backend)
    B -->|MongoDB Driver (Motor)| C[MongoDB Database]
    B -->|Google Gemini SDK| D[Google Gemini API]
    B -->|File I/O (aiofiles)| E[File Storage (Disk)]

    subgraph FastAPI Backend
        B1[API Layer<br>app/api/routes] --> B2(Service Layer<br>app/services)
        B2 --> B3[Data Access Layer<br>app/db]
        B2 --> D
        B2 --> E
        B1 --> B4[Core Layer<br>app/core]
        B2 --> B4
    end

    C -->|Data Storage| B3
    E -->|File Storage| B2
```

**Explanation of Diagram:**

*   **Frontend (React):** The user interface where users (Candidates, HR, Admins) interact with the system. It sends HTTP requests to the FastAPI backend.
*   **FastAPI Backend:** The core application logic. It receives requests from the frontend, processes them, interacts with the database and external services, and sends responses back to the frontend.
*   **MongoDB Database:** The primary data store for all application data (users, interviews, messages, requests).
*   **Google Gemini API:** An external service providing LLM capabilities for question generation and answer evaluation.
*   **File Storage (Disk):** The server's local file system used for storing uploaded files, specifically resumes.
*   **API Layer:** The entry point for incoming requests, handling routing, request validation, and calling the appropriate service logic.
*   **Service Layer:** Contains the main business logic and orchestrates interactions between other layers and external services.
*   **Data Access Layer:** Provides an abstraction for database operations, handling connections and queries.
*   **Core Layer:** Contains cross-cutting concerns like configuration, security utilities, and dependencies.

### 2.2. Architectural Style
The backend employs a **Layered Architecture**, promoting separation of concerns and modularity.

*   **Presentation Layer (API Layer):**
    *   Handles HTTP requests and responses.
    *   Uses FastAPI routers (`app/api/routes/`).
    *   Performs input validation using Pydantic schemas (`app/schemas/`).
    *   Enforces authentication and authorization using dependencies (`app/core/security.py`).
    *   Translates incoming requests into calls to the Service Layer.
    *   Formats responses from the Service Layer into appropriate HTTP responses.
*   **Business Logic Layer (Service Layer):**
    *   Contains the core business rules and workflows (`app/services/`).
    *   Orchestrates operations involving multiple data access or external service calls.
    *   Encapsulates complex logic (e.g., HR-Admin mapping flow, resume analysis process, interview state transitions).
    *   Should be independent of the API layer (not directly handle HTTP specifics).
*   **Data Access Layer:**
    *   Manages interactions with the database (`app/db/`).
    *   Uses Motor for asynchronous MongoDB operations.
    *   Provides methods for CRUD operations on collections.
    *   Abstracts the database technology from the Service Layer.
*   **Cross-Cutting Concerns (Core Layer):**
    *   Handles functionalities that span across multiple layers.
    *   Configuration loading (`app/core/config.py`).
    *   Security utilities (password hashing, JWT handling in `app/core/security.py`).
    *   Dependency Injection setup.

This layered approach enhances maintainability, testability, and allows for potential replacement of individual layers (e.g., swapping the database or LLM provider) with minimal impact on others.

### 2.3. Technology Stack
The backend is built using the following technologies:

*   **Programming Language:** Python 3.9+ - Chosen for its readability, extensive libraries, and strong support for asynchronous programming.
*   **Web Framework:** FastAPI - Selected for its high performance (comparable to Node.js and Go), automatic interactive API documentation (Swagger UI, ReDoc), and strong support for asynchronous operations and Pydantic for data validation.
*   **ASGI Server:** Uvicorn - A lightning-fast ASGI server, recommended for running FastAPI applications in production.
*   **Database:** MongoDB - A flexible, scalable NoSQL document database suitable for the application's evolving data structures.
*   **ODM/Driver:** Motor - The official asynchronous Python driver for MongoDB, essential for non-blocking database operations with FastAPI.
*   **Data Validation:** Pydantic - Provides data validation, serialization, and settings management using Python type hints, ensuring data integrity at the application boundaries.
*   **Authentication:** JWT (JSON Web Tokens) - A standard for secure information exchange. Implemented using `python-jose` for token handling and `passlib` with `bcrypt` for secure password hashing.
*   **LLM Integration:** Google Gemini API - Accessed via the `google-generativeai` Python SDK for generating interview questions and evaluating answers.
*   **File Parsing:** `pypdf` and `python-docx` - Libraries used by the Resume Parser service to extract text content from PDF and DOCX files respectively.
*   **NLP (Resume Analysis):** `spaCy` and `python-dateutil` - Libraries used by the Resume Analyzer service for tasks like skill extraction (Named Entity Recognition, keyword matching) and estimating years of experience from text.
*   **Asynchronous File Handling:** `aiofiles` - Enables asynchronous reading and writing of files, preventing blocking during file uploads.
*   **Testing:** Pytest - A widely used Python testing framework. `pytest-asyncio` is used for testing asynchronous code, and `httpx` (via FastAPI's `TestClient`) for making requests to the test application instance.
*   **Containerization (Optional but Recommended):** Docker and Docker Compose - For packaging the application and its dependencies into portable containers, simplifying deployment and ensuring consistency across environments.

### 2.4. Component Breakdown
The backend system is composed of several interconnected components:

*   **`app.main`:** The main application entry point. Initializes the FastAPI app, includes routers, sets up middleware (like CORS), and handles application lifespan events (e.g., connecting/disconnecting from the database).
*   **`app.core.config`:** Manages application configuration by loading settings from environment variables using Pydantic Settings. This includes sensitive information like database URLs, JWT secrets, and API keys.
*   **`app.core.security`:** Provides security-related utilities, including password hashing and verification using `bcrypt`, and JWT token creation, encoding, decoding, and validation using `python-jose`. It also contains FastAPI dependencies for authentication and role-based authorization.
*   **`app.db.mongodb`:** Contains the `MongoDBManager` class responsible for establishing and managing the asynchronous connection to the MongoDB database using Motor. It provides methods to get the database instance and close the connection.
*   **`app.db.seed_data` / `app.db.seed_default_questions`:** Scripts or modules for seeding initial data into the database, such as a default administrator user or a set of fallback interview questions.
*   **`app.models`:** Defines Pydantic models that represent the structure of data stored in the MongoDB collections. These models are used for data validation and serialization when interacting with the database. Examples include `User`, `HRMappingRequest`, `Interview`, `Message`.
*   **`app.schemas`:** Defines Pydantic models used for validating incoming request bodies, defining response structures, and specifying query/path parameters for the API endpoints. These schemas ensure data conforms to expected formats at the API boundary. Examples include `UserCreate`, `UserOut`, `Token`, `InterviewCreate`, `InterviewOut`, `RankedCandidate`, `RankedHR`.
*   **`app.services`:** Contains the business logic services. Each service focuses on a specific domain or functionality:
    *   `gemini_service.py`: Handles all interactions with the Google Gemini API.
    *   `invitation_service.py`: Manages the HR-Admin mapping request/application workflow.
    *   `resume_parser.py`: Extracts text from resume files.
    *   `resume_analyzer_service.py`: Analyzes resume text to extract skills and estimate experience.
    *   `search_service.py`: Implements search and ranking logic for candidates and HR profiles.
    *   *(Potentially other services for more complex logic)*
*   **`app.api.routes`:** Contains FastAPI routers, organized by functional area (e.g., `admin.py`, `auth.py`, `candidates.py`, `hr.py`, `interview.py`). These modules define the API endpoints, handle request parsing, call the appropriate service methods, and return responses. They utilize dependencies from `app.core.security` for authentication and authorization.
*   **`tests`:** Directory containing unit and integration tests for the backend components.
*   **`uploads`:** Directory on the server's file system for storing uploaded files (resumes). Subdirectories (`resumes`, `hr_resumes`) are used for organization.

## 3. Data Design

### 3.1. Database Choice
MongoDB is chosen as the primary database for the LLM Interviewer backend. Its document-oriented nature provides flexibility, which is beneficial given the potentially evolving structure of user profiles (especially with resume analysis data) and interview sessions (which can contain embedded questions and responses). MongoDB's horizontal scalability features (replication and sharding) are suitable for handling potential future growth in data volume and read/write traffic. The availability of a robust asynchronous Python driver (Motor) aligns well with FastAPI's asynchronous capabilities.

### 3.2. Key Collections and Schemas
The database schema is defined by the Pydantic models in `app/models/`. The key collections and their primary fields are:

#### 3.2.1. `users` Collection
Stores information for all user roles (Candidate, HR, Admin).
*   **`_id`**: `ObjectId` (Automatically generated by MongoDB). Unique identifier for the user.
*   **`username`**: `str` (Unique, Indexed). User-chosen username.
*   **`email`**: `EmailStr` (Unique, Indexed). User's email address, used for login and communication.
*   **`hashed_password`**: `str`. Securely hashed password using bcrypt.
*   **`role`**: `UserRole` (Enum: "candidate", "hr", "admin", Indexed). Defines the user's role and permissions.
*   **`created_at`**: `datetime`. Timestamp of user creation.
*   **`updated_at`**: `datetime`. Timestamp of the last update to the user document.
*   **`is_active`**: `bool` (Default: `True`). Flag indicating if the user account is active.
*   **`resume_path`**: `Optional[str]` (Candidate & HR). Path to the uploaded resume file on the server.
*   **`resume_text`**: `Optional[str]` (Candidate & HR, Text Indexed). Extracted text content from the resume. Used for keyword search.
*   **`extracted_skills_list`**: `Optional[List[str]]` (Candidate & HR). List of skills extracted from the resume text by the analyzer.
*   **`estimated_yoe`**: `Optional[float]` (Candidate & HR). Estimated years of experience extracted from the resume text.
*   **`hr_status`**: `Optional[HRStatus]` (Enum: "pending_profile", "profile_complete", "application_pending", "admin_request_pending", "mapped", HR only, Indexed). Tracks the HR user's progress in the mapping workflow.
*   **`mapping_status`**: `Optional[CandidateMappingStatus]` (Enum: "pending_resume", "pending_assignment", "assigned", Candidate only, Indexed). Tracks the candidate's progress in the assignment workflow.
*   **`admin_manager_id`**: `Optional[ObjectId]` (HR only, Indexed). References the `_id` of the Admin user this HR is mapped to.
*   **`assigned_hr_id`**: `Optional[ObjectId]` (Candidate only, Indexed). References the `_id` of the HR user assigned to this candidate.

**Indexes on `users`:**
*   Unique index on `email`.
*   Unique index on `username`.
*   Index on `role`.
*   Index on `hr_status`.
*   Index on `mapping_status`.
*   Index on `admin_manager_id`.
*   Index on `assigned_hr_id`.
*   Text index on `resume_text` for keyword search.

#### 3.2.2. `hr_mapping_requests` Collection
Manages the state of mapping requests/applications between HR and Admins.
*   **`_id`**: `ObjectId`. Unique identifier for the request.
*   **`request_type`**: `RequestMappingType` (Enum: "application", "request", Indexed). Type of mapping initiation.
*   **`requester_id`**: `ObjectId` (Indexed). The user who initiated the request (HR for "application", Admin for "request"). References `_id` in `users`.
*   **`target_id`**: `ObjectId` (Indexed). The user the request is directed to (Admin for "application", HR for "request"). References `_id` in `users`.
*   **`status`**: `RequestMappingStatus` (Enum: "pending", "accepted", "rejected", Indexed). Current status of the request.
*   **`created_at`**: `datetime`. Timestamp of request creation.
*   **`updated_at`**: `datetime`. Timestamp of the last update to the request status.

**Indexes on `hr_mapping_requests`:**
*   Index on `request_type`.
*   Index on `requester_id`.
*   Index on `target_id`.
*   Index on `status`.
*   Compound index on `target_id` and `status` for efficient lookup of pending items for a specific user.

#### 3.2.3. `interviews` Collection
Stores details about interview sessions.
*   **`_id`**: `ObjectId`. Unique identifier for the interview.
*   **`candidate_id`**: `ObjectId` (Indexed). References the `_id` of the candidate user.
*   **`hr_id`**: `ObjectId` (Indexed). References the `_id` of the HR user conducting the interview.
*   **`job_title`**: `str`. The job title the interview is for.
*   **`job_description`**: `Optional[str]`. Optional description of the job role.
*   **`status`**: `InterviewStatus` (Enum: "scheduled", "questions_generated", "in_progress", "completed", "evaluated", Indexed). Current state of the interview.
*   **`scheduled_at`**: `datetime`. Timestamp when the interview was scheduled.
*   **`started_at`**: `Optional[datetime]`. Timestamp when the candidate started the interview.
*   **`completed_at`**: `Optional[datetime]`. Timestamp when the candidate completed the interview.
*   **`generated_questions`**: `List[InterviewQuestion]` (Embedded Documents). List of questions for this interview.
    *   `question_id`: `str` (Unique within the interview). Identifier for the question.
    *   `text`: `str`. The question text.
    *   `category`: `str`. Category of the question (e.g., "Technical", "Behavioral").
    *   `difficulty`: `str`. Difficulty level (e.g., "Easy", "Medium", "Hard").
*   **`candidate_responses`**: `List[CandidateResponse]` (Embedded Documents). List of candidate's answers.
    *   `question_id`: `str`. References the `question_id` in `generated_questions`.
    *   `answer_text`: `str`. The candidate's provided answer.
    *   `submitted_at`: `datetime`. Timestamp when the answer was submitted.
    *   `manual_score`: `Optional[float]` (0.0-5.0). Manual score given by HR/Admin.
    *   `manual_feedback`: `Optional[str]`. Manual feedback given by HR/Admin.
    *   `ai_score`: `Optional[float]` (0.0-5.0). AI-generated score.
    *   `ai_feedback`: `Optional[str]`. AI-generated feedback.
*   **`evaluation_results`**: `Optional[InterviewEvaluation]` (Embedded Document). Overall evaluation results.
    *   `overall_score`: `Optional[float]` (0.0-5.0). Overall score for the interview. Can be manual or calculated from individual question scores.
    *   `overall_feedback`: `Optional[str]`. Overall feedback.
    *   `evaluated_by_id`: `Optional[ObjectId]`. References the user who performed the overall evaluation.
    *   `evaluated_at`: `Optional[datetime]`. Timestamp of overall evaluation.

**Indexes on `interviews`:**
*   Index on `candidate_id`.
*   Index on `hr_id`.
*   Index on `status`.
*   Compound index on `candidate_id` and `status` for fetching candidate's interviews.
*   Compound index on `hr_id` and `status` for fetching HR's interviews.

#### 3.2.4. `messages` Collection
Stores messages sent between users.
*   **`_id`**: `ObjectId`. Unique identifier for the message.
*   **`sender_id`**: `ObjectId` (Indexed). References the `_id` of the sending user.
*   **`recipient_id`**: `ObjectId` (Indexed). References the `_id` of the receiving user.
*   **`subject`**: `Optional[str]`. Subject line of the message.
*   **`content`**: `str`. The message body.
*   **`sent_at`**: `datetime` (Indexed). Timestamp when the message was sent.
*   **`read_status`**: `bool` (Default: `False`, Indexed). Flag indicating if the recipient has read the message.
*   **`read_at`**: `Optional[datetime]`. Timestamp when the message was marked as read.

**Indexes on `messages`:**
*   Index on `sender_id`.
*   Index on `recipient_id`.
*   Index on `sent_at`.
*   Compound index on `recipient_id` and `read_status` for efficient lookup of unread messages.

#### 3.2.5. `default_interview_questions` Collection (Optional)
Stores a set of predefined questions to be used as a fallback if LLM generation fails.
*   **`_id`**: `ObjectId`. Unique identifier for the question.
*   **`text`**: `str`. The question text.
*   **`category`**: `str`. Category of the question.
*   **`difficulty`**: `str`. Difficulty level.
*   **`job_title`**: `Optional[str]` (Indexed). Optional job title this question is relevant for.
*   **`tech_stack`**: `Optional[List[str]]` (Indexed). Optional list of technologies this question is relevant for.

**Indexes on `default_interview_questions`:**
*   Index on `job_title`.
*   Index on `tech_stack`.

### 3.3. Data Flow
Detailed data flow for key processes:

*   **User Registration:**
    *   Frontend sends `POST /api/v1/auth/register` with `UserCreate` schema.
    *   API layer validates input.
    *   Checks `users` collection for existing email/username.
    *   Hashes password using `bcrypt`.
    *   Creates a new user document in the `users` collection with initial status (`pending_resume` for candidate, `pending_profile` for HR).
    *   Returns `UserOut` schema (excluding sensitive info) with 201 Created.
*   **Resume Upload (Candidate/HR):**
    *   Frontend sends `POST /api/v1/candidate/resume` or `POST /api/v1/hr/resume` with `multipart/form-data`.
    *   API layer validates file type and size.
    *   Uses `aiofiles` to asynchronously save the file to the configured upload directory (`uploads/resumes` or `uploads/hr_resumes`) with a unique filename (e.g., `user_id_uuid.ext`).
    *   Calls `resume_parser.parse_resume` to extract text.
    *   If parsing is successful, calls `resume_analyzer_service.analyze_resume` to extract skills and YoE.
    *   Updates the user's document in the `users` collection with `resume_path`, `resume_text`, `extracted_skills_list`, `estimated_yoe`.
    *   Updates the user's status (`mapping_status` to `pending_assignment` for candidate, `hr_status` to `profile_complete` for HR) if the previous status was the initial pending state and parsing was successful.
    *   Includes cleanup logic for orphaned files if updates fail.
    *   Returns updated `CandidateProfileOut` or `HRProfileOut`.
*   **HR Applying to Admin:**
    *   HR user sends `POST /api/v1/hr/apply-to-admin/{admin_id}`.
    *   API layer validates HR role and profile status (`profile_complete`).
    *   Checks if the target Admin exists.
    *   Checks if the HR user already has a pending request/application.
    *   Creates a new document in `hr_mapping_requests` with `request_type="application"`, `requester_id` (HR), `target_id` (Admin), `status="pending"`.
    *   Updates the HR user's `hr_status` to `application_pending`.
    *   Returns the created `HRMappingRequestOut`.
*   **Admin Accepting HR Application:**
    *   Admin user sends `POST /api/v1/admin/hr-applications/{application_id}/accept`.
    *   API layer validates Admin role.
    *   Calls `invitation_service.accept_request_or_application`.
    *   Service finds the pending application in `hr_mapping_requests` targeted at this Admin.
    *   Updates the application `status` to `accepted`.
    *   Updates the HR user's document: sets `hr_status` to `mapped` and `admin_manager_id` to the Admin's ID.
    *   Cleans up any other pending requests/applications for this HR user.
    *   Returns a success message.
*   **Admin Assigning Candidate to HR:**
    *   Admin user sends `POST /api/v1/admin/candidates/{candidate_id}/assign-hr` with `AssignHrRequest` body (`hr_id`).
    *   API layer validates Admin role.
    *   Fetches candidate and HR user documents.
    *   Validates candidate status (`pending_assignment`) and HR status (`mapped`).
    *   Updates the candidate document: sets `assigned_hr_id` to `hr_id` and `mapping_status` to `assigned`.
    *   Returns the updated `CandidateProfileOut`.
*   **Interview Scheduling (by HR/Admin):**
    *   HR/Admin sends `POST /api/v1/hr/interviews/create` (or equivalent admin endpoint) with `InterviewCreate` schema.
    *   API layer validates user role and checks if the user is the assigned HR for the candidate (or is an Admin).
    *   Validates candidate status (`assigned`).
    *   Calls `gemini_service.generate_questions` based on job title, description, and optionally candidate resume text.
    *   If LLM generation fails, attempts to fetch default questions from `default_interview_questions`.
    *   If questions are available (from LLM or defaults), creates a new document in the `interviews` collection with status `scheduled`, embedded questions, and references to candidate/HR.
    *   Returns the created `InterviewOut`.
*   **Candidate Taking Interview:**
    *   Candidate fetches their scheduled interview (`GET /api/v1/candidate/interviews/{interview_id}`).
    *   Candidate submits answers (`POST /api/v1/candidate/interviews/{interview_id}/submit-answer`).
    *   API layer validates candidate role and ownership of the interview.
    *   Updates the `interviews` document, adding the submitted answer to the `candidate_responses` list.
    *   Updates interview status (e.g., to `in_progress` after the first answer, `completed` after the last answer).
    *   Returns updated interview state.
*   **Interview Evaluation (by HR/Admin):**
    *   HR/Admin can manually add scores/feedback to individual answers or the overall interview.
    *   HR/Admin can trigger AI evaluation (`POST /api/v1/hr/interviews/{interview_id}/evaluate`).
    *   API layer validates user role and ownership/assignment.
    *   Calls `gemini_service.evaluate_answer` for each question/answer pair.
    *   Updates the `candidate_responses` embedded documents with AI scores/feedback.
    *   Calculates an overall score if needed (e.g., average of AI scores).
    *   Updates the `evaluation_results` embedded document and interview status to `evaluated`.
    *   Returns the updated `InterviewOut`.

### 3.4. Data Retention and Archival
Currently, the system does not implement automated data retention policies or archival mechanisms. All data is stored indefinitely in MongoDB.

**Future Considerations for Data Management:**
*   **Soft Deletes:** Instead of physically deleting users or interviews, mark them as inactive or archived with a timestamp. This preserves historical data for reporting or potential recovery.
*   **TTL Indexes:** Use MongoDB's Time To Live (TTL) indexes for certain data (e.g., old messages, temporary files) to automatically remove documents after a specified period.
*   **Archival to Cold Storage:** For very large datasets, implement a process to move older, less frequently accessed data to cheaper storage solutions (e.g., S3, Google Cloud Storage) and potentially remove it from the primary MongoDB cluster.
*   **Regular Backups:** Implement a robust schedule for backing up the MongoDB database and the file upload storage. Store backups in a separate location (off-site or in a different cloud region).

## 4. API Design

### 4.0 Application Functionality and API Endpoint Mapping

This section provides a high-level overview of the application's core functionalities for each user role and maps them to their primary API endpoints. This serves as a quick reference before the detailed specifications in section 4.3.

**Common Functionalities (All Authenticated Users):**
*   **View Own Profile:** `GET /api/v1/auth/me`

**Authentication Functionalities:**
*   **User Registration:** `POST /api/v1/auth/register`
*   **User Login:** `POST /api/v1/auth/login`

**Administrator Functionalities:**
The Administrator role has oversight over the entire system, including user management, HR-Admin mapping, candidate assignment, and overall interview process monitoring.
*   **User Management:**
    *   List all users: `GET /api/v1/admin/users`
    *   Delete a non-admin user: `DELETE /api/v1/admin/users/{user_id_to_delete}`
*   **HR Management & Mapping:**
    *   View pending HR applications: `GET /api/v1/admin/hr-applications`
    *   Accept an HR application: `POST /api/v1/admin/hr-applications/{application_id}/accept`
    *   Reject an HR application: `POST /api/v1/admin/hr-applications/{application_id}/reject`
    *   Search for HR profiles: `GET /api/v1/admin/search-hr`
    *   Send a mapping request to an HR: `POST /api/v1/admin/hr/{hr_id}/send-mapping-request`
    *   Unmap an HR: `POST /api/v1/admin/hr/{hr_id}/unmap`
*   **Candidate Management:**
    *   Assign an HR to a Candidate: `POST /api/v1/admin/candidates/{candidate_id}/assign-hr`
    *   Search candidate profiles: `GET /api/v1/admin/search-candidates`
*   **Interview Management (Full Oversight):**
    *   Schedule an interview for any candidate with any mapped HR: `POST /api/v1/admin/interviews/schedule`
    *   List all interviews: `GET /api/v1/admin/interviews`
    *   View a specific interview: `GET /api/v1/admin/interviews/{interview_id}`
    *   Manually evaluate a candidate's response: `POST /api/v1/admin/interviews/{interview_id}/responses/{response_id}/evaluate`
    *   Trigger AI evaluation for an interview/response: `POST /api/v1/admin/interviews/{interview_id}/evaluation/ai`
    *   Submit overall interview evaluation: `POST /api/v1/admin/interviews/{interview_id}/evaluation`
*   **System Statistics:**
    *   View system statistics: `GET /api/v1/admin/stats`

**HR Personnel Functionalities:**
HR Personnel manage their profiles, interact with Admins for mapping, source and invite candidates, and manage the interview process for candidates assigned to them.
*   **Profile Management:**
    *   View own HR profile: `GET /api/v1/hr/profile`
    *   Update own HR profile (details, YoE, company): `PUT /api/v1/hr/profile`
    *   Upload/update own resume: `POST /api/v1/hr/resume`
*   **Admin Mapping Workflow:**
    *   List Admins to apply to: `GET /api/v1/hr/admins-for-application`
    *   Apply to an Admin for mapping: `POST /api/v1/hr/apply-to-admin/{admin_id}`
    *   View pending requests from Admins: `GET /api/v1/hr/admin-requests`
    *   Accept an Admin's mapping request: `POST /api/v1/hr/admin-requests/{request_id}/accept`
    *   Reject an Admin's mapping request: `POST /api/v1/hr/admin-requests/{request_id}/reject`
    *   Unmap self from current Admin: `POST /api/v1/hr/unmap`
*   **Candidate Sourcing & Invitation:**
    *   Search for candidate profiles: `GET /api/v1/hr/search-candidates`
    *   Send an invitation message to a candidate: `POST /api/v1/hr/candidates/{candidate_id}/invite`
*   **Interview Management (for Assigned Candidates):**
    *   List candidates assigned to self: `GET /api/v1/hr/assigned-candidates`
    *   Schedule an interview for an assigned candidate: `POST /api/v1/hr/interviews/schedule`
    *   List interviews managed by self: `GET /api/v1/hr/interviews`
    *   View a specific interview managed by self: `GET /api/v1/hr/interviews/{interview_id}`
    *   Manually evaluate a response in an interview managed by self: `POST /api/v1/hr/interviews/{interview_id}/responses/{response_id}/evaluate`
    *   Trigger AI evaluation for an interview managed by self: `POST /api/v1/hr/interviews/{interview_id}/evaluation/ai`
    *   Submit overall evaluation for an interview managed by self: `POST /api/v1/hr/interviews/{interview_id}/evaluation`
*   **Messaging:**
    *   View messages (sent/received): `GET /api/v1/hr/messages` (also covered by candidate invitation)

**Candidate Functionalities:**
Candidates register, manage their profiles and resumes, receive invitations, and participate in the interview process.
*   **Profile Management:**
    *   View own candidate profile: `GET /api/v1/candidate/profile`
    *   Update own candidate profile: `PUT /api/v1/candidate/profile`
    *   Upload/update own resume: `POST /api/v1/candidate/resume`
*   **Interview Process:**
    *   List own interviews: `GET /api/v1/candidate/interviews`
    *   View a specific interview's details (and questions if active): `GET /api/v1/candidate/interviews/{interview_id}`
    *   Start an interview: `POST /api/v1/candidate/interviews/{interview_id}/start`
    *   Submit an answer to an interview question: `POST /api/v1/candidate/interviews/{interview_id}/submit-answer`
    *   Complete an interview: `POST /api/v1/candidate/interviews/{interview_id}/complete`
*   **Messaging:**
    *   View received messages (e.g., invitations): `GET /api/v1/candidate/messages`
    *   Mark messages as read: `POST /api/v1/candidate/messages/mark-read`

### 4.1. General Principles
The API design adheres to the following principles to ensure consistency, usability, and maintainability:

*   **RESTful Design:** Resources (users, interviews, requests, messages) are exposed via clear URLs, and standard HTTP methods (GET, POST, PUT, DELETE) are used to perform actions on these resources.
*   **JSON Format:** All request bodies and successful response bodies use JSON format. Error responses also use a consistent JSON structure.
*   **API Versioning:** The API is versioned using a URL prefix (`/api/v1/`) to allow for future iterations without breaking existing clients.
*   **Stateless Operations:** Each API request contains all the necessary information for the server to process it. The server does not store client-specific session state between requests. Authentication is handled via JWTs passed in headers.
*   **Clear and Consistent Naming:** Endpoint paths, request/response fields, and error messages use clear, descriptive, and consistent naming conventions (e.g., `users`, `hr-applications`, `candidate_id`).
*   **Meaningful Status Codes:** Standard HTTP status codes are used to indicate the outcome of a request (e.g., 200 OK, 201 Created, 204 No Content, 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 Unprocessable Entity, 500 Internal Server Error).
*   **Input Validation:** All incoming data (request bodies, query parameters, path parameters) is strictly validated using Pydantic schemas at the API layer to ensure data integrity and prevent malicious input.
*   **Output Formatting:** Response data is formatted using Pydantic schemas to ensure consistency and control which fields are exposed to the client (e.g., excluding sensitive fields like `hashed_password`).

### 4.2. Authentication and Authorization
Security is a critical aspect, and the API implements robust authentication and authorization mechanisms:

*   **Authentication:**
    *   Users register via the `/auth/register` endpoint. Passwords are never stored in plain text; they are hashed using `bcrypt` before saving to the database.
    *   Users log in via the `/auth/login` endpoint by providing their email/username and password. The backend verifies the credentials against the stored hash.
    *   Upon successful login, the backend generates a JWT containing essential user information (like user ID and role) and signs it with a secret key.
    *   The JWT is returned to the client. The client is responsible for storing this token (e.g., in local storage or cookies) and including it in the `Authorization` header (`Bearer <token>`) for all subsequent requests to protected endpoints.
    *   FastAPI dependencies (`Depends(get_current_user)`, `Depends(get_current_active_user)`) are used to extract and validate the JWT on incoming requests. If the token is missing, invalid, or expired, a 401 Unauthorized response is returned.
*   **Authorization (Role-Based Access Control - RBAC):**
    *   Each API endpoint is protected by dependencies that check the role of the authenticated user.
    *   Custom dependencies (e.g., `Depends(verify_admin_user)`, `Depends(require_candidate)`, `Depends(require_hr)`) are used to ensure that only users with the required role can access specific routes.
    *   If a user attempts to access an endpoint without the necessary role, a 403 Forbidden response is returned.
    *   Authorization logic also extends to resource ownership checks within the service layer (e.g., ensuring a candidate can only view their own interviews, or an HR can only manage candidates assigned to them).

### 4.3. Detailed Endpoint Specifications
This section provides a detailed breakdown of the API endpoints, grouped by their functional area.

#### 4.3.1. Authentication Endpoints (`/api/v1/auth`)

*   **`POST /api/v1/auth/register`**
    *   **Description:** Registers a new user with a specified role (candidate, hr, or admin). Admin registration might be restricted in production or handled via a separate process.
    *   **Authentication:** None required.
    *   **Request Method:** `POST`
    *   **Request Body:** `UserCreate` schema
        ```json
        {
          "username": "string",
          "email": "user@example.com",
          "password": "string",
          "role": "candidate" | "hr" | "admin"
        }
        ```
    *   **Response Body:** `UserOut` schema (on success, status 201)
        ```json
        {
          "id": "string (ObjectId)",
          "username": "string",
          "email": "user@example.com",
          "role": "candidate" | "hr" | "admin",
          "created_at": "datetime (ISO 8601)",
          "resume_path": "string | null"
          // Other role-specific fields might be null initially
        }
        ```
    *   **Status Codes:**
        *   `201 Created`: User registered successfully.
        *   `400 Bad Request`: Username or email already registered, or invalid role provided.
        *   `422 Unprocessable Entity`: Pydantic validation error for request body (e.g., invalid email format, password too short).
        *   `500 Internal Server Error`: Unexpected server error during registration (e.g., database issue).
    *   **Logic:**
        1.  Receive and validate `UserCreate` data.
        2.  Check if a user with the provided email or username already exists in the `users` collection. If so, return 400.
        3.  Validate the requested `role` against allowed registration roles (e.g., prevent self-registration as admin in production).
        4.  Hash the provided password using `security.get_password_hash`.
        5.  Create a new user document dictionary. Set initial `is_active` to `True`, `created_at` and `updated_at` to current time. Set initial role-specific statuses (`mapping_status` for candidate, `hr_status` for HR).
        6.  Insert the new document into the `users` collection.
        7.  Return the newly created user document, validated against `UserOut` schema.

*   **`POST /api/v1/auth/login`**
    *   **Description:** Logs in a user using email or username and password, returning a JWT access token.
    *   **Authentication:** None required.
    *   **Request Method:** `POST`
    *   **Request Body:** `OAuth2PasswordRequestForm` (standard OAuth2 form data)
        ```
        username: string (can be email or username)
        password: string
        ```
    *   **Response Body:** `Token` schema (on success, status 200)
        ```json
        {
          "access_token": "string",
          "token_type": "bearer"
        }
        ```
    *   **Status Codes:**
        *   `200 OK`: Login successful, returns access token.
        *   `401 Unauthorized`: Incorrect login credentials (user not found or invalid password).
        *   `422 Unprocessable Entity`: Pydantic validation error for form data.
        *   `500 Internal Server Error`: Unexpected server error during login.
    *   **Logic:**
        1.  Receive and validate `OAuth2PasswordRequestForm` data.
        2.  Attempt to retrieve the user from the `users` collection by either email or username.
        3.  If user not found, return 401.
        4.  Verify the provided password against the stored hashed password using `security.verify_password`.
        5.  If password verification fails, return 401.
        6.  If the user is found and password is correct, create a JWT access token using `security.create_access_token`. The token payload should include the user's ID (`sub`) and `role`.
        7.  Return the access token and token type.

*   **`GET /api/v1/auth/me`**
    *   **Description:** Returns the details of the currently authenticated user based on the provided JWT.
    *   **Authentication:** Requires valid JWT (`Depends(get_current_active_user)`).
    *   **Request Method:** `GET`
    *   **Request Body:** None.
    *   **Response Body:** `UserOut` schema (on success, status 200)
        ```json
        {
          "id": "string (ObjectId)",
          "username": "string",
          "email": "user@example.com",
          "role": "candidate" | "hr" | "admin",
          "created_at": "datetime (ISO 8601)",
          "resume_path": "string | null"
          // ... other role-specific fields
        }
        ```
    *   **Status Codes:**
        *   `200 OK`: User details returned successfully.
        *   `401 Unauthorized`: Invalid or missing token.
        *   `500 Internal Server Error`: Unexpected server error during user retrieval.
    *   **Logic:**
        1.  The `get_current_active_user` dependency extracts and validates the JWT from the `Authorization` header.
        2.  The dependency retrieves the user document from the database based on the user ID in the token payload.
        3.  If the user is not found or is inactive, the dependency raises an HTTPException (401).
        4.  The endpoint receives the authenticated `User` model from the dependency.
        5.  Return the user model, validated against the `UserOut` schema.

#### 4.3.2. Admin Endpoints (`/api/v1/admin`)
These endpoints are accessible only to users with the 'admin' role (`Depends(verify_admin_user)`).

*   **`GET /api/v1/admin/users`**
    *   **Description:** Retrieves a list of all users in the system. Supports optional filtering and pagination.
    *   **Authentication:** Requires Admin role.
    *   **Request Method:** `GET`
    *   **Query Parameters:**
        *   `role`: `Optional[UserRole]` - Filter by user role.
        *   `status`: `Optional[str]` - Filter by candidate `mapping_status` or HR `hr_status`.
        *   `limit`: `int` (Default: 100, Max: 1000) - Maximum number of users to return.
        *   `skip`: `int` (Default: 0) - Number of users to skip (for pagination).
    *   **Request Body:** None.
    *   **Response Body:** `List[UserOut]` (on success, status 200)
        ```json
        [
          {
            "id": "string (ObjectId)",
            "username": "string",
            "email": "user1@example.com",
            "role": "candidate",
            "created_at": "datetime (ISO 8601)",
            "resume_path": "string | null",
            "mapping_status": "pending_assignment"
            // ... other fields based on role
          },
          // ... more users
        ]
        ```
    *   **Status Codes:**
        *   `200 OK`: List of users returned.
        *   `401 Unauthorized`: Invalid or missing token.
        *   `403 Forbidden`: Authenticated user is not an Admin.
        *   `422 Unprocessable Entity`: Invalid query parameters.
        *   `500 Internal Server Error`: Database error.
    *   **Logic:**
        1.  Receive and validate query parameters.
        2.  Construct a MongoDB query filter based on `role` and `status` parameters.
        3.  Query the `users` collection using the filter, applying `skip` and `limit` for pagination.
        4.  Fetch the results and validate each document against the `UserOut` schema.
        5.  Return the list of users.

*   **`GET /api/v1/admin/stats`**
    *   **Description:** Retrieves system statistics, such as user counts by role/status, interview counts, etc.
    *   **Authentication:** Requires Admin role.
    *   **Request Method:** `GET`
    *   **Request Body:** None.
    *   **Response Body:** `Dict[str, Any]` (on success, status 200)
        ```json
        {
          "total_users": 100,
          "total_admins": 1,
          "total_hr": 20,
          "total_candidates": 79,
          "hr_profile_complete": 15,
          "hr_mapped": 10,
          "candidates_pending_resume": 30,
          "candidates_pending_assignment": 25,
          "candidates_assigned": 24,
          "total_interviews_scheduled": 75,
          "total_interviews_completed": 60,
          "llm_service_status": "Operational" // Placeholder or actual check
        }
        ```
    *   **Status Codes:**
        *   `200 OK`: Statistics returned.
        *   `401 Unauthorized`: Invalid or missing token.
        *   `403 Forbidden`: Authenticated user is not an Admin.
        *   `500 Internal Server Error`: Database error during aggregation/counting.
    *   **Logic:**
        1.  Perform aggregation queries on the `users` and `interviews` collections to count documents based on roles, statuses, etc.
        2.  Potentially perform a health check on the Gemini service.
        3.  Compile the statistics into a dictionary.
        4.  Return the dictionary.

*   **`DELETE /api/v1/admin/users/{user_id_to_delete}`**
    *   **Description:** Deletes a specified user by ID. Prevents self-deletion or deleting other Admins. If deleting an HR user, un-assigns their candidates.
    *   **Authentication:** Requires Admin role.
    *   **Request Method:** `DELETE`
    *   **Path Parameters:**
        *   `user_id_to_delete`: `str` (ObjectId) - The ID of the user to delete.
    *   **Request Body:** None.
    *   **Response Body:** None (on success, status 204 No Content).
    *   **Status Codes:**
        *   `204 No Content`: User deleted successfully.
        *   `400 Bad Request`: Invalid user ID format.
        *   `401 Unauthorized`: Invalid or missing token.
        *   `403 Forbidden`: Authenticated user is not an Admin, or attempting to delete self or another Admin.
        *   `404 Not Found`: User with the specified ID not found.
        *   `500 Internal Server Error`: Database error during deletion or candidate un-assignment.
    *   **Logic:**
        1.  Receive and validate `user_id_to_delete` format.
        2.  Retrieve the user document to be deleted. If not found, return 404.
        3.  Check if the authenticated Admin user is attempting to delete themselves or another Admin. If so, return 403.
        4.  If the user to be deleted is an HR:
            *   Update all candidate documents where `assigned_hr_id` matches the HR's ID. Set `assigned_hr_id` to `None` and `mapping_status` to `pending_assignment`.
        5.  Delete the user document from the `users` collection.
        6.  Return 204 No Content.

*   **`GET /api/v1/admin/hr-applications`**
    *   **Description:** Retrieves pending HR applications directed to the currently authenticated admin.
    *   **Authentication:** Requires Admin role.
    *   **Request Method:** `GET`
    *   **Request Body:** None.
    *   **Response Body:** `List[HRMappingRequestOut]` (on success, status 200)
        ```json
        [
          {
            "request_type": "application",
            "requester_id": "string (ObjectId)",
            "target_id": "string (ObjectId)",
            "status": "pending",
            "id": "string (ObjectId)",
            "created_at": "datetime (ISO 8601)",
            "updated_at": "datetime (ISO 8601)",
            "requester_info": { // Embedded HR user info
              "id": "string (ObjectId)",
              "username": "string",
              "email": "hr@example.com",
              "role": "hr",
              "years_of_experience": 5.0,
              "company": "Acme Corp"
            },
            "target_info": null // Target is the admin, not embedded for brevity
          }
          // ... more applications
        ]
        ```
    *   **Status Codes:**
        *   `200 OK`: List of pending applications returned.
        *   `401 Unauthorized`: Invalid or missing token.
        *   `403 Forbidden`: Authenticated user is not an Admin.
        *   `500 Internal Server Error`: Error fetching applications from the database or service.
    *   **Logic:**
        1.  Get the authenticated Admin user ID.
        2.  Call `InvitationService.get_pending_applications_for_admin` with the Admin ID.
        3.  The service queries `hr_mapping_requests` for documents where `request_type="application"`, `target_id` matches the Admin ID, and `status="pending"`.
        4.  Uses MongoDB aggregation (`$lookup`) to join with the `users` collection and embed the `requester_info` (HR user details).
        5.  Returns the list of requests, validated against `HRMappingRequestOut`.

*   **`POST /api/v1/admin/hr-applications/{application_id}/accept`**
    *   **Description:** Allows an admin to accept an HR's application for mapping.
    *   **Authentication:** Requires Admin role.
    *   **Request Method:** `POST`
    *   **Path Parameters:**
        *   `application_id`: `str` (ObjectId) - The ID of the HR mapping request document.
    *   **Request Body:** None.
    *   **Response Body:** `Dict[str, str]` (on success, status 200)
        ```json
        {
          "message": "Application <application_id> accepted."
        }
        ```
    *   **Status Codes:**
        *   `200 OK`: Application accepted successfully.
        *   `400 Bad Request`: Invalid application ID format, or `InvitationError` from service (e.g., request not found, not pending, not an application, not targeted at this admin).
        *   `401 Unauthorized`: Invalid or missing token.
        *   `403 Forbidden`: Authenticated user is not an Admin.
        *   `500 Internal Server Error`: Service or database error during acceptance.
    *   **Logic:**
        1.  Get the authenticated Admin user.
        2.  Call `InvitationService.accept_request_or_application` with the `application_id` and the Admin user object.
        3.  The service validates the request, updates its status to `accepted`, updates the HR user's status to `mapped` and sets their `admin_manager_id`.
        4.  Returns a success message.

*   **`POST /api/v1/admin/hr-applications/{application_id}/reject`**
    *   **Description:** Allows an admin to reject an HR's application.
    *   **Authentication:** Requires Admin role.
    *   **Request Method:** `POST`
    *   **Path Parameters:**
        *   `application_id`: `str` (ObjectId) - The ID of the HR mapping request document.
    *   **Request Body:** None.
    *   **Response Body:** `Dict[str, str]` (on success, status 200)
        ```json
        {
          "message": "Application <application_id> rejected."
        }
        ```
    *   **Status Codes:**
        *   `200 OK`: Application rejected successfully.
        *   `400 Bad Request`: Invalid application ID format, or `InvitationError` from service (e.g., request not found, not pending, not an application, not targeted at this admin).
        *   `401 Unauthorized`: Invalid or missing token.
        *   `403 Forbidden`: Authenticated user is not an Admin.
        *   `500 Internal Server Error`: Service or database error during rejection.
    *   **Logic:**
        1.  Get the authenticated Admin user.
        2.  Call `InvitationService.reject_request_or_application` with the `application_id` and the Admin user object.
        3.  The service validates the request, updates its status to `rejected`, and resets the HR user's `hr_status` to `profile_complete` if they have no other pending items.
        4.  Returns a success message.

*   **`GET /api/v1/admin/search-hr`**
    *   **Description:** Searches for HR profiles based on query parameters (status, keyword in resume, years of experience).
    *   **Authentication:** Requires Admin role.
    *   **Request Method:** `GET`
    *   **Query Parameters:**
        *   `status_filter`: `Optional[HRStatus]` - Filter by HR status. Defaults to `profile_complete`.
        *   `keyword`: `Optional[str]` - Keyword to search in HR resume text (requires text index).
        *   `yoe_min`: `Optional[float]` (>= 0) - Minimum years of experience.
        *   `limit`: `int` (Default: 20, Max: 100) - Maximum number of results.
        *   `skip`: `int` (Default: 0) - Number of results to skip.
    *   **Request Body:** None.
    *   **Response Body:** `List[RankedHR]` (on success, status 200)
        ```json
        [
          {
            "id": "string (ObjectId)",
            "username": "string",
            "email": "hr1@example.com",
            "role": "hr",
            "created_at": "datetime (ISO 8601)",
            "resume_path": "string | null",
            "hr_status": "mapped",
            "years_of_experience": 5.0,
            "company": "string | null",
            "admin_manager_id": "string (ObjectId) | null",
            "relevance_score": 0.95, // Score based on search criteria
            "match_details": { // Details explaining the score
              "text_search_score": 0.5,
              "yoe_match": true
            }
          }
          // ... more ranked HRs
        ]
        ```
    *   **Status Codes:**
        *   `200 OK`: List of ranked HR profiles returned.
        *   `401 Unauthorized`: Invalid or missing token.
        *   `403 Forbidden`: Authenticated user is not an Admin.
        *   `422 Unprocessable Entity`: Invalid query parameters.
        *   `500 Internal Server Error`: Service or database error.
    *   **Logic:**
        1.  Get the authenticated Admin user.
        2.  Call `SearchService.search_hr_profiles` with validated query parameters.
        3.  The service queries the `users` collection for users with `role="hr"`.
        4.  Applies filters for `status_filter`, `keyword` (text search on `resume_text`), and `yoe_min`.
        5.  Calculates a `relevance_score` for each matching HR profile.
        6.  Returns the list of `RankedHR` objects.

*   **`POST /api/v1/admin/hr/{hr_id}/send-mapping-request`**
    *   **Description:** Allows an Admin to send a mapping request to an HR user.
    *   **Authentication:** Requires Admin role.
    *   **Request Method:** `POST`
    *   **Path Parameters:**
        *   `hr_id`: `str` (ObjectId) - The ID of the HR user to send the request to.
    *   **Request Body:** None.
    *   **Response Body:** `HRMappingRequestOut` (on success, status 201)
    *   **Status Codes:**
        *   `201 Created`: Mapping request sent successfully.
        *   `400 Bad Request`: Invalid HR ID, HR user not found, HR user not in a state to receive a request (e.g., already mapped, application pending), or Admin already has a pending request to this HR.
        *   `401 Unauthorized`: Invalid or missing token.
        *   `403 Forbidden`: Authenticated user is not an Admin.
        *   `404 Not Found`: HR user with `hr_id` not found.
        *   `422 Unprocessable Entity`: Invalid `hr_id` format.
        *   `500 Internal Server Error`: Service or database error.
    *   **Logic:**
        1.  Get the authenticated Admin user.
        2.  Validate `hr_id`.
        3.  Call `InvitationService.create_admin_to_hr_request` with Admin user and `hr_id`.
        4.  The service checks:
            *   If the target HR user exists and has `role="hr"`.
            *   If the HR user's `hr_status` is `profile_complete`.
            *   If there isn't an existing pending request from this Admin to this HR, or an application from this HR to this Admin.
            *   If the HR is not already mapped.
        5.  Creates a new document in `hr_mapping_requests` with `request_type="request"`, `requester_id` (Admin), `target_id` (HR), `status="pending"`.
        6.  Updates the HR user's `hr_status` to `admin_request_pending`.
        7.  Returns the created `HRMappingRequestOut`.

*   **`POST /api/v1/admin/hr/{hr_id}/unmap`**
    *   **Description:** Allows an Admin to unmap a currently mapped HR user. This removes the mapping but does not delete the HR user.
    *   **Authentication:** Requires Admin role.
    *   **Request Method:** `POST`
    *   **Path Parameters:**
        *   `hr_id`: `str` (ObjectId) - The ID of the HR user to unmap.
    *   **Request Body:** None.
    *   **Response Body:** `Dict[str, str]` (on success, status 200)
        ```json
        {
          "message": "HR user <hr_id> unmapped successfully."
        }
        ```
    *   **Status Codes:**
        *   `200 OK`: HR user unmapped successfully.
        *   `400 Bad Request`: Invalid HR ID, HR user not found, HR user not mapped to this Admin, or other service error.
        *   `401 Unauthorized`: Invalid or missing token.
        *   `403 Forbidden`: Authenticated user is not an Admin.
        *   `404 Not Found`: HR user with `hr_id` not found.
        *   `422 Unprocessable Entity`: Invalid `hr_id` format.
        *   `500 Internal Server Error`: Service or database error.
    *   **Logic:**
        1.  Get the authenticated Admin user.
        2.  Validate `hr_id`.
        3.  Call `InvitationService.admin_unmap_hr` with Admin user and `hr_id`.
        4.  The service checks:
            *   If the target HR user exists and has `role="hr"`.
            *   If the HR user's `hr_status` is `mapped` and `admin_manager_id` matches the authenticated Admin's ID.
        5.  Updates the HR user's document: sets `hr_status` to `profile_complete` and `admin_manager_id` to `None`.
        6.  Optionally, re-assign candidates previously assigned to this HR (e.g., set their `assigned_hr_id` to `None` and `mapping_status` to `pending_assignment`). This needs clarification on business logic.
        7.  Returns a success message.

*   **`POST /api/v1/admin/candidates/{candidate_id}/assign-hr`**
    *   **Description:** Assigns a specific HR user to a candidate.
    *   **Authentication:** Requires Admin role.
    *   **Request Method:** `POST`
    *   **Path Parameters:**
        *   `candidate_id`: `str` (ObjectId) - The ID of the candidate.
    *   **Request Body:** `AssignHrRequest` schema
        ```json
        {
          "hr_id": "string (ObjectId)"
        }
        ```
    *   **Response Body:** `CandidateProfileOut` (on success, status 200)
    *   **Status Codes:**
        *   `200 OK`: HR assigned to candidate successfully.
        *   `400 Bad Request`: Invalid candidate ID or HR ID, candidate not found, HR not found, candidate not in `pending_assignment` status, HR not in `mapped` status, or HR is not managed by this Admin (if applicable).
        *   `401 Unauthorized`: Invalid or missing token.
        *   `403 Forbidden`: Authenticated user is not an Admin.
        *   `404 Not Found`: Candidate or HR user not found.
        *   `422 Unprocessable Entity`: Invalid ID format or request body.
        *   `500 Internal Server Error`: Database error.
    *   **Logic:**
        1.  Get the authenticated Admin user.
        2.  Validate `candidate_id` and `hr_id` from the request body.
        3.  Retrieve the candidate user document. If not found or not a candidate, return 404/400.
        4.  Retrieve the HR user document. If not found or not an HR, return 404/400.
        5.  Check candidate's `mapping_status`. Must be `pending_assignment`.
        6.  Check HR user's `hr_status`. Must be `mapped`. (Optionally, check if `admin_manager_id` of HR matches current Admin, or allow any Admin to assign any mapped HR).
        7.  Update the candidate document: set `assigned_hr_id` to `hr_id` and `mapping_status` to `assigned`.
        8.  Return the updated candidate profile.

*   **`GET /api/v1/admin/search-candidates`**
    *   **Description:** Searches for candidate profiles. Mirrors HR functionality but accessible to Admins for oversight.
    *   **Authentication:** Requires Admin role.
    *   **Request Method:** `GET`
    *   **Query Parameters:**
        *   `status_filter`: `Optional[CandidateMappingStatus]` - Filter by candidate mapping status.
        *   `keyword`: `Optional[str]` - Keyword to search in candidate resume text.
        *   `skills`: `Optional[List[str]]` - List of skills to filter by (exact match on `extracted_skills_list`).
        *   `yoe_min`: `Optional[float]` (>= 0) - Minimum years of experience.
        *   `limit`: `int` (Default: 20, Max: 100)
        *   `skip`: `int` (Default: 0)
    *   **Request Body:** None.
    *   **Response Body:** `List[RankedCandidate]` (on success, status 200)
    *   **Status Codes:**
        *   `200 OK`: List of ranked candidate profiles returned.
        *   `401 Unauthorized`: Invalid or missing token.
        *   `403 Forbidden`: Authenticated user is not an Admin.
        *   `422 Unprocessable Entity`: Invalid query parameters.
        *   `500 Internal Server Error`: Service or database error.
    *   **Logic:**
        1.  Call `SearchService.search_candidates` with validated query parameters.
        2.  The service queries `users` collection for `role="candidate"`.
        3.  Applies filters and calculates relevance scores.
        4.  Returns the list of `RankedCandidate` objects.

*   **`POST /api/v1/admin/interviews/schedule`**
    *   **Description:** Allows an Admin to schedule an interview for any candidate, assigning any mapped HR.
    *   **Authentication:** Requires Admin role.
    *   **Request Method:** `POST`
    *   **Request Body:** `AdminInterviewCreate` schema (similar to `InterviewCreate` but might include `hr_id` if Admin is scheduling for an HR they don't manage, or if HR is not yet assigned to candidate).
        ```json
        {
          "candidate_id": "string (ObjectId)",
          "hr_id": "string (ObjectId)", // HR who will conduct/be associated
          "job_title": "string",
          "job_description": "string | null",
          "tech_stack": "List[string] | null",
          "use_candidate_resume_for_questions": "bool | null"
        }
        ```
    *   **Response Body:** `InterviewOut` (on success, status 201)
    *   **Status Codes:**
        *   `201 Created`: Interview scheduled successfully.
        *   `400 Bad Request`: Invalid input (e.g., candidate/HR not found, candidate not assignable, HR not mapped).
        *   `401 Unauthorized`: Invalid or missing token.
        *   `403 Forbidden`: Authenticated user is not an Admin.
        *   `422 Unprocessable Entity`: Validation error.
        *   `500 Internal Server Error`: LLM service error or database error.
    *   **Logic:**
        1.  Validate request body.
        2.  Verify candidate exists and is in a schedulable state (e.g., `assigned` or Admin overrides).
        3.  Verify HR exists and is `mapped`.
        4.  If candidate is not yet assigned to this HR, Admin assignment might happen implicitly or be a prerequisite.
        5.  Call `GeminiService.generate_questions`.
        6.  If LLM fails, use fallback questions.
        7.  Create `Interview` document.
        8.  Return `InterviewOut`.

*   **`GET /api/v1/admin/interviews`**
    *   **Description:** Retrieves a list of all interviews in the system. Supports filtering and pagination.
    *   **Authentication:** Requires Admin role.
    *   **Request Method:** `GET`
    *   **Query Parameters:**
        *   `candidate_id`: `Optional[str]` (ObjectId)
        *   `hr_id`: `Optional[str]` (ObjectId)
        *   `status`: `Optional[InterviewStatus]`
        *   `limit`: `int` (Default: 100)
        *   `skip`: `int` (Default: 0)
    *   **Response Body:** `List[InterviewOut]` (on success, status 200)
    *   **Status Codes:**
        *   `200 OK`.
        *   `401 Unauthorized`.
        *   `403 Forbidden`.
        *   `422 Unprocessable Entity`.
    *   **Logic:**
        1.  Construct query based on filters.
        2.  Fetch interviews from `interviews` collection.
        3.  Return list.

*   **`GET /api/v1/admin/interviews/{interview_id}`**
    *   **Description:** Retrieves details of a specific interview.
    *   **Authentication:** Requires Admin role.
    *   **Request Method:** `GET`
    *   **Path Parameters:** `interview_id`: `str` (ObjectId)
    *   **Response Body:** `InterviewOut` (on success, status 200)
    *   **Status Codes:**
        *   `200 OK`.
        *   `401 Unauthorized`.
        *   `403 Forbidden`.
        *   `404 Not Found`.
    *   **Logic:** Fetch interview by ID.

*   **`POST /api/v1/admin/interviews/{interview_id}/responses/{response_id}/evaluate`**
    *   **Description:** Admin manually scores and provides feedback for a specific candidate response.
    *   **Authentication:** Requires Admin role.
    *   **Request Method:** `POST`
    *   **Path Parameters:** `interview_id`, `response_id` (or `question_id`)
    *   **Request Body:** `ManualEvaluationIn` schema
        ```json
        {
          "manual_score": "float (0.0-5.0)",
          "manual_feedback": "string"
        }
        ```
    *   **Response Body:** `InterviewOut` (updated interview, status 200)
    *   **Status Codes:**
        *   `200 OK`.
        *   `400 Bad Request`.
        *   `401 Unauthorized`.
        *   `403 Forbidden`.
        *   `404 Not Found` (interview or response).
        *   `422 Unprocessable Entity`.
    *   **Logic:**
        1.  Find interview and the specific response.
        2.  Update `manual_score` and `manual_feedback` for the response.
        3.  Update interview's `updated_at` and potentially overall evaluation if logic dictates.
        4.  Return updated interview.

*   **`POST /api/v1/admin/interviews/{interview_id}/evaluation/ai`**
    *   **Description:** Triggers AI evaluation for all unanswered/unevaluated questions or a specific question in an interview.
    *   **Authentication:** Requires Admin role.
    *   **Request Method:** `POST`
    *   **Path Parameters:** `interview_id`
    *   **Request Body:** `AIEvaluationTriggerIn` (optional, e.g., `question_id` if for a specific one)
        ```json
        {
          "question_id": "string | null" // If null, evaluate all applicable
        }
        ```
    *   **Response Body:** `InterviewOut` (updated interview, status 200)
    *   **Status Codes:**
        *   `200 OK`.
        *   `400 Bad Request`.
        *   `401 Unauthorized`.
        *   `403 Forbidden`.
        *   `404 Not Found`.
        *   `500 Internal Server Error` (LLM error).
    *   **Logic:**
        1.  Fetch interview.
        2.  Iterate through responses (all or specific).
        3.  For each, call `GeminiService.evaluate_answer`.
        4.  Update `ai_score` and `ai_feedback`.
        5.  Update interview status to `evaluated` if all done.
        6.  Return updated interview.

*   **`POST /api/v1/admin/interviews/{interview_id}/evaluation`**
    *   **Description:** Admin provides overall manual evaluation for an interview.
    *   **Authentication:** Requires Admin role.
    *   **Request Method:** `POST`
    *   **Path Parameters:** `interview_id`
    *   **Request Body:** `OverallEvaluationIn` schema
        ```json
        {
          "overall_score": "float (0.0-5.0)",
          "overall_feedback": "string"
        }
        ```
    *   **Response Body:** `InterviewOut` (updated interview, status 200)
    *   **Status Codes:**
        *   `200 OK`.
        *   `400 Bad Request`.
        *   `401 Unauthorized`.
        *   `403 Forbidden`.
        *   `404 Not Found`.
        *   `422 Unprocessable Entity`.
    *   **Logic:**
        1.  Fetch interview.
        2.  Update `evaluation_results` with Admin's ID, score, feedback, and timestamp.
        3.  Set interview status to `evaluated`.
        4.  Return updated interview.

#### 4.3.3. Candidate Endpoints (`/api/v1/candidate`)
These endpoints are accessible to users with the 'candidate' role (`Depends(require_candidate)`).

*   **`GET /api/v1/candidate/profile`**
    *   **Description:** Retrieves the profile of the currently authenticated candidate.
    *   **Authentication:** Requires Candidate role.
    *   **Request Method:** `GET`
    *   **Response Body:** `CandidateProfileOut` schema (on success, status 200)
    *   **Status Codes:** `200 OK`, `401 Unauthorized`, `403 Forbidden`.

*   **`PUT /api/v1/candidate/profile`**
    *   **Description:** Updates the profile of the currently authenticated candidate.
    *   **Authentication:** Requires Candidate role.
    *   **Request Method:** `PUT`
    *   **Request Body:** `CandidateProfileUpdate` schema
    *   **Response Body:** `CandidateProfileOut` (on success, status 200)
    *   **Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `422 Unprocessable Entity`.

*   **`POST /api/v1/candidate/resume`**
    *   **Description:** Uploads or updates the candidate's resume.
    *   **Authentication:** Requires Candidate role.
    *   **Request Method:** `POST`
    *   **Request Body:** `multipart/form-data` with a file field (e.g., `resume`).
    *   **Response Body:** `CandidateProfileOut` (on success, status 200)
    *   **Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `422 Unprocessable Entity`, `500 Internal Server Error`.

*   **`GET /api/v1/candidate/interviews`**
    *   **Description:** Retrieves a list of interviews for the authenticated candidate.
    *   **Authentication:** Requires Candidate role.
    *   **Request Method:** `GET`
    *   **Query Parameters:** `status`, `limit`, `skip`.
    *   **Response Body:** `List[InterviewCandidateView]` (on success, status 200)
    *   **Status Codes:** `200 OK`, `401 Unauthorized`, `403 Forbidden`.

*   **`GET /api/v1/candidate/interviews/{interview_id}`**
    *   **Description:** Retrieves details of a specific interview for the candidate.
    *   **Authentication:** Requires Candidate role.
    *   **Request Method:** `GET`
    *   **Path Parameters:** `interview_id`.
    *   **Response Body:** `InterviewCandidateView` (on success, status 200)
    *   **Status Codes:** `200 OK`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`.

*   **`POST /api/v1/candidate/interviews/{interview_id}/start`**
    *   **Description:** Marks an interview as started by the candidate.
    *   **Authentication:** Requires Candidate role.
    *   **Request Method:** `POST`
    *   **Path Parameters:** `interview_id`.
    *   **Response Body:** `InterviewCandidateView` (updated interview, status 200)
    *   **Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`.

*   **`POST /api/v1/candidate/interviews/{interview_id}/submit-answer`**
    *   **Description:** Submits an answer for a specific question in an ongoing interview.
    *   **Authentication:** Requires Candidate role.
    *   **Request Method:** `POST`
    *   **Path Parameters:** `interview_id`.
    *   **Request Body:** `SubmitAnswerIn` schema
    *   **Response Body:** `InterviewCandidateView` (updated interview, status 200)
    *   **Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`, `422 Unprocessable Entity`.

*   **`POST /api/v1/candidate/interviews/{interview_id}/complete`**
    *   **Description:** Marks an interview as completed by the candidate.
    *   **Authentication:** Requires Candidate role.
    *   **Request Method:** `POST`
    *   **Path Parameters:** `interview_id`.
    *   **Response Body:** `InterviewCandidateView` (updated interview, status 200)
    *   **Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`.

*   **`GET /api/v1/candidate/messages`**
    *   **Description:** Retrieves messages for the authenticated candidate.
    *   **Authentication:** Requires Candidate role.
    *   **Request Method:** `GET`
    *   **Query Parameters:** `limit`, `skip`, `unread_only`.
    *   **Response Body:** `List[MessageOut]` (on success, status 200)
    *   **Status Codes:** `200 OK`, `401 Unauthorized`, `403 Forbidden`.

*   **`POST /api/v1/candidate/messages/mark-read`**
    *   **Description:** Marks specified messages as read for the candidate.
    *   **Authentication:** Requires Candidate role.
    *   **Request Method:** `POST`
    *   **Request Body:** `MarkMessagesReadIn` schema
    *   **Response Body:** `Dict[str, int]` (status 200)
    *   **Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `422 Unprocessable Entity`.

#### 4.3.4. HR Endpoints (`/api/v1/hr`)
These endpoints are accessible to users with the 'hr' role (`Depends(require_hr)`).

*   **`GET /api/v1/hr/profile`**
    *   **Description:** Retrieves the profile of the currently authenticated HR user.
    *   **Authentication:** Requires HR role.
    *   **Request Method:** `GET`
    *   **Response Body:** `HRProfileOut` schema (on success, status 200)
    *   **Status Codes:** `200 OK`, `401 Unauthorized`, `403 Forbidden`.

*   **`PUT /api/v1/hr/profile`**
    *   **Description:** Updates the profile of the currently authenticated HR user.
    *   **Authentication:** Requires HR role.
    *   **Request Method:** `PUT`
    *   **Request Body:** `HRProfileUpdate` schema
    *   **Response Body:** `HRProfileOut` (on success, status 200)
    *   **Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `422 Unprocessable Entity`.

*   **`POST /api/v1/hr/resume`**
    *   **Description:** Uploads or updates the HR user's resume.
    *   **Authentication:** Requires HR role.
    *   **Request Method:** `POST`
    *   **Request Body:** `multipart/form-data` with `resume`.
    *   **Response Body:** `HRProfileOut` (on success, status 200)
    *   **Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `422 Unprocessable Entity`, `500 Internal Server Error`.

*   **`GET /api/v1/hr/admins-for-application`**
    *   **Description:** Retrieves a list of Admin users to whom the HR can apply for mapping.
    *   **Authentication:** Requires HR role, `hr_status` must be `profile_complete`.
    *   **Request Method:** `GET`
    *   **Response Body:** `List[AdminBasicInfo]` (on success, status 200)
    *   **Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`.

*   **`POST /api/v1/hr/apply-to-admin/{admin_id}`**
    *   **Description:** HR user applies to a specific Admin for mapping.
    *   **Authentication:** Requires HR role, `hr_status` must be `profile_complete`.
    *   **Request Method:** `POST`
    *   **Path Parameters:** `admin_id`.
    *   **Response Body:** `HRMappingRequestOut` (on success, status 201)
    *   **Status Codes:** `201 Created`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`.

*   **`GET /api/v1/hr/admin-requests`**
    *   **Description:** Retrieves pending mapping requests sent by Admins to the authenticated HR user.
    *   **Authentication:** Requires HR role.
    *   **Request Method:** `GET`
    *   **Response Body:** `List[HRMappingRequestOut]` (on success, status 200)
    *   **Status Codes:** `200 OK`, `401 Unauthorized`, `403 Forbidden`.

*   **`POST /api/v1/hr/admin-requests/{request_id}/accept`**
    *   **Description:** HR accepts a mapping request from an Admin.
    *   **Authentication:** Requires HR role.
    *   **Request Method:** `POST`
    *   **Path Parameters:** `request_id`.
    *   **Response Body:** `Dict[str, str]` (on success, status 200)
    *   **Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`.

*   **`POST /api/v1/hr/admin-requests/{request_id}/reject`**
    *   **Description:** HR rejects a mapping request from an Admin.
    *   **Authentication:** Requires HR role.
    *   **Request Method:** `POST`
    *   **Path Parameters:** `request_id`.
    *   **Response Body:** `Dict[str, str]` (on success, status 200)
    *   **Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`.

*   **`POST /api/v1/hr/unmap`**
    *   **Description:** HR user unmaps themselves from their current Admin.
    *   **Authentication:** Requires HR role, `hr_status` must be `mapped`.
    *   **Request Method:** `POST`
    *   **Response Body:** `Dict[str, str]` (on success, status 200)
    *   **Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`.

*   **`GET /api/v1/hr/search-candidates`**
    *   **Description:** Searches for candidate profiles.
    *   **Authentication:** Requires HR role, `hr_status` must be `mapped`.
    *   **Request Method:** `GET`
    *   **Query Parameters:** (Same as Admin's search-candidates)
    *   **Response Body:** `List[RankedCandidate]` (on success, status 200)
    *   **Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`.

*   **`POST /api/v1/hr/candidates/{candidate_id}/invite`**
    *   **Description:** HR sends an invitation message to a candidate.
    *   **Authentication:** Requires HR role, `hr_status` must be `mapped`.
    *   **Request Method:** `POST`
    *   **Path Parameters:** `candidate_id`.
    *   **Request Body:** `MessageCreate` schema
    *   **Response Body:** `MessageOut` (on success, status 201)
    *   **Status Codes:** `201 Created`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`.

*   **`GET /api/v1/hr/assigned-candidates`**
    *   **Description:** Retrieves a list of candidates assigned to the authenticated HR.
    *   **Authentication:** Requires HR role, `hr_status` must be `mapped`.
    *   **Request Method:** `GET`
    *   **Query Parameters:** `limit`, `skip`.
    *   **Response Body:** `List[CandidateProfileOut]` (on success, status 200)
    *   **Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`.

*   **`POST /api/v1/hr/interviews/schedule`**
    *   **Description:** HR schedules an interview for an assigned candidate.
    *   **Authentication:** Requires HR role, `hr_status` must be `mapped`.
    *   **Request Method:** `POST`
    *   **Request Body:** `InterviewCreate` schema
    *   **Response Body:** `InterviewOut` (on success, status 201)
    *   **Status Codes:** `201 Created`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`.

*   **`GET /api/v1/hr/interviews`**
    *   **Description:** Retrieves interviews conducted or scheduled by the authenticated HR.
    *   **Authentication:** Requires HR role.
    *   **Request Method:** `GET`
    *   **Query Parameters:** `candidate_id`, `status`, `limit`, `skip`.
    *   **Response Body:** `List[InterviewOut]` (on success, status 200)
    *   **Status Codes:** `200 OK`, `401 Unauthorized`, `403 Forbidden`.

*   **`GET /api/v1/hr/interviews/{interview_id}`**
    *   **Description:** Retrieves details of a specific interview managed by the HR.
    *   **Authentication:** Requires HR role.
    *   **Request Method:** `GET`
    *   **Path Parameters:** `interview_id`.
    *   **Response Body:** `InterviewOut` (on success, status 200)
    *   **Status Codes:** `200 OK`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`.

*   **`POST /api/v1/hr/interviews/{interview_id}/responses/{response_id}/evaluate`**
    *   **Description:** HR manually scores and provides feedback for a specific candidate response.
    *   **Authentication:** Requires HR role.
    *   **Request Method:** `POST`
    *   **Path Parameters:** `interview_id`, `response_id`.
    *   **Request Body:** `ManualEvaluationIn` schema
    *   **Response Body:** `InterviewOut` (updated interview, status 200)
    *   **Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`.

*   **`POST /api/v1/hr/interviews/{interview_id}/evaluation/ai`**
    *   **Description:** Triggers AI evaluation for an interview managed by the HR.
    *   **Authentication:** Requires HR role.
    *   **Request Method:** `POST`
    *   **Path Parameters:** `interview_id`.
    *   **Request Body:** `AIEvaluationTriggerIn`
    *   **Response Body:** `InterviewOut` (updated interview, status 200)
    *   **Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`.

*   **`POST /api/v1/hr/interviews/{interview_id}/evaluation`**
    *   **Description:** HR provides overall manual evaluation for an interview.
    *   **Authentication:** Requires HR role.
    *   **Request Method:** `POST`
    *   **Path Parameters:** `interview_id`.
    *   **Request Body:** `OverallEvaluationIn` schema
    *   **Response Body:** `InterviewOut` (updated interview, status 200)
    *   **Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`.

*   **`GET /api/v1/hr/messages`**
    *   **Description:** Retrieves messages sent or received by the HR user.
    *   **Authentication:** Requires HR role.
    *   **Request Method:** `GET`
    *   **Query Parameters:** `limit`, `skip`, `unread_only`, `candidate_id`.
    *   **Response Body:** `List[MessageOut]` (on success, status 200)
    *   **Status Codes:** `200 OK`, `401 Unauthorized`, `403 Forbidden`.

## 5. Service Layer Design

This section outlines the core services responsible for the business logic of the LLM Interviewer backend. Each service encapsulates a specific domain of functionality, interacting with the Data Access Layer for database operations and other services or external APIs as needed.

### 5.1. `GeminiService` (`app/services/gemini_service.py`)
Handles all interactions with the Google Gemini API.
*   **Purpose:** To abstract the complexities of LLM communication, prompt engineering, and response parsing.
*   **Key Responsibilities & Methods:**
    *   `generate_questions(job_title: str, job_description: Optional[str], tech_stack: Optional[List[str]], candidate_resume_text: Optional[str]) -> List[InterviewQuestionSchema]`:
        *   Constructs an appropriate prompt for Gemini based on job details and optionally candidate resume.
        *   Calls the Gemini API to generate interview questions.
        *   Parses the LLM response (expected to be JSON) into a list of `InterviewQuestionSchema` objects.
        *   Handles API errors, rate limits, and content safety issues from Gemini.
        *   Includes logic for cleaning and validating the LLM's JSON output.
    *   `evaluate_answer(question_text: str, answer_text: str, job_context: Optional[str]) -> EvaluationResultSchema`:
        *   Constructs a prompt for Gemini to evaluate a candidate's answer against a given question and job context.
        *   Calls the Gemini API to get a score and feedback.
        *   Parses the LLM response into an `EvaluationResultSchema` object (containing score and feedback).
        *   Handles API errors and response parsing.
    *   `_call_gemini_api(prompt: str) -> str`: (Private helper) Manages the actual API call, including error handling and retries.
    *   `_clean_json_response(raw_text: str) -> Optional[Union[List[Dict], Dict]]`: (Private helper) Cleans and parses potentially malformed JSON from LLM.

### 5.2. `InvitationService` (`app/services/invitation_service.py`)
Manages the workflow for HR personnel applying to Admins and Admins sending requests to HR personnel for mapping.
*   **Purpose:** To orchestrate the multi-step process of establishing a supervisory relationship between an HR user and an Admin.
*   **Key Responsibilities & Methods:**
    *   `create_hr_to_admin_application(hr_user: User, admin_id: ObjectId, db: AsyncIOMotorDatabase) -> HRMappingRequest`:
        *   Validates if the HR user can create an application (e.g., profile complete, not already mapped or applied).
        *   Validates if the target Admin exists.
        *   Creates an `HRMappingRequest` document with `type="application"` and `status="pending"`.
        *   Updates the HR user's `hr_status` to `application_pending`.
    *   `create_admin_to_hr_request(admin_user: User, hr_id: ObjectId, db: AsyncIOMotorDatabase) -> HRMappingRequest`:
        *   Validates if the Admin can send a request.
        *   Validates if the target HR user exists, is an HR, and is in a state to receive a request (e.g., profile complete, not mapped).
        *   Creates an `HRMappingRequest` document with `type="request"` and `status="pending"`.
        *   Updates the HR user's `hr_status` to `admin_request_pending`.
    *   `accept_request_or_application(request_id: ObjectId, current_user: User, db: AsyncIOMotorDatabase) -> HRMappingRequest`:
        *   Validates the request exists, is pending, and the `current_user` is the correct target (Admin for application, HR for request).
        *   Updates the `HRMappingRequest` status to `accepted`.
        *   Updates the HR user's `hr_status` to `mapped` and sets their `admin_manager_id`.
        *   Updates the Admin user (if necessary, e.g., list of managed HRs - though current model doesn't show this on Admin).
        *   Deletes/invalidates other pending requests/applications for the involved HR user.
    *   `reject_request_or_application(request_id: ObjectId, current_user: User, db: AsyncIOMotorDatabase) -> HRMappingRequest`:
        *   Validates the request and current user.
        *   Updates the `HRMappingRequest` status to `rejected`.
        *   Resets the HR user's `hr_status` to `profile_complete` (if no other pending items).
    *   `hr_unmap_self(hr_user: User, db: AsyncIOMotorDatabase) -> User`:
        *   Validates HR is currently mapped.
        *   Clears `admin_manager_id` and sets `hr_status` to `profile_complete` for the HR user.
    *   `admin_unmap_hr(admin_user: User, hr_id: ObjectId, db: AsyncIOMotorDatabase) -> User`:
        *   Validates Admin is unmapping an HR they manage.
        *   Clears `admin_manager_id` and sets `hr_status` to `profile_complete` for the HR user.
        *   Handles re-assignment of candidates managed by the unmapped HR.
    *   `get_pending_applications_for_admin(admin_id: ObjectId, db: AsyncIOMotorDatabase) -> List[HRMappingRequestOutWithUserInfo]`: Fetches applications for an admin.
    *   `get_pending_requests_for_hr(hr_id: ObjectId, db: AsyncIOMotorDatabase) -> List[HRMappingRequestOutWithUserInfo]`: Fetches requests for an HR.

### 5.3. `ResumeParserService` (`app/services/resume_parser.py`)
Responsible for extracting raw text content from uploaded resume files.
*   **Purpose:** To provide a common interface for reading different resume file formats.
*   **Key Responsibilities & Methods:**
    *   `parse_resume(file_path: str, file_extension: str) -> str`:
        *   Takes a file path and its extension.
        *   Uses `pypdf` to extract text from PDF files.
        *   Uses `python-docx` to extract text from DOCX files.
        *   Returns the extracted raw text.
        *   Handles errors during file reading or parsing.

### 5.4. `ResumeAnalyzerService` (`app/services/resume_analyzer_service.py`)
Analyzes extracted resume text to identify skills, estimate years of experience, and potentially other structured data.
*   **Purpose:** To convert unstructured resume text into structured data usable for searching and filtering.
*   **Key Responsibilities & Methods:**
    *   `analyze_resume(resume_text: str) -> ResumeAnalysisResult`:
        *   Takes raw resume text as input.
        *   Calls `extract_skills` and `extract_experience_years`.
        *   Returns a `ResumeAnalysisResult` object containing `extracted_skills_list` and `estimated_yoe`.
    *   `extract_skills(resume_text: str) -> List[str]`:
        *   Uses NLP techniques (e.g., spaCy for Named Entity Recognition, keyword matching against a predefined skill list) to identify technical skills, soft skills, etc.
        *   Returns a list of unique skills found.
    *   `extract_experience_years(resume_text: str) -> Optional[float]`:
        *   Uses NLP (e.g., spaCy for date entity recognition) and pattern matching (regex with `python-dateutil`) to find employment date ranges.
        *   Calculates the total duration of work experience.
        *   Returns an estimated total years of experience.

### 5.5. `SearchService` (`app/services/search_service.py`)
Implements logic for searching and ranking candidates and HR profiles based on various criteria.
*   **Purpose:** To provide advanced search capabilities beyond simple database queries, incorporating relevance scoring.
*   **Key Responsibilities & Methods:**
    *   `search_candidates(db: AsyncIOMotorDatabase, current_user: User, keyword: Optional[str], skills: Optional[List[str]], yoe_min: Optional[float], status_filter: Optional[CandidateMappingStatus], limit: int, skip: int) -> List[RankedCandidate]`:
        *   Constructs a MongoDB query based on filters:
            *   `keyword`: Performs a text search on `resume_text` (requires text index).
            *   `skills`: Filters by `extracted_skills_list` (e.g., `$all` operator).
            *   `yoe_min`: Filters by `estimated_yoe >= yoe_min`.
            *   `status_filter`: Filters by `mapping_status`.
        *   Retrieves matching candidate profiles.
        *   Calculates a `relevance_score` for each candidate based on how well they match the criteria (e.g., text search score, number of matching skills, YOE proximity).
        *   Sorts results by relevance score.
        *   Returns a list of `RankedCandidate` objects.
    *   `search_hr_profiles(db: AsyncIOMotorDatabase, current_user: User, keyword: Optional[str], yoe_min: Optional[float], status_filter: Optional[HRStatus], limit: int, skip: int) -> List[RankedHR]`:
        *   Similar to `search_candidates` but for HR profiles (`role="hr"`).
        *   Filters by `hr_status`, `keyword` in HR resume, `estimated_yoe` or manually entered `years_of_experience`.
        *   Calculates relevance and returns `RankedHR` objects.
    *   `_calculate_relevance_score(...)`: (Private helper) Contains the logic for scoring matches.

## 6. Security Considerations

### 6.1. Authentication
*   JWT (JSON Web Tokens) are used for stateless authentication.
*   Access tokens have a configurable expiration time (`ACCESS_TOKEN_EXPIRE_MINUTES`).
*   Passwords are hashed using `bcrypt` via `passlib`.
*   HTTPS should be enforced in production to protect tokens in transit.

### 6.2. Authorization (RBAC)
*   Role-based access control is implemented using FastAPI dependencies.
*   Specific endpoints require specific roles (Admin, HR, Candidate).
*   Resource ownership is checked where applicable (e.g., a candidate can only access their own interviews, or an HR can only manage candidates assigned to them).

### 6.3. Input Validation
*   Pydantic models are used for strict validation of all incoming request data (bodies, query params, path params).
*   This helps prevent common vulnerabilities like injection attacks (though ORM/ODM helps too) and ensures data integrity.
*   File uploads are validated for type and size.

### 6.4. LLM Interaction Security
*   The Gemini API key is stored securely as an environment variable and not exposed to the client.
*   Prompts sent to the LLM are constructed carefully on the backend to avoid prompt injection from user-supplied data if possible, or sanitized.
*   Safety settings for the Gemini API are configured to block harmful content generation.

### 6.5. File Uploads
*   Resumes are stored with unique filenames (e.g., `user_id_uuid.ext`) to prevent overwrites and direct path traversal if names were user-controlled.
*   Upload directory (`uploads/`) should ideally be outside the web server's document root or have direct script execution disabled.
*   Consider virus scanning for uploaded files in a production environment.

### 6.6. CORS (Cross-Origin Resource Sharing)
*   CORS is configured via `CORSMiddleware` to allow requests only from specified frontend origins (`CORS_ALLOWED_ORIGINS`).

### 6.7. Dependency Management
*   Regularly update dependencies (`requirements.txt`) to patch known vulnerabilities. Use tools like `pip-audit` or Snyk.

### 6.8. Error Handling & Logging
*   Sensitive information should not be leaked in error messages or logs.
*   Comprehensive logging helps in auditing and incident response.

## 7. Deployment Strategy

### 7.1. Environment Configuration
*   Application settings (database URL, JWT secret, API keys) are managed via environment variables (loaded from a `.env` file in development, set directly in production environments).
*   Pydantic Settings (`app.core.config.Settings`) are used for loading and validating these.

### 7.2. Containerization (Docker)
*   A `Dockerfile` is provided to build a container image for the backend application.
*   `docker-compose.yml` can be used to orchestrate the backend service along with a MongoDB instance for local development and testing.
*   **Dockerfile Example Outline:**
    ```dockerfile
    FROM python:3.9-slim
    WORKDIR /app
    COPY requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt
    COPY ./app /app/app
    # COPY ./uploads /app/uploads # Or use a volume
    EXPOSE 8000
    CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
    ```

### 7.3. Production Deployment
*   **ASGI Server:** Uvicorn with multiple worker processes (e.g., `uvicorn app.main:app --workers 4`).
*   **Process Manager:** A process manager like Gunicorn (managing Uvicorn workers) or Supervisor can be used to ensure the application runs reliably.
    *   Example with Gunicorn: `gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app`
*   **Reverse Proxy:** Nginx or Traefik is recommended as a reverse proxy in front of the Uvicorn/Gunicorn server. It can handle:
    *   HTTPS termination (SSL/TLS).
    *   Load balancing if multiple instances of the backend are run.
    *   Serving static files (though less relevant for a pure API backend).
    *   Rate limiting and basic security filtering.
*   **Database:** A managed MongoDB service (like MongoDB Atlas) is recommended for production for scalability, backups, and maintenance.
*   **File Storage:** For uploaded resumes, consider using a cloud storage solution (AWS S3, Google Cloud Storage) in production for better scalability, durability, and potentially CDN integration, instead of local disk storage. The `UPLOAD_DIR` would then point to a mount or be handled via SDKs.
*   **Logging:** Centralized logging (e.g., ELK stack, Grafana Loki, CloudWatch Logs) should be set up.
*   **Monitoring:** Application performance monitoring (APM) tools (e.g., Datadog, New Relic, Prometheus/Grafana) and health checks.

## 8. Scalability and Performance

### 8.1. Asynchronous Operations
*   FastAPI's asynchronous nature, along with `async/await` and asynchronous libraries (Motor, aiofiles, httpx), allows the backend to handle many concurrent requests efficiently without blocking.

### 8.2. Database Optimization
*   Proper indexing on MongoDB collections is crucial for query performance (as detailed in Section 3.2).
*   Connection pooling is managed by Motor.
*   For very high read loads, consider MongoDB read replicas.

### 8.3. Caching
*   **LLM Responses:** Responses from the Gemini API (e.g., generated questions for common job roles) could be cached (e.g., using Redis or an in-memory cache with TTL) to reduce API calls and latency, especially for non-personalized content.
*   **User Data:** Frequently accessed, rarely changing user data could be cached.
*   **Configuration:** Application settings are loaded once at startup.

### 8.4. Horizontal Scaling
*   The stateless nature of the API allows for running multiple instances of the backend application behind a load balancer.
*   MongoDB can be scaled horizontally using sharding if necessary.

### 8.5. LLM API Rate Limits
*   Be mindful of Google Gemini API rate limits. Implement retry mechanisms with exponential backoff for API calls.
*   Caching (as mentioned above) can help mitigate hitting rate limits.

## 9. Testing Strategy

### 9.1. Unit Tests
*   Focus on testing individual functions, methods, and classes in isolation.
*   Mock external dependencies like database calls (Motor) and Gemini API calls (`unittest.mock` or `pytest-mock`).
*   Test business logic in services, utility functions in `core`, and Pydantic model validation.
*   Location: `tests/unit/` (hypothetical, current structure is flat in `tests/`)

### 9.2. Integration Tests
*   Test interactions between components, such as API endpoints calling services, and services interacting with a test database.
*   Use FastAPI's `TestClient` (which uses `httpx`) to make requests to the API.
*   A separate test database instance is used, potentially seeded with test data and cleaned up after tests. The `pytest-mongodb` plugin or custom fixtures can manage this.
*   Test authentication, authorization, request/response validation, and core workflows.
*   Location: `tests/integration/` (hypothetical) or directly in `tests/` as currently structured (e.g., `test_auth.py`, `test_admin.py`).

### 9.3. End-to-End (E2E) Tests
*   While primarily focused on the backend, some E2E tests could simulate client interactions if a simple client script is used.
*   More commonly, E2E tests are driven from the frontend testing suite (e.g., Cypress, Playwright) interacting with a deployed backend. (Outside backend scope, but good to be aware of).

### 9.4. Tools
*   **Pytest:** Primary testing framework.
*   **pytest-asyncio:** For testing asynchronous code.
*   **pytest-mock:** For mocking dependencies.
*   **httpx (via TestClient):** For API integration testing.
*   **Faker:** For generating realistic test data.
*   **Coverage.py:** To measure test coverage.

### 9.5. Test Environment
*   Use a separate configuration for testing (e.g., different database name, disabled external calls by default unless specifically testing them).
*   The `TESTING_MODE` flag in settings can control behavior (e.g., skip seeding real default data).

## 10. Error Handling and Logging

### 10.1. Error Handling
*   FastAPI provides default JSON error responses for HTTPExceptions.
*   Custom exception handlers can be defined for specific error types to provide more detailed or structured error responses if needed.
*   Service layer functions should raise specific custom exceptions (e.g., `UserNotFoundError`, `InvalidOperationError`) that can be caught in the API layer and translated into appropriate HTTPExceptions.
*   Avoid exposing raw tracebacks or sensitive internal details in production error responses.

### 10.2. Logging
*   Standard Python `logging` module is used.
*   Configure log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL) via environment variables.
*   Log important events: application startup/shutdown, API requests (method, path, status code, latency), errors and exceptions, key business logic steps (e.g., user registration, interview creation, LLM calls).
*   Log format should be structured (e.g., JSON) for easier parsing by log management systems. Include timestamp, log level, module/function name, message, and relevant context (e.g., user ID, request ID).
*   In production, logs should be sent to a centralized logging system.

## 11. Future Enhancements / Considerations

*   **Advanced Candidate Ranking:** Implement more sophisticated NLP techniques and machine learning models for candidate ranking based on resume content, job description match, and potentially other factors.
*   **Real-time Notifications:** Use WebSockets or Server-Sent Events (SSE) for real-time notifications (e.g., new message, interview invitation, HR mapping status change).
*   **ATS/HRIS Integration:** Develop connectors or webhooks to integrate with popular Applicant Tracking Systems or HR Information Systems.
*   **Interview Feedback Analysis:** Use LLMs to analyze aggregated feedback from multiple interviewers to identify patterns or biases.
*   **Question Variety & Difficulty Control:** More fine-grained control over question generation, including ensuring variety and dynamically adjusting difficulty based on candidate performance.
*   **Bulk Operations:** Add API endpoints for bulk actions (e.g., bulk candidate import, bulk assignment).
*   **Internationalization (i18n) and Localization (l10n):** Support for multiple languages in UI and LLM interactions.
*   **Accessibility (a11y):** Ensure API design choices do not hinder frontend accessibility.

## 12. Operational Considerations

### 12.1. Monitoring
*   **Application Metrics:** Track request rates, error rates, response latencies (overall and per-endpoint).
*   **System Metrics:** Monitor CPU, memory, disk, and network usage of backend servers and database.
*   **LLM API Metrics:** Monitor Gemini API call latency, error rates, and token usage.
*   **Database Performance:** Monitor MongoDB query performance, connection counts, replication lag.
*   **Health Checks:** Implement a `/health` endpoint that checks connectivity to the database and other critical services.

### 12.2. Alerting
*   Set up alerts for critical errors (e.g., high error rates, LLM API failures, database down).
*   Alert on performance degradation or resource exhaustion.

### 12.3. Backups and Recovery
*   Regular automated backups of the MongoDB database.
*   Regular backups of the resume file storage.
*   Test disaster recovery procedures.

### 12.4. API Key Management
*   Securely store and manage API keys (Gemini, etc.). Use a secrets management system in production (e.g., HashiCorp Vault, AWS Secrets Manager, Google Secret Manager).
*   Rotate API keys periodically.

## 13. Glossary

*   **API:** Application Programming Interface.
*   **ATS:** Applicant Tracking System.
*   **CRUD:** Create, Read, Update, Delete.
*   **CORS:** Cross-Origin Resource Sharing.
*   **FastAPI:** A modern, fast (high-performance) web framework for building APIs with Python 3.7+ based on standard Python type hints.
*   **HRIS:** Human Resources Information System.
*   **JWT:** JSON Web Token. A standard for securely transmitting information between parties as a JSON object.
*   **LLM:** Large Language Model (e.g., Google Gemini).
*   **MongoDB:** A NoSQL document-oriented database.
*   **Motor:** Asynchronous Python driver for MongoDB.
*   **NLP:** Natural Language Processing.
*   **ODM:** Object-Document Mapper.
*   **Pydantic:** A Python library for data validation and settings management using Python type hints.
*   **RBAC:** Role-Based Access Control.
*   **RESTful:** Representational State Transfer - an architectural style for designing networked applications.
*   **SDK:** Software Development Kit.
*   **SPA:** Single-Page Application.
*   **Uvicorn:** An ASGI server for Python.
*   **YoE:** Years of Experience.

## 14. Document History

| Version | Date       | Author        | Changes                                      |
| :------ | :--------- | :------------ | :------------------------------------------- |
| 1.0     | 2024-MM-DD | System Design | Initial Draft                                |
| 1.1     | 2024-MM-DD | AI Assistant  | Expanded API, Data, Security, Deployment etc.|

</final_file_content>

IMPORTANT: For any future changes to this file, use the final_file_content shown above as your reference. This content reflects the current state of the file, including any auto-formatting (e.g., if you used single quotes but the formatter converted them to double quotes). Always base your SEARCH/REPLACE operations on this final version to ensure accuracy.

<environment_details>
# VSCode Visible Files
C:/Users/babhi/AppData/Local/Programs/Microsoft VS Code/extension-output-formulahendry.code-runner-#1-Code
C:/Users/babhi/AppData/Local/Programs/Microsoft VS Code/perform_git_rewrite.ps1
C:/Users/babhi/AppData/Local/Programs/Microsoft VS Code/perform_git_rewrite.ps1
temp_systemdesign.md

# VSCode Open Tabs
add_pydantic_titles.py
server/app/schemas/admin.py
server/app/api/routes/admin.py
server/Dockerfile
docker-compose.yml
Readme.md
.gitignore
perform_git_rewrite.ps1
temp_api_integration_test.sh
temp_systemdesign.md
temp_dockerignore.txt
temp_env.txt
temp_env_example.txt
temp_gitignore.txt
temp_pytest_ini.txt
temp_requirements_dev.txt
temp_requirements.txt
temp_readme.txt
temp_dockerfile.txt
c:/Users/babhi/AppData/Local/Programs/Microsoft VS Code/perform_git_rewrite.ps1
server/app/core/schema_utils.py
server/app/schemas/interview.py
server/app/schemas/user.py

# Current Time
5/13/2025, 10:21:19 PM (Asia/Calcutta, UTC+5.5:00)

# Context Window Usage
940,987 / 1,048.576K tokens used (90%)

# Current Mode
ACT MODE
</environment_details>
