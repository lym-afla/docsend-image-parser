#!/usr/bin/env python3
"""
Test script to verify DocSend authentication before running full download
"""

import json
import os
from docsend_image_downloader import DocSendImageDownloader

def load_cookies_from_template():
    """Load cookies from the template file"""
    if not os.path.exists('cookies_template.json'):
        print("❌ cookies_template.json not found")
        print("💡 Run 'python get_cookies_helper.py' first")
        return None
    
    try:
        with open('cookies_template.json', 'r') as f:
            data = json.load(f)
        return data.get('cookies', {})
    except json.JSONDecodeError:
        print("❌ Error reading cookies_template.json")
        return None

def test_authentication(document_id, view_id, cookies):
    """Test if authentication works for a specific document"""
    print(f"🔍 Testing authentication for document {document_id}")
    print(f"👁️  View ID: {view_id}")
    print()
    
    # Create downloader with cookies
    downloader = DocSendImageDownloader(cookies=cookies)
    
    # Try to get page 1 data
    print("📄 Testing page 1 access...")
    page_data = downloader.get_page_data(document_id, view_id, 1)
    
    if page_data:
        print("✅ Authentication successful!")
        print(f"📊 Page data keys: {list(page_data.keys())}")
        if 'imageUrl' in page_data:
            print(f"🖼️  Image URL found: {page_data['imageUrl'][:50]}...")
        return True
    else:
        print("❌ Authentication failed!")
        print("💡 Please check your cookies and try again")
        return False

def main():
    """Main test function"""
    print("🧪 DocSend Authentication Test")
    print("=" * 40)
    print()
    
    # Load cookies from template
    cookies = load_cookies_from_template()
    if not cookies:
        return
    
    # Check if cookies are set
    valid_cookies = {k: v for k, v in cookies.items() if v != "YOUR_COOKIE_VALUE_HERE"}
    if not valid_cookies:
        print("❌ No valid cookies found in template")
        print("💡 Please edit cookies_template.json with your actual cookie values")
        return
    
    print("✅ Found cookies in template:")
    for name, value in valid_cookies.items():
        print(f"   {name}: {value[:20]}...")
    print()
    
    # Test with your document
    document_id = "93wdni8fvi9ch8pd"  # Update with your document ID
    view_id = "gss34jz44akupkjr"      # Update with your view ID
    
    print("📝 Using test document:")
    print(f"   Document ID: {document_id}")
    print(f"   View ID: {view_id}")
    print("💡 Update these values in the script if testing a different document")
    print()
    
    # Test authentication
    success = test_authentication(document_id, view_id, valid_cookies)
    
    if success:
        print("\n🎉 Authentication test passed!")
        print("✅ You can now run the full download script")
        print("💡 Run: python docsend_to_pdf.py")
    else:
        print("\n❌ Authentication test failed!")
        print("💡 Please:")
        print("   1. Get fresh cookies from your browser")
        print("   2. Update cookies_template.json")
        print("   3. Make sure you have access to the document")

if __name__ == "__main__":
    main() 