import os
import re
import requests
from dotenv import load_dotenv
from xai_sdk import Client
from xai_sdk.chat import system, user, file
from playwright.sync_api import sync_playwright


load_dotenv()

client = Client(api_key=os.getenv("XAI_API_KEY"))
chat = client.chat.create(model="grok-4")

def ask_file(prompt:str):
    agent_file_id = "file_6ed62445-f5fe-4478-a588-e7fc3c8a796c"
    
    chat.append(system("You are an information agent. Your job is to pick the closest integration section from the document we're looking at and provide the exact name, description and the list of URLs the integration contains."))
    chat.append(user(prompt, file(agent_file_id)))
    print("🔎 Agent is searching for answer...")
    response = chat.sample()
    print("ANSWER:\n")
    return response.content

def extract_urls_from_content(content):
    # given the content, grab the URLs and put it into a python list
    js_urls_in_content = re.findall(r'https?://[^\s"\'<>]+\.js', content)
    return js_urls_in_content

def check_script_on_website(website_url, script_to_find):
    # Check if a script URL loads on a website and show its initiator.

    all_responses = []
    request_initiators = {}

    with sync_playwright() as p:
        # Launch headless browser
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Get CDP(Chrome DevTools Protocol) session to capture call stacks
        cdp = page.context.new_cdp_session(page)
        cdp.send("Network.enable")

        # Capture initiator info including call stack
        def on_request_sent(event):
            url = event["request"]["url"]
            request_initiators[url] = event.get("initiator", {})

        cdp.on("Network.requestWillBeSent", on_request_sent)

        # Collect ALL requests into a list
        page.on("response", lambda res: all_responses.append(res))

        # Visit the website
        print(f"Checking {website_url}...")
        page.goto(website_url, wait_until="networkidle")
        browser.close()

    # print(f"ALL NETWORK REQUESTS: {all_responses}")

    # Now filter the requests to find matching scripts
    found_scripts = []
    for response in all_responses:
        if script_to_find in response.url:
            initiator_info = request_initiators.get(response.url, {})
            call_stack = initiator_info.get("stack", {}).get("callFrames", [])
            
            call_stack_chat = client.chat.create(model="grok-4-1-fast-reasoning")
            call_stack_chat.append(system("You are professional web developer. Your job is to review the call stack information and tell me in one concise sentence wehre the script originates from. So your answer should look like this: 'This script orignates from the GTM-XYZ'. Don't be limited to this same answer. Review the call stack script and provide an accurate answer."))

            call_stack_summarized = call_stack_chat.append(
                user(f"Tell me where this script is origninating from using the call stack information: {str(call_stack)}")).sample()

            found_scripts.append(
                {
                    "script_url": response.url,
                    "script_status": response.status,
                    "initiator": response.frame.url if response.frame else "Unknown",
                    "call_stack": call_stack_summarized.content
                }
            )
    for script in found_scripts:
        print(f"Script URL: {script["script_url"]}")
        print(f"Status: {script["script_status"]}")
        print(f"Initiator: {script["initiator"]}")
        print(f"Call stack summary: {script["call_stack"]}")
    return found_scripts


if __name__ == "__main__":
    content = ask_file("What does the srp integration do?")
    integration_urls = extract_urls_from_content(content)
    results = check_script_on_website(website_url="https://gooba.motivehq.site/", script_to_find=integration_urls[0])

