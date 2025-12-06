"""
Network Request Checker Agent
-----------------------------
This script checks if a specific file/URL gets loaded when visiting a website.
Now includes: status codes, errors, and initiator call stacks.

Usage:
    python script_locator.py

How it works:
    1. Opens a browser (headless by default)
    2. Uses Chrome DevTools Protocol for detailed network monitoring
    3. Captures status codes, errors, and initiator info
    4. Reports detailed results
"""

from playwright.sync_api import sync_playwright
import sys
import json


def check_if_file_loads(website_url: str, file_to_find: str, headless: bool = True) -> dict:
    """
    Check if a specific file gets loaded when visiting a website.
    Returns detailed info including status, errors, and initiator call stack.
    """
    
    # Store detailed request info (keyed by request ID)
    captured_requests = {}
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        
        # =============================================
        # CDP (Chrome DevTools Protocol) for full info
        # =============================================
        client = page.context.new_cdp_session(page)
        client.send("Network.enable")
        
        # --- CAPTURE REQUEST + INITIATOR ---
        def on_request_will_be_sent(params):
            request_id = params.get("requestId")
            request = params.get("request", {})
            initiator = params.get("initiator", {})
            
            captured_requests[request_id] = {
                "url": request.get("url"),
                "method": request.get("method"),
                # Initiator info (who triggered this request)
                "initiator_type": initiator.get("type"),  # script, parser, other
                "initiator_url": initiator.get("url"),
                "initiator_stack": initiator.get("stack"),  # Full call stack!
                # Will be filled by response/error handlers
                "status": None,
                "status_text": None,
                "error": None,
                "blocked_reason": None,
            }
        
        # --- CAPTURE RESPONSE STATUS ---
        def on_response_received(params):
            request_id = params.get("requestId")
            response = params.get("response", {})
            if request_id in captured_requests:
                captured_requests[request_id]["status"] = response.get("status")
                captured_requests[request_id]["status_text"] = response.get("statusText")
                captured_requests[request_id]["mime_type"] = response.get("mimeType")
        
        # --- CAPTURE FAILURES/ERRORS ---
        def on_loading_failed(params):
            request_id = params.get("requestId")
            if request_id in captured_requests:
                captured_requests[request_id]["error"] = params.get("errorText")
                captured_requests[request_id]["canceled"] = params.get("canceled", False)
                captured_requests[request_id]["blocked_reason"] = params.get("blockedReason")
        
        # Register CDP event handlers
        client.on("Network.requestWillBeSent", on_request_will_be_sent)
        client.on("Network.responseReceived", on_response_received)
        client.on("Network.loadingFailed", on_loading_failed)
        
        # --- VISIT THE WEBSITE ---
        print(f"🌐 Visiting: {website_url}")
        page.goto(website_url, wait_until="networkidle")
        page.wait_for_timeout(2000)
        
        browser.close()
    
    # --- FIND MATCHING REQUESTS ---
    matching = {
        rid: data for rid, data in captured_requests.items() 
        if file_to_find in (data.get("url") or "")
    }
    
    return {
        "found": len(matching) > 0,
        "matching_requests": matching,
        "total_requests": len(captured_requests)
    }


def format_call_stack(stack):
    """Format the initiator call stack for readable output."""
    if not stack:
        return "  (no call stack available)"
    
    lines = []
    call_frames = stack.get("callFrames", [])
    for i, frame in enumerate(call_frames[:5]):  # Show top 5 frames
        func_name = frame.get("functionName") or "(anonymous)"
        url = frame.get("url", "")
        line = frame.get("lineNumber", "?")
        col = frame.get("columnNumber", "?")
        # Shorten URL for display
        short_url = url.split("/")[-1] if url else "(unknown)"
        lines.append(f"  {i+1}. {func_name} @ {short_url}:{line}:{col}")
    
    if len(call_frames) > 5:
        lines.append(f"  ... and {len(call_frames) - 5} more frames")
    
    return "\n".join(lines) if lines else "  (empty stack)"


def check_multiple_files(website_url: str, files_to_find: list, headless: bool = True):
    """Check if multiple files load on a website."""
    results = {}
    for file_url in files_to_find:
        print(f"\n🔍 Checking: {file_url}")
        results[file_url] = check_if_file_loads(website_url, file_url, headless)
    return results


def main():
    # ============================================
    # CONFIGURE YOUR CHECK HERE
    # ============================================
    
    website_url = "http://racewaynissan.com/"
    file_to_find = "https://store-plugin.revolutionparts.com/?hash=7d1745c8ead9a4d12d7fdd61e62bd3de"
    headless = True
    
    # ============================================
    
    print("=" * 60)
    print("🔍 NETWORK REQUEST CHECKER (with CDP)")
    print("=" * 60)
    print(f"Website:     {website_url}")
    print(f"Looking for: {file_to_find}")
    print("=" * 60)
    
    result = check_if_file_loads(website_url, file_to_find, headless)
    
    print(f"\n📊 Total requests captured: {result['total_requests']}")
    
    if result["found"]:
        print(f"\n✅ SUCCESS! Found {len(result['matching_requests'])} matching request(s):\n")
        
        for rid, data in result["matching_requests"].items():
            print("-" * 60)
            print(f"📄 URL: {data['url']}")
            print(f"   Method: {data['method']}")
            
            # Status info
            if data["status"]:
                status_emoji = "✅" if 200 <= data["status"] < 400 else "⚠️"
                print(f"   Status: {status_emoji} {data['status']} {data['status_text']}")
            
            # Error info (if any)
            if data["error"]:
                print(f"   ❌ Error: {data['error']}")
            if data["blocked_reason"]:
                print(f"   🚫 Blocked: {data['blocked_reason']}")
            
            # Initiator info
            print(f"\n   📍 Initiator Type: {data['initiator_type']}")
            if data["initiator_url"]:
                print(f"   📍 Initiator URL: {data['initiator_url']}")
            
            print(f"\n   📚 Call Stack:")
            print(format_call_stack(data["initiator_stack"]))
            print()
    else:
        print(f"\n❌ NOT FOUND - The file was not loaded on this page.")
        print("\n💡 Possible reasons:")
        print("   - The script URL might be different")
        print("   - The script might be conditionally loaded")
        print("   - The script might load on a different page")
    
    return result["found"]


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
