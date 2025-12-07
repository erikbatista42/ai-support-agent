# Technical Support Agent

Technical support agent where you can ask questions about your codebase and verify scripts on live websites.

## What It Does

1. **Ask questions** about a codebase (powered by Greptile)
2. **Extracts URLs** mentioned in answers (powered by Grok/xAI)
3. **Verifies scripts** are actually loading on target websites (Playwright + CDP)

## Tech Stack

| Component | Purpose |
|-----------|---------|
| **Greptile API** | Codebase semantic search |
| **xAI Grok** | URL extraction from natural language |
| **Playwright** | Browser automation with Chrome DevTools Protocol |
| **Gradio** | Chat UI |

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/ai-support-agent.git
cd ai-support-agent
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Configure API keys

Create a `.env` file in the project root:

```bash
XAI_API_KEY=your_xai_api_key_here
GREPTILE_API_KEY=your_greptile_api_key_here
```

### 4. Run the app

```bash
python app.py
```

Then open http://127.0.0.1:7860 in your browser.

## Usage

1. Enter a **website URL** in the input field (e.g., `https://example.com`)
2. Ask a question about script integrations (e.g., "How does the tracking script integrate?")
3. The agent will:
   - Search the codebase for relevant information
   - Extract any URLs mentioned in the answer
   - Verify if those URLs are actually loading on the target website
   - Report detailed results including HTTP status and call stacks

## Project Structure

```
ai-support-agent/
├── app.py              # Gradio chat UI
├── search_codebase.py  # Greptile + Grok integration
├── script_locator.py   # Playwright network monitoring
├── requirements.txt    # Python dependencies
└── .env                # API keys (not committed)
```

## How It Works

```
User Question
     │
     ▼
┌─────────────┐
│  Greptile   │  ─── Searches codebase for answer
└─────────────┘
     │
     ▼
┌─────────────┐
│  Grok/xAI   │  ─── Extracts URLs from answer
└─────────────┘
     │
     ▼
┌─────────────┐
│ Playwright  │  ─── Visits website, monitors network
│    + CDP    │      requests via Chrome DevTools
└─────────────┘
     │
     ▼
  Results
  (found/not found + details)
```

## License

MIT

