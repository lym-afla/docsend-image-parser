import requests
import os
import time

class DocSendImageDownloader:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-GB,en;q=0.9,en-US;q=0.8',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://docsend.com/',
            'X-CSRF-Token': 'Z_uo3cPmS5BBkC6rtGQZg2ebC3AvcxLy4GNPFjOHi3IsWChrM4oGokvyjwGjgRjZSuNpinKLwkCUvpaXKyZ5cg'
        }
        self.base_url = 'https://docsend.com'
        
        # Set cookies from your browser session
        self.session.cookies.set('_v_', '55%2B5mSXUwg8fLUfNWXv5IyrP%2FsbdFNH%2B9HR7r%2F8TjD8ij7%2Fc1BjNzJ7cpM2bDkk0JVj2B2exZvfuiKrMsZEj4RXMBNngyvKGgLhUJZ%2BdzC9qvZRCiA%3D%3D--XBZlDun08qCSUm%2Bx--2jFQJhKd7cOPxHJBDShtWQ%3D%3D')
        self.session.cookies.set('_dss_', 'b3b25fd4db284ce60bd6c8f7c3b26668')
        self.session.cookies.set('intercom-id-lv6lji7h', '6b5eaac1-5baa-4607-98f9-7b2b6d84c08c')
        self.session.cookies.set('intercom-device-id-lv6lji7h', '802fb9cc-8b6d-4927-8d23-4587794d1989')
        self.session.cookies.set('__Secure-dbx_consent', '{"consentType":1,"consentDate":"2025-03-18T15:20:34.466Z","expireDate":"2025-09-18T15:20:34.466Z","consentMonths":6,"categories":{"strictly necessary":true,"general marketing and advertising":false,"analytics":false,"performance and functionality":false,"social media advertising":false},"userInteracted":true,"numDots":1}')
        self.session.cookies.set('_us_', 'eyJfcmFpbHMiOnsibWVzc2FnZSI6IkluWnBaWGRsWkNCa2IyTWkiLCJleHAiOm51bGwsInB1ciI6ImNvb2tpZS5fdXNfIn19--d99e89135b29409ec95f7b01021ec543a463b2ba')
        
    def get_page_data(self, document_id, view_id, page_number):
        """Get page data from DocSend API"""
        url = f'{self.base_url}/view/{document_id}/d/{view_id}/page_data/{page_number}'
        params = {
            'viewLoadTime': int(time.time()),
            'timezoneOffset': 10800  # You might want to make this dynamic
        }
        
        try:
            response = self.session.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching page data: {e}")
            if hasattr(e.response, 'text'):
                print(f"Response content: {e.response.text}")
            return None

    def download_image(self, image_url, output_dir, page_number):
        """Download image from the provided URL"""
        try:
            response = self.session.get(image_url, headers=self.headers)
            response.raise_for_status()
            
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate filename from URL or use page number
            filename = f'page_{page_number}.jpg'
            filepath = os.path.join(output_dir, filename)
            
            # Save the image
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            print(f"Successfully downloaded image for page {page_number}")
            return filepath
        except requests.exceptions.RequestException as e:
            print(f"Error downloading image: {e}")
            if hasattr(e.response, 'text'):
                print(f"Response content: {e.response.text}")
            return None

    def download_document_images(self, document_id, view_id, start_page=1, end_page=None, output_dir='downloaded_images'):
        """Download images from a DocSend document"""
        page = start_page
        while True:
            if end_page and page > end_page:
                break
                
            print(f"Processing page {page}...")
            page_data = self.get_page_data(document_id, view_id, page)
            
            if not page_data:
                print(f"No data found for page {page}")
                break
                
            if 'imageUrl' in page_data:
                image_url = page_data['imageUrl']
                self.download_image(image_url, output_dir, page)
            else:
                print(f"No image URL found for page {page}")
                break
                
            page += 1
            time.sleep(1)  # Add delay to avoid rate limiting

def main():
    # Example usage
    downloader = DocSendImageDownloader()
    
    # Document ID and view ID from the network requests
    document_id = "4czrsfv6iketzu76"
    view_id = "dummy"
    output_dir = 'Zephyr_teaser'
    end_page = 3
    
    # Download images from pages 1 to 10 (adjust as needed)
    downloader.download_document_images(
        document_id=document_id,
        view_id=view_id,
        start_page=1,
        end_page=end_page,
        output_dir=f'downloaded_images/{output_dir}'
    )

if __name__ == "__main__":
    main() 