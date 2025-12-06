import os
from dotenv import load_dotenv
load_dotenv()

from xai_sdk import Client
from xai_sdk.chat import user, system, file

client = Client(api_key=os.getenv("XAI_API_KEY"), timeout=3600)

chat = client.chat.create(model="grok-4-1-fast")

# Get file content
content = client.files.content("file_35a96920-fa92-47a9-a7d9-68c60f11c9e3")

chat.append(system(f"You are Motive Support. Your goal is to help answer any Motive Admin platform questions. You will reference this documentation {content}. If you have found the answer in the documentation, don't say anything else, just reference the documentation. Make sure that you never reference the platform documentation and focus on answering questions here."))

chat.append(user("Where can I see a list of dealers?"))

response = chat.sample()
print(response.content)