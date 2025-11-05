import requests
import os
import time
import json
from urllib.parse import urlparse, parse_qs

class DocSendImageDownloader:
    def __init__(self, cookies=None, user_agent=None):
        """
        Initialize DocSend image downloader with authentication
        
        Args:
            cookies (dict): Dictionary of cookies from browser session
            user_agent (str): User agent string (optional)
        """
        self.session = requests.Session()
        
        # Set default headers that mimic a real browser
        self.headers = {
            'User-Agent': user_agent or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://docsend.com/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Connection': 'keep-alive',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"'
        }
        
        self.base_url = 'https://docsend.com'
        
        # Set cookies if provided
        if cookies:
            for name, value in cookies.items():
                self.session.cookies.set(name, value, domain='.docsend.com')
        
        # Initialize without hardcoded cookies - they should be provided by user
    
    def extract_document_info_from_url(self, docsend_url):
        """
        Extract document_id and view_id from a DocSend URL
        
        Args:
            docsend_url (str): Full DocSend URL
            
        Returns:
            tuple: (document_id, view_id) or (None, None) if parsing fails
        """
        try:
            # Parse the URL
            parsed = urlparse(docsend_url)
            path_parts = parsed.path.strip('/').split('/')
            
            # DocSend URL format: /view/{document_id}/d/{view_id}
            if len(path_parts) >= 4 and path_parts[0] == 'view':
                document_id = path_parts[1]
                view_id = path_parts[3]
                return document_id, view_id
            else:
                print("❌ Could not parse DocSend URL. Expected format: https://docsend.com/view/{document_id}/d/{view_id}")
                return None, None
        except Exception as e:
            print(f"❌ Error parsing URL: {e}")
            return None, None
    
    def get_page_data(self, document_id, view_id, page_number):
        """Get page data from DocSend API"""
        if view_id:
            url = f'{self.base_url}/view/{document_id}/d/{view_id}/page_data/{page_number}'
        else:
            url = f'{self.base_url}/view/{document_id}/page_data/{page_number}'
        params = {
            'viewLoadTime': int(time.time()),
            'timezoneOffset': int(time.timezone / 3600) * 3600  # Dynamic timezone offset
        }
        
        try:
            response = self.session.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                print(f"❌ 403 Forbidden - Authentication required!")
                print("💡 Please provide fresh cookies from your browser session.")
                print("   See instructions in the README for how to get cookies.")
            elif e.response.status_code == 404:
                print(f"❌ 404 Not Found - Page {page_number} doesn't exist")
            else:
                print(f"❌ HTTP Error {e.response.status_code}: {e}")
            if hasattr(e.response, 'text'):
                print(f"Response content: {e.response.text}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching page data: {e}")
            return None

    def download_image(self, image_url, output_dir, page_number):
        """Download image from the provided URL"""
        try:
            response = self.session.get(image_url, headers=self.headers)
            response.raise_for_status()
            
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate filename from URL or use page number
            filename = f'page_{page_number:03d}.jpg'
            filepath = os.path.join(output_dir, filename)
            
            # Save the image
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            print(f"✅ Downloaded page {page_number}")
            return filepath
        except requests.exceptions.RequestException as e:
            print(f"❌ Error downloading image for page {page_number}: {e}")
            raise

    def download_document_images(self, document_id, view_id, start_page=1, end_page=None, output_dir='downloaded_images'):
        """Download images from a DocSend document"""
        print(f"🔍 Starting download for document {document_id}")
        print(f"📁 Output directory: {output_dir}")
        
        downloaded_count = 0
        page = start_page
        
        while True:
            if end_page and page > end_page:
                break
                
            print(f"📄 Processing page {page}...")
            page_data = self.get_page_data(document_id, view_id, page)
            
            if not page_data:
                print(f"❌ No data found for page {page} - stopping download")
                break
                
            if 'imageUrl' in page_data:
                image_url = page_data['imageUrl']
                try:
                    result = self.download_image(image_url, output_dir, page)
                    if result:
                        downloaded_count += 1
                except requests.exceptions.RequestException as e:
                    print(f"❌ No data found for page {page} - stopping download")
                    break
            else:
                print(f"❌ No image URL found for page {page} - stopping download")
                break
                
            page += 1
            time.sleep(0.5)  # Small delay to be respectful to the server
        
        print(f"🎉 Download complete! Downloaded {downloaded_count} pages.")
        return downloaded_count

def get_cookies_from_browser():
    """
    Instructions for getting cookies from browser
    """
    print("\n" + "="*60)
    print("🔐 AUTHENTICATION SETUP REQUIRED")
    print("="*60)
    print("DocSend requires authentication. Follow these steps:")
    print()
    print("1. Open your browser and go to the DocSend document")
    print("2. Complete any authentication steps (email verification, etc.)")
    print("3. Open Developer Tools (F12)")
    print("4. Go to Application/Storage tab")
    print("5. Look for Cookies under the docsend.com domain")
    print("6. Copy the following cookies:")
    print("   - _v_")
    print("   - _dss_")
    print("   - _us_")
    print("   - Any other cookies that look important")
    print()
    print("Then update the cookies in your script or pass them as parameters.")
    print("="*60)

def main():
    """Example usage with authentication"""
    
    # Check if we have proper authentication
    print("🔍 DocSend Image Downloader")
    print("=" * 40)
    
    # You can either:
    # 1. Update the cookies here directly
    # 2. Pass them as parameters when creating the downloader
    
    # Option 1: Update cookies here (replace with your fresh cookies)
    cookies = {
        # 'cookie_name': 'cookie_value',
        # Add your cookies here after getting them from browser
    }
    
    # Option 2: Create downloader with cookies
    if cookies:
        downloader = DocSendImageDownloader(cookies=cookies)
    else:
        print("⚠️  No cookies provided - authentication will likely fail")
        get_cookies_from_browser()
        return
    
    # Extract document info from URL or specify manually
    docsend_url = "https://docsend.com/view/93wdni8fvi9ch8pd/d/gss34jz44akupkjr"
    document_id, view_id = downloader.extract_document_info_from_url(docsend_url)
    
    if not document_id or not view_id:
        print("❌ Could not extract document information from URL")
        return
    
    print(f"📄 Document ID: {document_id}")
    print(f"👁️  View ID: {view_id}")
    
    # Download images
    output_dir = 'downloaded_images/test_document'
    downloader.download_document_images(
        document_id=document_id,
        view_id=view_id,
        start_page=1,
        end_page=5,  # Adjust as needed
        output_dir=output_dir
    )

if __name__ == "__main__":
    main() 