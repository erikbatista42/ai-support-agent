import os
import requests
from rich.markdown import Markdown
from rich.console import Console

from dotenv import load_dotenv
load_dotenv()

from xai_sdk import Client
from xai_sdk.chat import user, system, file

client = Client(api_key=os.getenv("XAI_API_KEY"), timeout=3600)
xai_api_key = os.getenv("XAI_API_KEY")
greptile_api_key = os.getenv("GREPTILE_API_KEY")

# chat = client.chat.create(model="grok-4-1-fast")

# # Get file content
# content = client.files.content("file_35a96920-fa92-47a9-a7d9-68c60f11c9e3")

# chat.append(system(f"You are Motive Support. Your goal is to help answer any Motive Admin platform questions. You will reference this documentation {content}. If you have found the answer in the documentation, don't say anything else, just reference the documentation. Make sure that you never reference the platform documentation and focus on answering questions here."))

# chat.append(user("Where can I see a list of dealers?"))

# response = chat.sample()
# print(response.content)

# -------------
# Have the user ask a question like "how does the Gubagoo script work?" and it searches the codebase.
def index_repo(repo="erikbatista42/tiny-llm"):
    """Index a repo with Greptile (run once before querying)"""
    response = requests.post(
        "https://api.greptile.com/v2/repositories",
        headers={
            "Authorization": f"Bearer {greptile_api_key}",
            "Content-Type": "application/json"
        },
        json={
            "remote": "github",
            "repository": repo,
            "branch": "main"
        }
    )
    print("Index response:", response.status_code, response.json())
    return response.json()

# Run this FIRST (comment out after it succeeds)
# index_repo()

def ask_about_code(question, repo="erikbatista42/tiny-llm"):
    """Query codebase and get answer from Greptile"""
    response = requests.post(
        "https://api.greptile.com/v2/query",
        headers={
            "Authorization": f"Bearer {greptile_api_key}",
            "Content-Type": "application/json"
        },
        json={
            "messages": [{"role": "user", "content": question}],
            "repositories": [{"remote": "github", "repository": repo, "branch": "main"}]
        }
    )
    result = response.json()
    return result.get("message", "No answer found.")


console = Console()

answer = ask_about_code("How is the neural network implemented?")

console.print(Markdown(answer))