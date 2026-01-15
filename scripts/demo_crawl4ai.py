import asyncio
import json
import re
import sys
import os
from crawl4ai import AsyncWebCrawler

# Target URL (Real London Property)
PROPERTY_ID = "164254985"
URL = f"https://www.rightmove.co.uk/properties/{PROPERTY_ID}#/?channel=RES_BUY"
OUTPUT_FILE = "rightmove_full_data.json"

def extract_json_object(html_content, start_marker):
    """
    Robustly extracts a JSON object starting after 'start_marker' by counting braces.
    """
    start_idx = html_content.find(start_marker)
    if start_idx == -1:
        return None
    
    open_brace_idx = html_content.find("{", start_idx)
    if open_brace_idx == -1:
        return None

    balance = 0
    in_string = False
    escape = False
    
    for i in range(open_brace_idx, len(html_content)):
        char = html_content[i]
        
        if escape:
            escape = False
            continue
            
        if char == '\\':
            escape = True
            continue
            
        if char == '"' and not escape:
            in_string = not in_string
            continue
            
        if not in_string:
            if char == '{':
                balance += 1
            elif char == '}':
                balance -= 1
                if balance == 0:
                    return html_content[open_brace_idx : i+1]
    
    return None

async def main():
    print(f"🕷️  Crawling URL: {URL}...")
    
    js_extract_model = "return window.PAGE_MODEL;"

    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await crawler.arun(
            url=URL,
            js_code=js_extract_model,
            magic=True,
        )
        
        if not result.success:
            print(f"❌ Failed to crawl: {result.error_message}")
            return

        print("\n✅ Crawl Successful!")
        
        model_data = result.js_execution_result 
        
        if not model_data:
            print("⚠️ Direct JS capture returned None. Using Brace-Counting extraction...")
            json_str = extract_json_object(result.html, "window.PAGE_MODEL =")
            
            if json_str:
                try:
                    model_data = json.loads(json_str)
                    print("✅ Extraction successful!")
                except json.JSONDecodeError as e:
                    print(f"❌ Extracted text but failed to parse JSON: {e}")
            else:
                 print("❌ Could not find 'window.PAGE_MODEL =' or matching braces.")

        if model_data:
            # SAVE TO FILE
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(model_data, f, indent=2)
            
            print("="*50)
            print(f"� FULL DATA SAVED TO: {os.path.abspath(OUTPUT_FILE)}")
            print("="*50)
            
            # Print a recursive summary of the keys to give a "Comprehensive View" in the terminal
            print("\n📊 DATA STRUCTURE SUMMARY:")
            print_structure(model_data)

def print_structure(data, indent=0, max_depth=2):
    if indent > max_depth * 2:
        return
    
    spacing = " " * indent
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                type_name = "Array" if isinstance(value, list) else "Object"
                count = f"[{len(value)}]" if isinstance(value, list) else ""
                print(f"{spacing}- {key}: {type_name}{count}")
                # Recurse for core data fields we care about
                if indent == 0 or key in ["propertyData", "address", "prices", "location"]:
                    # Peek inside lists
                    if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                         print_structure(value[0], indent + 2, max_depth)
                    else:
                        print_structure(value, indent + 2, max_depth)
            else:
                # Leaf node - print sample if it's interesting (not None/Empty)
                if value:
                    val_str = str(value)
                    if len(val_str) > 50: val_str = val_str[:50] + "..."
                    print(f"{spacing}- {key}: {val_str}")

if __name__ == "__main__":
    asyncio.run(main())
