# DocSend Image Downloader

This script allows you to download images from DocSend documents by simulating browser requests and compile them into a PDF with optional OCR (Optical Character Recognition).

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

4. Compile the downloaded images into a searchable PDF:
```bash
python compile_to_pdf.py
```

## Configuration Options

In `compile_to_pdf.py`, you can configure:

```python
def main():
    # Basic settings
    image_subfolder = 'your_document_name'
    use_ocr = True  # Set to False for simple PDF without OCR
    
    # OCR settings
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

## Notes

- **Tesseract OCR** is now the default and recommended method for most use cases
- The script includes a 1-second delay between requests to avoid rate limiting
- Images are saved in the `downloaded_images` directory by default
- The script will automatically create output directories if they don't exist
- Authentication tokens and cookies may expire, requiring updates from your browser session
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

## Troubleshooting

### Common Issues:
1. **"Tesseract not found"**: Install Tesseract OCR for your operating system
2. **"OCRmyPDF failed"**: Use default Tesseract mode instead (recommended)
3. **Authentication errors**: Update cookies and CSRF token from fresh browser session
4. **Permission denied**: Close any PDF viewers before running the script

### Tips:
- Start with Tesseract OCR (default) - it provides the best balance of quality and file size
- Only use premium OCR if you need maximum text extraction accuracy
- Check that your document subfolder name matches the downloaded images folder
