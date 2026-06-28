# 🚀 Developer Portfolio AutoSync Agent

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python Badge" />
  <img src="https://img.shields.io/badge/Next.js-15+-000000?style=for-the-badge&logo=nextdotjs&logoColor=white" alt="Next.js Badge" />
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI Badge" />
  <img src="https://img.shields.io/badge/Turso-LibSQL-000000?style=for-the-badge&logo=sqlite&logoColor=fff" alt="Turso Badge" />
  <img src="https://img.shields.io/badge/Docker-Supported-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker Badge" />
</p>

An automated, modular agent that polls or receives webhooks for new GitHub repositories, extracts their metadata, uses LLMs to generate professional project descriptions, and automatically syncs them into your developer portfolio—complete with a real-time Next.js telemetry and approval dashboard.

---

## 🛠️ Features

* **Auto-Discovery**: Polls GitHub repositories or listens to webhooks to identify new project additions in real-time.
* **LLM-Powered Descriptions**: Utilizes OpenAI (GPT-4o) or Claude to extract technologies and generate clean, engaging summaries of projects.
* **Telemetrics Dashboard**: A modern Next.js dashboard featuring live logs, success rates, and sync statistics.
* **Interactive Approval Flow**: Visual diff approvals on the dashboard allow you to approve, customize, or reject updates before they are committed to production.
* **Instant Sync Trigger**: Trigger a synchronization cycle on-demand via the **"Run Sync Now"** dashboard button.
* **Persistent Turso Integration**: Fully backed by Turso libSQL to provide seamless, shared cloud-database state between the local agent and the deployed dashboard.
* **Docker Support**: Containerized configuration for simple, one-step deployment of the agent and dashboard.

---

## 📐 Architecture

> 🌐 **Interactive Diagram:** Open the interactive visual dashboard directly in your browser:  
> 👉 **[architecture.html](architecture.html)** (Double-click to inspect component APIs, configs, and file structures)

```
                 +-------------------+
                 |    GitHub API     |
                 +---------+---------+
                           |
                           v
+--------------------------+--------------------------+
|                  AutoSync Python Agent              |
|                                                     |
|  1. Detects new repos (Poll / Webhooks)             |
|  2. LLM extracts metadata & generates summaries     |
|  3. Posts pending changes & logs to Dashboard API   |
+--------------------------+--------------------------+
                           |
                           | HTTP GET/POST (REST)
                           v
+--------------------------+--------------------------+
|                     Next.js Dashboard               |
|                                                     |
|  - Telemetry logs & stats                           |
|  - UI to review and click 'Approve & Push'          |
|  - Database: Turso libSQL (Cloud)                   |
+-----------------------------------------------------+
                           |
                           | Merges, commits & pushes
                           v
+--------------------------+--------------------------+
|                  Developer Portfolio                |
|                    (Mock Portfolio)                 |
+-----------------------------------------------------+
```

> 💡 **Tip:** Open the [Interactive Architecture Diagram](file:///Users/saransh/vs%20code/Developer%20Portfolio%20AutoSync%20Agent/architecture.html) directly in your browser to inspect system components, databases, and key source files.

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.9+** and **Node.js 20+**
- A **GitHub Personal Access Token** (with `repo` permissions)
- A **Turso/libSQL database** and Auth Token
- An **OpenAI API Key** (for metadata generation)

### 2. Installation
Clone the repository and install the dependencies:

```bash
# Install Python virtual environment and packages
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Install Dashboard dependencies
cd dashboard
npm install
```

### 3. Configuration
Configure the agent and dashboard by editing the environment variables.

Create a [`.env`](file:///Users/saransh/vs%20code/Developer%20Portfolio%20AutoSync%20Agent/.env) file in the root directory:
```env
# GitHub Credentials
GITHUB_TOKEN=your-github-token

# LLM Credentials
OPENAI_API_KEY=your-openai-api-key

# Telemetry Dashboard URL
VERCEL_DASHBOARD_URL=https://developer-portfolio-auto-sync-agent.vercel.app

# Turso Cloud Database
TURSO_DATABASE_URL=libsql://your-db-route.turso.io
TURSO_AUTH_TOKEN=your-auth-token
```

Create a [`config.yaml`](file:///Users/saransh/vs%20code/Developer%20Portfolio%20AutoSync%20Agent/config.yaml) file:
```yaml
github:
  username: "your-github-username"
  poll_interval: 3600

portfolio:
  local_path: "./mock_portfolio"
  repo_url: "https://github.com/your-username/portfolio.git"
  branch: "det"
  structure_type: "json"
  file_path: "projects.json"

llm:
  provider: "openai"
  openai_model: "gpt-4o"
```

---

## 🏃 Running the Application

### Method A: Docker Compose (Recommended)
Launch the entire stack (telemetry server and dashboard) with a single command:
```bash
docker-compose up --build
```

### Method B: Manual Execution
1. **Start the Next.js Dashboard**:
   ```bash
   cd dashboard
   npm run dev
   ```
   *The dashboard will start on `http://localhost:3000`.*

2. **Start the Python Agent**:
   In another terminal tab, launch the agent in FastAPI webhook/serve mode:
   ```bash
   source .venv/bin/activate
   python3 main.py --serve
   ```
   *This starts the webhook receiver on port `8000` and automatically runs the daemon loop in the background, checking for dashboard sync requests every 10 seconds.*

---

## 📊 Dashboard Telemetry

The Next.js panel allows you to monitor and control the synchronization agent:
- **Execution Stream**: Real-time logging of repository discovery, LLM requests, and git merges.
- **Pending Review Queue**: Displays proposed changes (with visual green/red unified diffs).
- **Run Sync Now**: Instantly wakes up the local agent daemon to scan for updates on-demand.
