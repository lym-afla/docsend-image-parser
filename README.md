# DocSend Image Downloader

This script allows you to download images from DocSend documents by simulating browser requests and compile them into a PDF.

## How It Works

The script works by:
1. Making authenticated requests to DocSend's API to get page data
2. Extracting image URLs from the page data
3. Downloading the images using the extracted URLs
4. (Optional) Compiling the downloaded images into a single PDF

## Required Parameters

To use this script with a new DocSend document, you'll need to extract the following parameters from your browser's network requests:

1. **Document ID**: Found in the URL path
   - Example: `s9nwbcx2vp4ufckc` from `https://docsend.com/view/s9nwbcx2vp4ufckc/d/...`

2. **View ID**: Found in the URL path after `/d/`
   - Example: `hp6yg2mafaccxdwz` from `https://docsend.com/view/.../d/hp6yg2mafaccxdwz/...`

3. **Authentication Headers and Cookies**: Found in your browser's network requests
   - Open Chrome DevTools (F12)
   - Go to the Network tab
   - Find any request to `docsend.com`
   - Look for:
     - `X-CSRF-Token` in the request headers
     - Cookies in the request headers (especially `_v_`, `_dss_`, etc.)

## How to Get the Parameters

1. Open your DocSend document in Chrome
2. Open Chrome DevTools (F12)
3. Go to the Network tab
4. Refresh the page
5. Look for requests to `docsend.com`
6. Find a request to `/page_data/` endpoint
7. Copy the following:
   - Document ID and View ID from the URL
   - CSRF Token from request headers
   - Cookies from request headers

## Usage

1. Update the parameters in the `main()` function:
```python
document_id = "your_document_id"
view_id = "your_view_id"
```

2. Update the authentication headers and cookies in the `__init__` method:
```python
self.headers['X-CSRF-Token'] = 'your_csrf_token'
self.session.cookies.set('_v_', 'your_v_cookie')
# ... other cookies
```

3. Run the script to download images:
```bash
python docsend_image_downloader.py
```

4. (Optional) Compile the downloaded images into a PDF:
```bash
python compile_to_pdf.py
```

## Notes

- The script includes a 1-second delay between requests to avoid rate limiting
- Images are saved in the `downloaded_images` directory by default
- The script will automatically create the output directory if it doesn't exist
- Authentication tokens and cookies may expire, requiring updates from your browser session
- The PDF compilation script will automatically sort images by page number
- Images in the PDF are scaled to fit the page while maintaining aspect ratio

## Error Handling

The script includes error handling and will:
- Print detailed error messages if requests fail
- Show response content for debugging
- Skip pages that don't contain images
- Stop when it reaches the end of the document or specified page limit
<<<<<<< HEAD
- Handle missing or corrupted images during PDF compilation 
=======
- Handle missing or corrupted images during PDF compilation
>>>>>>> d828c94d8a73ee092b3fc12fa57ac1c606827863
