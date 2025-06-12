import os
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape
from reportlab.lib.units import inch, mm
import glob
import pytesseract
from PyPDF2 import PdfWriter, PdfReader
import io
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import Color

# Configure Tesseract path
def configure_tesseract():
    """Configure Tesseract path and verify installation"""
    tesseract_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        r'C:\Users\Public\Tesseract-OCR\tesseract.exe'
    ]
    
    # Try to find Tesseract executable
    for path in tesseract_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            print(f"Found Tesseract at: {path}")
            return True
    
    print("ERROR: Tesseract not found in common locations!")
    print("Please ensure Tesseract is installed and add its path to the script.")
    print("Download Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki")
    return False

def create_pdf_page(image_file, use_ocr=False):
    """
    Create a PDF page with the image and optionally add OCR text layer
    """
    # Open image and get dimensions
    img = Image.open(image_file)
    img_width, img_height = img.size
    
    # Convert pixels to points (1 point = 1/72 inch)
    margin = 2 * mm
    width_points = (img_width * 72.0 / img.info.get('dpi', (300,300))[0]) + margin
    height_points = (img_height * 72.0 / img.info.get('dpi', (300,300))[1]) + margin
    
    # Create PDF page in memory
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(width_points, height_points))
    
    # Draw the image
    c.drawImage(image_file, 
                margin/2,
                margin/2,
                width=width_points-margin,
                height=height_points-margin,
                preserveAspectRatio=True)
    
    # Add OCR layer if requested
    if use_ocr:
        try:
            # Configure Tesseract first
            if not configure_tesseract():
                print("Warning: OCR requested but Tesseract not found. Skipping OCR layer.")
            else:
                text = pytesseract.image_to_pdf_or_hocr(image_file, extension='hocr')
                text_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                
                # Create invisible text layer
                c.setFillColor(Color(0, 0, 0, 0))  # Transparent text
                for i in range(len(text_data['text'])):
                    if text_data['text'][i].strip():
                        x = text_data['left'][i] * width_points / img_width
                        # Convert y coordinate (OCR uses top-left origin, PDF uses bottom-left)
                        y = height_points - (text_data['top'][i] * height_points / img_height)
                        c.drawString(x + margin/2, y - margin/2, text_data['text'][i])
        except Exception as e:
            print(f"Warning: OCR failed for {image_file}: {str(e)}")
    
    c.save()
    
    # Get the value of the BytesIO buffer
    packet.seek(0)
    return PdfReader(packet)

def create_pdf(image_dir, output_pdf, use_ocr=False):
    """
    Create a PDF from all JPG images in the specified directory.
    Optionally make it searchable with OCR.
    """
    # Get all jpg files in the directory
    image_files = glob.glob(os.path.join(image_dir, 'page_*.jpg'))
    
    # Sort files by page number
    image_files.sort(key=lambda x: int(x.split('_')[-1].split('.')[0]))
    
    if not image_files:
        print(f"No JPG images found in {image_dir}")
        return
    
    # Create PDF writer
    pdf_writer = PdfWriter()
    
    # Process each image
    for i, image_file in enumerate(image_files, 1):
        print(f"Processing page {i}{'with OCR' if use_ocr else ''}...")
        
        # Create page
        pdf_reader = create_pdf_page(image_file, use_ocr)
        
        # Add page to output PDF
        pdf_writer.add_page(pdf_reader.pages[0])
    
    # Save the final PDF
    with open(output_pdf, 'wb') as output_file:
        pdf_writer.write(output_file)
    
    print(f"PDF created successfully: {output_pdf}")

def main():
    # Directory containing the downloaded images
    image_subfolder = 'Zephyr_teaser'
    image_dir = f'downloaded_images/{image_subfolder}'
    
    # Output PDF file - name based on whether OCR is used
    use_ocr = False  # Set to True to enable OCR
    output_pdf = f'pdf_documents/{image_subfolder}.pdf'
    
    # Create PDF
    create_pdf(image_dir, output_pdf, use_ocr)

if __name__ == "__main__":
    main() 