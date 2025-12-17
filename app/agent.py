import os
import re
import requests
import airtable
from dotenv import load_dotenv
from xai_sdk import Client
from xai_sdk.chat import system, user, file, tool
from playwright.sync_api import sync_playwright


load_dotenv()

client = Client(api_key=os.getenv("XAI_API_KEY"))
chat = client.chat.create(model="grok-4")


class Agent():
    
    def __init__(self, file_id: str, system_prompt: str, at_table_name:str):
        # Agent config
        self.file_id = file_id
        self.system_prompt = system_prompt
        
        # Airtable config
        self.at_table_name = at_table_name

        # Agent tools setup
        self.agent_tools = None
        self.tools_map = None

    def setup_tools(self):
        tool_definitions = [
            tool(
                name="check_script_on_website",
                description="Use this to VERIFY if a script/integration is loading correctly on a website",
                parameters={
                    "type": "object",
                    "properties": {
                        "website_url": {
                            "type": "string",
                            "description": "The URL of the website to check",
                            },
                        "script_to_find": {
                            "type": "string",
                            "description": "The script URL or partial name to search for",
                            },
                        },
                        "required": ["website_url", "script_to_find"]
                        }
                )
            ]
        
        tools_map = {
            "check_script_on_website": self.check_script_on_website
        }

        self.tool_definitions = tool_definitions
        self.tools_map = tools_map



    
    def ask_file(self, user_prompt:str, extract_urls=False):
        chat.append(system(self.system_prompt))
        chat.append(user(user_prompt, file(self.file_id)))

        print("🔎 AGENT IS SEARCHING FILE LOCATED IN xAI Collections...")
        response = chat.sample()
        print("RESPONSE FROM AGENT:\n ", response.content)

        if extract_urls:
            return self.extract_urls_from_content(response.content)
        
        return response.content

    def extract_urls_from_content(self, content):
        # given the content, grab the URLs and put it into a python list
        js_urls_in_content = re.findall(r'https?://[^\s"\'<>]+\.js', content)
        return js_urls_in_content


    def check_script_on_website(self, website_url, script_to_find):
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
                call_stack_chat.append(system("You are professional web developer. Your job is to review the call stack information and tell me in one concise sentence where the script originates from. So your answer should look like this: 'This script orignates from the GTM-XYZ'. Don't be limited to this exact same answer. Review the script's call stack and provide an accurate answer."))

                call_stack_summarized = call_stack_chat.append(
                    user(f"Tell me where this script is origninating from using the call stack information: {str(call_stack)}")).sample()

                found_scripts_data = {
                        "script_url": response.url,
                        "script_status": str(response.status),
                        "initiator": response.frame.url if response.frame else "Unknown",
                        "call_stack_summary": call_stack_summarized.content
                    }

                found_scripts.append(found_scripts_data)
                
                # Send data found to Airtable
                airtable_instance = airtable.Airtable(base_id=os.getenv("AIRTABLE_BASE_ID"), api_key=os.getenv("AIRTABLE_API_KEY"))
                airtable_instance.create(table_name=self.at_table_name, data=found_scripts_data)
            
        # for script in found_scripts:
        #     print(f"Script URL: {script["script_url"]}")
        #     print(f"Status: {script["script_status"]}")
        #     print(f"Initiator: {script["initiator"]}")
        #     print(f"Call stack summary: {script["call_stack_summary"]}")

        return found_scripts

if __name__ == "__main__":
    agent = Agent(
        file_id="file_5b1f18d6-1536-4514-85b1-c5afc4ecf000", 
        system_prompt="You are an information agent. Your job is to pick the closest integration section from the document we're looking at and provide the exact name, description and the list of URLs the integration has if it has any.",
        at_table_name="agent_logs"
        )

    get_user_intention = input("Say 'Verify' if you want to verify an integration. Otherwise, ask a question about any integration. \n \n")

    if get_user_intention == "Verify":
            integration_information_urls = agent.ask_file(user_prompt=get_user_intention, extract_urls=True)
            
            for url in integration_information_urls:
                result = agent.check_script_on_website(website_url="https://gooba.motivehq.site/", script_to_find=url)
                print(result) 
    else:
        integration_information = agent.ask_file(user_prompt=get_user_intention, extract_urls=False)
        print(integration_information)

    


    

    


    

