# QueueCTL — CLI-Based Background Job Queue System

A **Python-based background job queue system** with CLI control, worker processes, automatic retries (exponential backoff), and a Dead Letter Queue (DLQ).  
Built as part of the **Flam Backend Internship Assignment**.

---
## 🎥 Demo Video
Watch the full demo here: [Demo Link](https://drive.google.com/drive/folders/1pP9eG1tn2ltplAhTtFO6zKgYLfWrGU3G?usp=drive_link)

---

## Features

- Enqueue and manage background jobs via CLI
- Multiple parallel worker processes
- Retry mechanism with **exponential backoff**
- **Dead Letter Queue (DLQ)** for permanently failed jobs
- Persistent job storage using **SQLite**
- Graceful worker shutdown
- Configurable retry count & backoff base
- Comprehensive test suite

---

## Architecture Overview

┌────────────────────┐
│ CLI Interface      │ ← queuectl (Python Click)
└───────┬────────────┘
        │
        ▼
┌────────────────────┐
│ Job Manager Layer  │ ← Handles enqueue, state transitions,
│ (manager.py)       │ retries, DLQ management
└───────┬────────────┘
        │
        ▼
┌────────────────────┐
│ Worker Processes   │ ← Execute jobs (subprocess),
│ (worker.py)        │ handle backoff & failure
└───────┬────────────┘
        │
        ▼
┌────────────────────┐
│ Persistent Store   │ ← SQLite database (queue.db)
│ (db.py)            │
└────────────────────┘

---

## Job Lifecycle

| State        | Description                       |
| ------------ | --------------------------------- |
| `pending`    | Waiting for worker                |
| `processing` | Currently being executed          |
| `completed`  | Executed successfully             |
| `failed`     | Failed but retryable              |
| `dead`       | Permanently failed (moved to DLQ) |

---

## Setup Instructions

### 1. Clone the repository

```powershell
git clone https://github.com/<your-username>/queuectl.git
cd queuectl
```

### 2. Create and activate a virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Initialize database 

The database (src/queue.db) will be created automatically on the first run.
You can verify schema integrity using:
```powershell
python tests\check_schema.py
```


## CLI Usage Examples (Windows PowerShell)

### Enqueue a job

Create a simple job JSON

```powershell
[System.IO.File]::WriteAllText("tests/job_hello.json", '{"id":"job1","command":"echo Hello from QueueCTL","state":"pending","attempts":0,"max_retries":3,"created_at":"2025-11-08T10:30:00Z","updated_at":"2025-11-08T10:30:00Z"}', (New-Object System.Text.UTF8Encoding $false))
```

Enqueue the job:

```powershell
python cli.py enqueue --file tests/job_hello.json
```
List pending jobs:

```powershell
python cli.py list --state pending
```

⚙️ Start worker(s)

### Start Worker(s)

Start one or more workers:

```powershell
python cli.py worker start --count 2
```

Stop workers gracefully:

```powershell
python cli.py worker stop
```

### List jobs

```powershell
python cli.py list --state pending
```

### Check System Status

```powershell
python cli.py status
```

### Dead Letter Queue (DLQ)

View failed jobs:

```powershell
python cli.py dlq list
```
Retry a DLQ job:

```powershell
python cli.py dlq retry job1
```

### Configuration Management

```powershell
python cli.py config set default_max_retries 5
python cli.py config set backoff_base 2
python cli.py config get default_max_retries
```

---

## Retry & Backoff Logic

When a job fails, it is retried automatically using:

```
delay = (base) ^ (attempts) seconds
```

Example (base = 2):

Attempt 1 → delay = 2¹ = 2s  
Attempt 2 → delay = 2² = 4s  
Attempt 3 → delay = 2³ = 8s

After exceeding max_retries, job moves to the Dead Letter Queue.

---

## Persistence

All job data is stored in a local SQLite database:

```
src/queue.db
```
Data persists across restarts
You can verify a job’s state directly:
```
python tests\check_job.py
```
The schema includes:
```
id, command, state, attempts, max_retries, created_at, updated_at, last_error, stdout, stderr
```

---

## Testing Instructions

A functional test suite is provided at tests directory.

Run all automated tests:

```powershell
python tests\run_tests.py
```

You should see output similar to:

```
Test1 PASS: job completed: test-echo-1
Test2 PASS: job moved to DLQ: test-fail-1
Test3 PASS: multiple workers completed all jobs
Test4 PASS: job persisted in DB and pending

ALL TESTS PASSED ✅
```
You can also run individual test utilities:
```
python tests\check_schema.py    # Verify DB schema
python tests\reset_job.py       # Reset job to pending
python tests\check_job.py       # Inspect specific job record

```
---

## 🧱 Project Structure

```
queuectl/
├── cli.py                    # CLI root launcher
├── src/
│   ├── queuectl/
│   │   ├── cli.py            # CLI command definitions
│   │   ├── manager.py        # Job enqueue, state management
│   │   ├── worker.py         # Worker logic and backoff
│   │   ├── db.py             # SQLite interface
│   │   └── utils.py          # Helper utilities
│   └── queue.db              # Persistent store
├── tests/
│   ├── check_schema.py
│   ├── check_job.py
│   ├── reset_job.py
│   ├── job1.py
│   ├── job_hello.json
│   └── run_tests.py
└── README.md

```
---

## Assumptions & Trade-offs

Commands executed via subprocess — sandboxing not included (keep jobs safe).

SQLite chosen for simplicity and persistence.

No job priority or scheduling (can be extended easily).

Tested on Windows PowerShell (Python 3.11) and Ubuntu Linux.

Job timeout and logging are planned as optional enhancements.

## 🧮 Configuration Defaults

| Key                      | Default     |   Description               |
| -------------------------| ----------- |-----------------------------|
| `default_max_retries`    | 3           |   Maximum retry count       |
| `backoff_base`           | 2           |   Exponential backoff base  |


👨‍💻 Author

Guntur Ridhi

📧 gunturridhi@gmail.com

🔗 https://github.com/Ridhi-215



