# System Data Flow & Architecture

This document clarifies how data moves from your sensors to your dashboard and why `backend.py` is required.

## 1. The Data Pipeline

The system uses a **Central Database** (MongoDB Atlas) to sync data between the Cloud and your Local Dashboard.

```mermaid
graph TD
    subgraph "Field / Sensors"
        Sensors[ESP32 / Sensors] -->|MQTT| VM[GCP Virtual Machine]
    end

    subgraph "Cloud Infrastructure"
        VM -->|Insert Data| DB[(MongoDB Atlas Cloud DB)]
    end

    subgraph "Your Local Computer"
        DB -->|Fetch Data| Backend[backend.py (Port 5000)]
        Backend -->|JSON API| Frontend[React Dashboard (Port 5173)]
    end
```

## 2. Why `backend.py` is Mandatory

Your React Frontend (**Port 5173**) is just a visual interface running in your browser. It **cannot** connect directly to the MongoDB Cloud Database for security reasons (you cannot store database passwords in frontend code).

Instead, it relies on **`backend.py`** to act as a secure bridge.

1.  **`backend.py`** connects to the Cloud Database using your secure credentials.
2.  It queries the data (e.g., "Give me the last 7 days of logs").
3.  It serves this data at `http://localhost:5000/api/...`.
4.  The Frontend calls this API to render the charts.

**If `backend.py` is stopped, the bridge is broken, and the Frontend gets no data.**

## 3. How to View Cloud Data

To see the data from the cloud:

1.  Ensure your **GCP VM** is running and receiving data (which puts it in the DB).
2.  Run **`python app/backend.py`** locally. It will act as the "reader" for that Cloud DB.
3.  Open your **Frontend**. It will ask `backend.py` for the data, which `backend.py` retrieves from the Cloud DB.
