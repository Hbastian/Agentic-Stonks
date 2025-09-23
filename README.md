
# Flask + Gradio + OpenAI Starter (PyCharm-ready, Commented)

This template shows how to:
- Run a **Flask** web server
- Mount a **Gradio** user interface at `/gradio`
- Call the **OpenAI API** to generate code from prompts
- Keep secrets safe with `.env` and `.gitignore`

## Prereqs
- Python **3.10+** recommended
- An **OpenAI API key** (from https://platform.openai.com/)

## Quick Start (Terminal)
```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # then put your real key in .env
python app.py
# Visit: http://127.0.0.1:5000/ and http://127.0.0.1:5000/gradio
```

## PyCharm
- Open folder, install deps from `requirements.txt`.
- Create Run Config for `app.py`.
- Either store `OPENAI_API_KEY` in `.env` or in Run Config environment variables.

## Secrets
- `.gitignore` excludes `.env` so keys won't be committed.
- Each teammate keeps their own `.env` locally.
- Share `.env.example` only.
