# DocSend Image Downloader

This script allows you to download images from DocSend documents by simulating browser requests and compile them into a PDF with optional OCR (Optical Character Recognition).

## 🔐 Authentication Required

**Important**: DocSend requires proper authentication. If you get a 403 Forbidden error, you need to provide fresh authentication cookies from your browser session.

### Quick Setup for Authentication

1. **Run the helper script** to get detailed instructions:
   ```bash
   python get_cookies_helper.py
   ```

2. **Follow the browser steps** to extract cookies:
   - Open your DocSend document in browser
   - Complete any authentication steps (email verification, etc.)
   - Open Developer Tools (F12)
   - Go to Application/Storage → Cookies → docsend.com
   - Copy the important cookies: `_v_`, `_dss_`, `_us_`

3. **Update your script** with the cookies:
   ```python
   cookies = {
       '_v_': 'your_actual_cookie_value',
       '_dss_': 'your_actual_cookie_value',
       '_us_': 'your_actual_cookie_value',
   }
   ```

## How It Works

The script works by:
1. Making authenticated requests to DocSend's API to get page data
2. Extracting image URLs from the page data
3. Downloading the images using the extracted URLs
4. (Optional) Compiling the downloaded images into a single PDF
5. (Optional) Adding OCR text layer for searchable PDFs

## Features

### PDF Creation Options
- **Simple PDF**: Images only (smallest file size)
- **Searchable PDF (Default)**: Uses Tesseract OCR for excellent quality/size balance ⭐ **RECOMMENDED**
- **Premium OCR PDF**: Uses OCRmyPDF for maximum OCR quality (larger files)

### OCR Quality Comparison
| Method | File Size | OCR Quality | Speed | Best For |
|--------|-----------|-------------|-------|----------|
| No OCR | Smallest | None | Fastest | Quick viewing |
| **Tesseract (Default)** | **Medium** | **Excellent** | **Fast** | **Most use cases** ⭐ |
| OCRmyPDF Premium | Largest | Maximum | Slower | Critical text extraction |

## Required Parameters

To use this script with a new DocSend document, you'll need:

1. **Document ID**: Found in the URL path
   - Example: `93wdni8fvi9ch8pd` from `https://docsend.com/view/93wdni8fvi9ch8pd/d/...`

2. **View ID**: Found in the URL path after `/d/`
   - Example: `gss34jz44akupkjr` from `https://docsend.com/view/.../d/gss34jz44akupkjr/...`

3. **Authentication Cookies**: Fresh cookies from your browser session
   - `_v_` (session cookie)
   - `_dss_` (DocSend session)
   - `_us_` (user session)

## 🔧 How to Get Authentication Cookies

### Method 1: Using the Helper Script
```bash
python get_cookies_helper.py
```
This will create a template file and show detailed instructions.

### Method 2: Manual Browser Extraction
1. Open your DocSend document in browser
2. Complete any authentication steps (email verification, etc.)
3. Open Developer Tools (F12)
4. Go to Application/Storage tab
5. Expand Cookies → https://docsend.com
6. Copy the values for: `_v_`, `_dss_`, `_us_`

### Method 3: From Network Tab
1. Open Developer Tools (F12)
2. Go to Network tab
3. Refresh the page
4. Find any request to docsend.com
5. Right-click → Copy → Copy as cURL
6. Extract cookies from the cURL command

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Install Tesseract OCR:
   - **Windows**: Download from [Tesseract Wiki](https://github.com/UB-Mannheim/tesseract/wiki)
   - **macOS**: `brew install tesseract`
   - **Linux**: `apt install tesseract-ocr`

3. (Optional) For premium OCR, install OCRmyPDF dependencies:
   - **Windows**: `choco install ghostscript unpaper`
   - **macOS**: `brew install ocrmypdf`
   - **Linux**: `apt install ocrmypdf`

## Usage

### Quick Start
1. **Get your cookies** (see authentication section above)
2. **Update the script** with your document info and cookies:
   ```python
   # In docsend_to_pdf.py
   document_id = "your_document_id"
   view_id = "your_view_id"
   document_name = "Your Document Name"
   
   cookies = {
       '_v_': 'your_cookie_value',
       '_dss_': 'your_cookie_value',
       '_us_': 'your_cookie_value',
   }
   ```
3. **Run the script**:
   ```bash
   python docsend_to_pdf.py
   ```

### Advanced Usage
You can also use the individual components:

```bash
# Download images only
python docsend_image_downloader.py

# Create PDF from downloaded images
python compile_to_pdf.py
```

## Configuration Options

In `docsend_to_pdf.py`, you can configure:

```python
# Document settings
document_id = "your_document_id"
view_id = "your_view_id"
document_name = "Your Document Name"
end_page = 14  # Set to None for all pages

# Authentication
cookies = {
    '_v_': 'your_cookie_value',
    '_dss_': 'your_cookie_value',
    '_us_': 'your_cookie_value',
}

# OCR settings
use_ocr = True  # Set to False for simple PDF without OCR
use_premium_ocr = False  # Set to True for OCRmyPDF (premium quality)
language = 'eng'  # OCR language: 'eng', 'fra', 'deu', 'spa', etc.
```

### OCR Mode Selection:
- **`use_ocr = False`**: Creates simple PDF with images only
- **`use_ocr = True, use_premium_ocr = False`**: Uses Tesseract (recommended) ⭐
- **`use_ocr = True, use_premium_ocr = True`**: Uses OCRmyPDF (premium quality)

## Output Files

The script creates different output files based on your settings:
- `document_name.pdf` - Simple PDF without OCR
- `document_name_searchable.pdf` - Tesseract OCR (recommended)
- `document_name_searchable_premium.pdf` - OCRmyPDF premium quality

## Troubleshooting

### 403 Forbidden Error
This is the most common issue. It means your authentication has failed.

**Solution:**
1. Get fresh cookies from your browser (see authentication section)
2. Make sure you've completed any email verification steps
3. Try accessing the document in an incognito/private browser window first
4. Update the cookies in your script

### Common Issues:
1. **"Tesseract not found"**: Install Tesseract OCR for your operating system
2. **"OCRmyPDF failed"**: Use default Tesseract mode instead (recommended)
3. **Authentication errors**: Update cookies and CSRF token from fresh browser session
4. **Permission denied**: Close any PDF viewers before running the script

### Tips:
- Start with Tesseract OCR (default) - it provides the best balance of quality and file size
- Only use premium OCR if you need maximum text extraction accuracy
- Check that your document subfolder name matches the downloaded images folder
- **Cookies expire** - you may need to refresh them periodically

## Notes

- **Tesseract OCR** is now the default and recommended method for most use cases
- The script includes a 0.5-second delay between requests to avoid rate limiting
- Images are saved in the `downloaded_images` directory by default
- The script will automatically create output directories if they don't exist
- **Authentication tokens and cookies may expire**, requiring updates from your browser session
- The PDF compilation script automatically sorts images by page number
- Images in PDFs are scaled to fit pages while maintaining aspect ratio
- All PDFs are created in regular PDF format (fully editable, not PDF/A)

## Error Handling

The script includes comprehensive error handling and will:
- Print detailed error messages if requests fail
- Show response content for debugging
- Skip pages that don't contain images
- Stop when it reaches the end of the document or specified page limit
- Handle missing or corrupted images during PDF compilation
- Automatically fall back between OCR methods if needed
- Install missing Python dependencies automatically
- Provide clear authentication error messages
