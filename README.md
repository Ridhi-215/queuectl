<<<<<<< HEAD

# queuectl

# ![CI](https://github.com/Ridhi-215/queuectl/actions/workflows/ci.yml/badge.svg)

# 🧩 QueueCTL — CLI-Based Background Job Queue System

> > > > > > > 25ad085 (docs: add CI badge to README)

A **Python-based background job queue system** with CLI control, worker processes, automatic retries (exponential backoff), and a Dead Letter Queue (DLQ).  
Built as part of the **Flam Backend Internship Assignment**.

---

## 🚀 Features

- Enqueue and manage background jobs via CLI
- Multiple parallel worker processes
- Retry mechanism with **exponential backoff**
- **Dead Letter Queue (DLQ)** for permanently failed jobs
- Persistent job storage using **SQLite**
- Graceful worker shutdown
- Configurable retry count & backoff base
- Comprehensive test suite

---

## 🧠 Architecture Overview

┌────────────────────┐
│ CLI Interface │ ← queuectl (Python Click)
└───────┬────────────┘
│
▼
┌────────────────────┐
│ Job Manager Layer │ ← Handles enqueue, state transitions,
│ (manager.py) │ retries, DLQ management
└───────┬────────────┘
│
▼
┌────────────────────┐
│ Worker Processes │ ← Execute jobs (subprocess),
│ (worker.py) │ handle backoff & failure
└───────┬────────────┘
│
▼
┌────────────────────┐
│ Persistent Store │ ← SQLite database (queue.db)
│ (db.py) │
└────────────────────┘

### Job Lifecycle

| State        | Description                       |
| ------------ | --------------------------------- |
| `pending`    | Waiting for worker                |
| `processing` | Currently being executed          |
| `completed`  | Executed successfully             |
| `failed`     | Failed but retryable              |
| `dead`       | Permanently failed (moved to DLQ) |

---

## ⚙️ Setup Instructions

### 🧩 1. Clone the repository

powershell
git clone https://github.com/<your-username>/queuectl.git
cd queuectl

### 🐍 2. Create and activate a virtual environment

python -m venv venv
.\venv\Scripts\Activate.ps1

### 📦 3. Install dependencies

pip install -r requirements.txt

### 🏗️ 4. Initialize database (automatically created on first run)

## 💻 CLI Usage Examples (Windows PowerShell)

### 🧾 Enqueue a job

You can enqueue directly from a JSON file:

Create a simple job JSON

```powershell
[System.IO.File]::WriteAllText("job_hello.json", '{"id":"job1","command":"echo Hello from QueueCTL"}', (New-Object System.Text.UTF8Encoding $false))
```

Enqueue the job

```powershell
python cli.py enqueue --file job_hello.json
```

⚙️ Start worker(s)

### Start 2 workers

```powershell
python cli.py worker start --count 2
```

🛑 Stop workers

```powershell
python cli.py worker stop
```

📋 List jobs

```powershell
python cli.py list --state pending
```

🔁 Retry or check DLQ

```powershell
python cli.py dlq list
python cli.py dlq retry job1
```

⚙️ Change configuration

```powershell
python cli.py config set default_max_retries 5
python cli.py config set backoff_base 2
```

🔄 Retry & Backoff Logic

When a job fails, it is retried automatically using:

```
delay = (base) ^ (attempts) seconds
```

Example (base = 2):

Attempt 1 → delay = 2¹ = 2s  
Attempt 2 → delay = 2² = 4s  
Attempt 3 → delay = 2³ = 8s

After exceeding max_retries, job moves to the Dead Letter Queue.

💾 Persistence

All job data is stored in a local SQLite database:

```
src/queue.db
```

Jobs persist across restarts — stopping and restarting workers or the app will not lose job state.

🧪 Testing Instructions

A functional test suite is provided at tests/run_tests.py.

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

## 🧱 Project Structure

queuectl/
├── cli.py # Root launcher
├── src/
│ ├── queuectl/
│ │ ├── cli.py # CLI command definitions
│ │ ├── manager.py # Job enqueue, state handling
│ │ ├── worker.py # Worker processes
│ │ ├── db.py # SQLite database functions
│ │ └── utils.py # Helper utilities
│ └── queue.db # Persistent job store
├── tests/
│ └── run_tests.py # Automated validation script
└── README.md

## ⚖️ Assumptions & Trade-offs

Commands executed via subprocess — sandboxing not included (keep jobs safe).

SQLite chosen for simplicity and persistence.

No job priority or scheduling (can be extended easily).

Tested on Windows PowerShell (Python 3.11) and Ubuntu Linux.

Job timeout and logging are planned as optional enhancements.

## 🧮 Configuration Defaults

Key Default Description
default_max_retries 3 Retry count before DLQ
backoff_base 2 Exponential backoff base (seconds)

👨‍💻 Author

Guntur Ridhi
📧 gunturridhi@gmail.com

🔗 https://github.com/Ridhi-215
