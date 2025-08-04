#!/usr/bin/env python3
"""
Helper script to get DocSend cookies from your browser
"""

import json
import os

def print_cookie_instructions():
    """Print detailed instructions for getting cookies"""
    print("🔐 DOCSEND COOKIE EXTRACTION GUIDE")
    print("=" * 60)
    print()
    print("Follow these steps to get your authentication cookies:")
    print()
    print("1. 🌐 Open your web browser (Chrome, Firefox, Edge, etc.)")
    print("2. 📄 Go to your DocSend document URL")
    print("3. ✅ Complete any authentication steps (email verification, etc.)")
    print("4. 🔧 Open Developer Tools:")
    print("   - Press F12, or")
    print("   - Right-click → Inspect, or")
    print("   - Ctrl+Shift+I (Windows/Linux) or Cmd+Option+I (Mac)")
    print()
    print("5. 📋 In Developer Tools:")
    print("   - Click on 'Application' tab (Chrome) or 'Storage' tab (Firefox)")
    print("   - In the left sidebar, expand 'Cookies'")
    print("   - Click on 'https://docsend.com'")
    print()
    print("6. 📝 Copy these important cookies:")
    print("   - _v_ (session cookie)")
    print("   - _dss_ (DocSend session)")
    print("   - _us_ (user session)")
    print("   - Any other cookies that look important")
    print()
    print("7. 💾 Update the cookies in your script")
    print()
    print("=" * 60)

def create_cookie_template():
    """Create a template file for cookies"""
    template = {
        "cookies": {
            "_v_": "YOUR_COOKIE_VALUE_HERE",
            "_dss_": "YOUR_COOKIE_VALUE_HERE", 
            "_us_": "YOUR_COOKIE_VALUE_HERE",
            # Add any other cookies you find
        },
        "document_url": "https://docsend.com/view/YOUR_DOCUMENT_ID/d/YOUR_VIEW_ID",
        "document_name": "Your Document Name",
        "end_page": 10
    }
    
    with open('cookies_template.json', 'w') as f:
        json.dump(template, f, indent=2)
    
    print("📄 Created cookies_template.json")
    print("💡 Edit this file with your actual cookie values")

def load_cookies_from_file(filename='cookies_template.json'):
    """Load cookies from a JSON file"""
    if not os.path.exists(filename):
        print(f"❌ File {filename} not found")
        return None
    
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        return data.get('cookies', {})
    except json.JSONDecodeError:
        print(f"❌ Error reading {filename}")
        return None

def extract_document_info_from_url(url):
    """Extract document ID and view ID from URL"""
    try:
        # Simple extraction - you might want to use urllib.parse for more robust parsing
        if '/view/' in url and '/d/' in url:
            parts = url.split('/')
            view_index = parts.index('view')
            d_index = parts.index('d')
            
            if view_index + 1 < len(parts) and d_index + 1 < len(parts):
                document_id = parts[view_index + 1]
                view_id = parts[d_index + 1]
                return document_id, view_id
    except:
        pass
    
    return None, None

def main():
    """Main function"""
    print("🍪 DocSend Cookie Helper")
    print("=" * 30)
    print()
    
    # Check if template exists
    if not os.path.exists('cookies_template.json'):
        print("📝 Creating cookie template file...")
        create_cookie_template()
        print()
    
    # Print instructions
    print_cookie_instructions()
    
    # Check if user has cookies
    cookies = load_cookies_from_file()
    if cookies and any(cookies.values()):
        print("✅ Found cookies in template file!")
        print("📋 Current cookies:")
        for name, value in cookies.items():
            if value != "YOUR_COOKIE_VALUE_HERE":
                print(f"   {name}: {value[:20]}...")
            else:
                print(f"   {name}: [NOT SET]")
    else:
        print("❌ No valid cookies found in template file")
        print("💡 Please edit cookies_template.json with your actual cookie values")

if __name__ == "__main__":
    main() 