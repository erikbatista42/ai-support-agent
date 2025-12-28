import os
import datetime
from zoneinfo import ZoneInfo
import airtable
from dotenv import load_dotenv
from xai_sdk import Client
from xai_sdk.chat import system, user, file, tool
import json
from playwright.sync_api import sync_playwright

load_dotenv()

client = Client(api_key=os.getenv("XAI_API_KEY"))


class Agent():
    
    def __init__(self, file_id: str, system_prompt: str, at_table_name:str):
        # Agent config
        self.file_id = file_id
        self.system_prompt = system_prompt
        
        # Airtable config
        self.at_table_name = at_table_name

        # Agent tools setup
        self.tools_map = None
        self.current_user_prompt = None


    def setup_tools(self):
        # Use xAI SDK's tool() helper function
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


    def run_with_tools(self, user_prompt: str):
        self.setup_tools()
        self.current_user_prompt = user_prompt

        # new chat with tools enabled
        tool_chat = client.chat.create(
            model="grok-4",
            tools=self.tool_definitions, # here are the tools you can use
            tool_choice="auto" # decide on your own when to use them
        )

        tool_chat.append(system(self.system_prompt))
        tool_chat.append(user(user_prompt, file(self.file_id)))

        response = tool_chat.sample()
        # print("RESPONSE TOOL CALLS-----", response.tool_calls)

        for tool_call in response.tool_calls:
            tool_name = tool_call.function.name

            if tool_name == "check_script_on_website":
                print("Using tool: check_script_on_website")
                # print(f"Using tool: {function_name}")
                function_args = json.loads(tool_call.function.arguments)
                # print(f"   Arguments: {function_args}")

                result = self.tools_map[tool_name](**function_args)
                return result

        print("Using tool: read_attachment")
        # If we get here, AI answered using built-in tools (like read_attachment)
        found_scripts_data = {
                        "tool_used": "read_attachment",
                        "read_attachment_tool_response": response.content,
                        "date_and_time": datetime.datetime.now(ZoneInfo("America/New_York")).strftime("%m/%d/%y at %I:%M %p"),
                        "user_prompt": self.current_user_prompt,     
                        "human_verified": "not yet",
                        "response_script_url": "",
                        "script_status": "",
                        "initiator": "",
                        "call_stack_summary": "",
                        "is_correct": "", 
                    }
        airtable_instance = airtable.Airtable(base_id=os.getenv("AIRTABLE_BASE_ID"), api_key=os.getenv("AIRTABLE_API_KEY"))
        airtable_instance.create(table_name=self.at_table_name, data=found_scripts_data)
        print(f"AGENT RESPONSE: {response.content}")
        return response.content


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
                call_stack_chat.append(system(f"You are professional web developer. Your job is to review the call stack information and tell me in one concise sentence where the script originates from. So your answer should look like this: 'This script orignates from the GTM-XYZ'. Don't be limited to this exact same answer. Review the script's call stack and provide an accurate answer. If the script's call stack is empty, it means that it originated from the website. So say 'this script originated from {website_url}"))

                call_stack_summarized = call_stack_chat.append(
                    user(f"Tell me where this script is origninating from using the call stack information: {str(call_stack)}")).sample()

                found_scripts_data = {
                        "tool_used": "check_script_on_website",
                        "read_attachment_tool_response": "",
                        "response_script_url": response.url,
                        "script_status": str(response.status),
                        "initiator": response.frame.url if response.frame else "Unknown",
                        "call_stack_summary": call_stack_summarized.content,

                        "user_prompt": self.current_user_prompt,
                        "website_checked": website_url,         
                        "date_and_time": datetime.datetime.now(ZoneInfo("America/New_York")).strftime("%m/%d/%y at %I:%M %p"),  
                        "human_verified": "not yet",
                        "is_correct": "",   
                    }

                found_scripts.append(found_scripts_data)
                
                # Send data found to Airtable
                airtable_instance = airtable.Airtable(base_id=os.getenv("AIRTABLE_BASE_ID"), api_key=os.getenv("AIRTABLE_API_KEY"))
                airtable_instance.create(table_name=self.at_table_name, data=found_scripts_data)
            
        if not found_scripts:
            print(f"No matching scripts found for '{script_to_find}' on {website_url}")
            
            # Log "no scripts found" to Airtable
            no_scripts_data = {
                "tool_used": "check_script_on_website",
                "read_attachment_tool_response": "",
                "response_script_url": f"No match for: {script_to_find}",
                "script_status": "not found",
                "initiator": "",
                "call_stack_summary": "",
                "user_prompt": self.current_user_prompt,
                "website_checked": website_url,
                "date_and_time": datetime.datetime.now(ZoneInfo("America/New_York")).strftime("%m/%d/%y at %I:%M %p"),
                "human_verified": "not yet",
                "is_correct": "",
            }
            airtable_instance = airtable.Airtable(base_id=os.getenv("AIRTABLE_BASE_ID"), api_key=os.getenv("AIRTABLE_API_KEY"))
            airtable_instance.create(table_name=self.at_table_name, data=no_scripts_data)

        else:
            for script in found_scripts:
                print(f"Script URL: {script["response_script_url"]}")
                print(f"Status: {script["script_status"]}")
                print(f"Initiator: {script["initiator"]}")
                print(f"Call stack summary: {script["call_stack_summary"]}")

        return found_scripts

if __name__ == "__main__":
    agent = Agent(
        file_id="file_94997443-9e80-4386-a116-ee55a256aa7a", 
        system_prompt="You are an information agent. When the user wants to verify a script on a website, use the check_script_on_website tool. IMPORTANT: Always use the exact URLs listed in the document for the 'script_to_find' parameter - do not modify or guess different URLs.",
        at_table_name="agent_logs"
        )

    ''' sample prompt to ask about integration details '''
    # How does the Featurebase integration work?

    '''sample prompt to verify integration'''
    # check in https://pixel-verse-sample.netlify.app/ if the Featurebase integration is connected on the website.
    user_input = input("Ask about integrations within Erik's Site Builder: \n \n")

    print("Agent running...")
    result = agent.run_with_tools(user_input)
    # print(result)