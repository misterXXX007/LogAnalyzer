# 🚀 Spark Log Analytics Service

A distributed log processing service built with FastAPI, Celery, and Redis. This service provides an API for ingesting and analyzing Apache Spark log data asynchronously.

## ✨ Features

- **Asynchronous Processing**: Built with Celery for efficient background task processing
- **Idempotent Operations**: Safe for retries without duplicate processing
- **Out-of-Order Processing**: Handles log events regardless of their arrival order
- **Enhanced Logging**: Detailed logging for debugging and monitoring
- **RESTful API**: Clean, well-documented endpoints for all operations
- **Real-time Analytics**: Get insights into job performance and metrics
- **Persistent Storage**: SQLite database for reliable data persistence
- **Scalable Architecture**: Redis-backed task queue for horizontal scaling

## ⚠️ Current Limitations

- **Authentication**: Currently no authentication mechanism implemented
- **Rate Limiting**: No rate limiting implemented
- **Data Retention**: No automatic cleanup of old data
- **Load Testing**: Not yet load tested for production workloads

## 🛠 Tech Stack

| Component | Technology |
|-----------|------------|
| **API Framework** | [FastAPI](https://fastapi.tiangolo.com/) |
| **Task Queue** | [Celery](https://docs.celeryq.dev/) |
| **Message Broker** | [Redis](https://redis.io/) |
| **Database** | [SQLite](https://www.sqlite.org/) |
| **Containerization** | [Docker](https://www.docker.com/) |
| **Python Version** | 3.10+ |


## 🗂 Project Structure

```
src/
├── __init__.py
├── main.py                 # FastAPI application entry point
├── celery_worker.py        # Celery worker configuration
├── data/                   # Sample data and test fixtures
├── database/
│   └── sqlite.py           # Database configuration and session management
├── models/
│   └── logs.py             # SQLAlchemy models for logs and analytics
├── routes/
│   └── logs.py             # API routes and endpoint handlers
├── service/
│   └── logs.py             # Interface to interact with database
├── tasks/
│   └── processor.py        # Celery tasks for async processing
└── utils/
    └── logs.py             # Utility functions for log handling
```




## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.10 or higher
- pip (Python package manager)

### Running with Docker (Recommended)

```bash
# Build and start all services
docker-compose up --build

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Local Development Setup

1. **Set up a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start Redis** (in a separate terminal)
   ```bash
   docker run -d -p 6379:6379 --name redis redis:7-alpine
   ```

4. **Initialize the database**
   ```bash
   python src/init_db.py
   ```

5. **Start the application**
   ```bash
   # Terminal 1 - FastAPI server
   cd src
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   
   # Terminal 2 - Celery worker
   celery -A src.celery_worker.celery_app worker --loglevel=info
   ```

The API will be available at http://localhost:8000

## 📚 API Documentation

Once the service is running, you can access:

- **Interactive API Docs**: http://localhost:8000/docs

## 📡 API Endpoints

### 📤 Ingest Logs
- **POST** `/logs/ingest`
  - Accepts Spark log events in JSON format
  - Returns a task ID for tracking

  **Example Request - Job Start:**
  ```bash
  curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": 1234567,
    "event": "SparkListenerJobStart",
    "timestamp": "2025-05-22T15:00:00Z",
    "user": "alice"
  }'
  ```

  **Example Response:**
  ```json
  {"status":"received","task_id":"5f32b63b-1818-4a4b-97ca-cedaf477c1c7"}
  ```

  **Example Request - Task End:**
  ```bash
  curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "event": "SparkListenerTaskEnd",
    "job_id": 1234567,
    "timestamp": "2025-05-22T15:05:00Z",
    "task_id": "task_006",
    "duration_ms": 1500,
    "successful": false
  }'
  ```

  **Example Request - Job End:**
  ```bash
  curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "event": "SparkListenerJobEnd",
    "job_id": 1234567,
    "timestamp": "2025-05-22T15:30:00Z",
    "completion_time": "2025-05-22T15:30:00Z",
    "job_result": "JobSucceeded"
  }'
  ```

### 🔍 Get Job Status
- **GET** `/analytics/jobs/{job_id}`
  - Get the current status and results of a specific job
  - Path parameter: `job_id` (string, required) - The ID of the job to retrieve
  
  **Example Request:**
  ```bash
  curl -X GET "http://localhost:8000/analytics/jobs/550e8400-e29b-41d4-a716-446655440000" -H "accept: application/json"
  ```
  
  **Possible Responses:**
  
  *While job is processing (HTTP 202):*
  ```json
  {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "processing"
  }
  ```
  
  *When job is complete (HTTP 200):*
  ```json
  {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "success",
    "result": {
      "job_id": 12345,
      "status": "success",
      "start_time": "2025-05-22T10:30:00Z",
      "end_time": "2025-05-22T10:35:00Z",
      "duration_seconds": 300,
      "total_tasks": 100,
      "failed_tasks": 2,
      "success_rate": 0.98
    }
  }
  ```
  
  **Response Fields:**
  
  | Field | Type | Description |
  |-------|------|-------------|
  | `task_id` | String | The ID of the task being checked |
  | `status` | String | Current status (`processing` or `success`) |
  | `result` | Object | (Only present when complete) Detailed job results |
  | `result.job_id` | Integer | Spark job ID |
  | `result.status` | String | Final job status (`success` or `failure`) |
  | `result.start_time` | String | ISO 8601 timestamp of job start |
  | `result.end_time` | String | ISO 8601 timestamp of job completion |
  | `result.duration_seconds` | Float | Total job duration in seconds |
  | `result.total_tasks` | Integer | Total number of tasks in the job |
  | `result.failed_tasks` | Integer | Number of failed tasks |
  | `result.success_rate` | Float | Success rate (0.0 to 1.0) |

### 📊 Get Analytics Summary
- **GET** `/analytics/summary`
  - Get summary of analytics for a specific date
  - Query parameter: `date` (format: YYYY-MM-DD)
  
  **Example Request:**
  ```bash
  curl -X GET "http://localhost:8000/analytics/summary?date=2025-05-22" -H "accept: application/json"
  ```
  
  **Response Fields:**
  
  | Field | Type | Description |
  |-------|------|-------------|
  | `date` | String | The date for which analytics are being returned (YYYY-MM-DD) |
  | `summary` | Object | Aggregated analytics for all jobs on the specified date |
  | `summary.total_jobs` | Integer | Total number of jobs processed on this date |
  | `summary.total_tasks` | Integer | Total number of tasks across all jobs |
  | `summary.failed_tasks` | Integer | Number of tasks that failed |
  | `summary.avg_success_rate` | Float | Average success rate across all jobs (0.0 to 1.0) |
  | `summary.avg_duration_seconds` | Float | Average job duration in seconds |
  | `jobs` | Array | Detailed information about each job |
  | `jobs[].job_id` | Integer | Unique identifier for the job |
  | `jobs[].user` | String | User who initiated the job |
  | `jobs[].start_time` | String | ISO 8601 timestamp when the job started |
  | `jobs[].end_time` | String | ISO 8601 timestamp when the job completed |
  | `jobs[].status` | String | Final status of the job (e.g., "success", "failed") |
  | `jobs[].task_count` | Integer | Total number of tasks in the job |
  | `jobs[].failed_tasks` | Integer | Number of failed tasks in the job |
  | `jobs[].success_rate` | Float | Success rate for the job (0.0 to 1.0) |
  | `jobs[].duration_seconds` | Integer | Total duration of the job in seconds |
  
  **Example Response:**
  ```json
  {
    "date": "2025-05-22",
    "summary": {
      "total_jobs": 1,
      "total_tasks": 1,
      "failed_tasks": 1,
      "avg_success_rate": 0.0,
      "avg_duration_seconds": 1800.0
    },
    "jobs": [
      {
        "job_id": 1234567,
        "user": "alice",
        "start_time": "2025-05-22T15:00:00Z",
        "end_time": "2025-05-22T15:30:00Z",
        "status": "success",
        "task_count": 1,
        "failed_tasks": 1,
        "success_rate": 0.0,
        "duration_seconds": 1800
      }
    ]
  }
  ```

### Get Job Analytics
- **GET** `/analytics/jobs/{job_id}`
  - Retrieve analytics for a specific Spark job
  - Example: `GET /analytics/jobs/1234567`

## Complete Workflow Example

1. **Start a job**
   ```bash
   curl -X POST http://localhost:8000/logs/ingest \
   -H "Content-Type: application/json" \
   -d '{"job_id": 1234567, "event": "SparkListenerJobStart", "timestamp": "2025-05-22T15:00:00Z", "user": "alice"}'
   ```

2. **Add task events**
   ```bash
   curl -X POST http://localhost:8000/logs/ingest \
   -H "Content-Type: application/json" \
   -d '{"event": "SparkListenerTaskEnd", "job_id": 1234567, "timestamp": "2025-05-22T15:05:00Z", "task_id": "task_001", "duration_ms": 1500, "successful": true}'
   ```

3. **Complete the job**
   ```bash
   curl -X POST http://localhost:8000/logs/ingest \
   -H "Content-Type: application/json" \
   -d '{"event": "SparkListenerJobEnd", "job_id": 1234567, "timestamp": "2025-05-22T15:30:00Z", "completion_time": "2025-05-22T15:30:00Z", "job_result": "JobSucceeded"}'
   ```

4. **View analytics**
   ```bash
   curl -X GET "http://localhost:8000/analytics/summary?date=2025-05-22" -H "accept: application/json"
   ```

