# Agentic-Stonks

Agentic-Stonks is a web application that uses an AI agent (via the OpenAI API) to perform stock-related tasks. It provides an interactive user interface built with **Gradio**, served by a lightweight **Flask** backend.

---

## Features

* **AI Integration:** Connects directly to the **OpenAI API** for powerful agentic capabilities.
* **Interactive UI:** Powered by **Gradio** and mounted at the `/gradio` endpoint for easy experimentation.
* **Web Backend:** Built with **Flask**, providing a stable and scalable foundation.
* **Secure Configuration:** Uses `.env` files and `.gitignore` to keep your API keys safe and out of version control.

---

## Getting Started

Follow these instructions to get the project set up and running on your local machine.

### Prerequisites

* **Python 3.10+**
* **OpenAI API Key**: You must have an API key from [OpenAI Platform](https://platform.openai.com/).

### Installation & Setup

You can either use the automated `run.sh` script for macOS or follow the manual setup for any OS.

#### 1. macOS (Automated Setup)

This repository includes a `run.sh` script that automates the entire setup and execution process on macOS.

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/your-username/Agentic-Stonks.git](https://github.com/your-username/Agentic-Stonks.git)
    cd Agentic-Stonks
    ```

2.  **Create and configure your environment file:**
    ```bash
    cp .env.example .env
    ```
    Now, open the `.env` file with a text editor and paste your `OPENAI_API_KEY`.

3.  **Make the script executable:**
    This command only needs to be run once.
    ```bash
    chmod +x run.sh
    ```

4.  **Run the application:**
    Use this command every time you want to start the app.
    ```bash
    ./run.sh
    ```
    The script will automatically check for the correct Python version, create a virtual environment, install dependencies, and start the Flask server.

#### 2. Manual Setup (Windows / Linux)

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/your-username/Agentic-Stonks.git](https://github.com/your-username/Agentic-Stonks.git)
    cd Agentic-Stonks
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    # For Linux/macOS
    python3 -m venv .venv
    source .venv/bin/activate

    # For Windows
    python -m venv .venv
    .venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up environment variables:**
    ```bash
    cp .env.example .env
    ```
    Open the newly created `.env` file and add your `OPENAI_API_KEY`.

5.  **Run the application:**
    ```bash
    python app.py
    ```

---

## Usage

Once the server is running, the application will be accessible at the following addresses:

* **Flask Homepage:** `http://127.0.0.1:5000/`
* **Gradio Interface:** `http://127.0.0.1:5000/gradio`

---

## Configuration

All secret keys and environment specific settings are managed in the `.env` file. This file is **intentionally untracked** by Git (via `.gitignore`) to prevent leaking sensitive API keys.

* `.env.example`: A template file showing which variables are needed.
* `.env`: The local file you create to store your actual keys.

**Example `.env`:**
```ini
OPENAI_API_KEY='sk-YourActualKeyHere...'
