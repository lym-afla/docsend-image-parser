import os
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape
from reportlab.lib.units import inch, mm
import glob
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

def create_pdf_without_ocr(image_dir, output_pdf):
    """
    Create a PDF from all JPG images in the specified directory (no OCR).
    Fast and simple for cases where OCR is not needed.
    """
    # Get all jpg files in the directory
    image_files = glob.glob(os.path.join(image_dir, 'page_*.jpg'))
    
    # Sort files by page number
    image_files.sort(key=lambda x: int(x.split('_')[-1].split('.')[0]))
    
    if not image_files:
        print(f"No JPG images found in {image_dir}")
        return False
    
    # Create PDF using reportlab (faster without OCR)
    from reportlab.pdfgen import canvas
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_pdf), exist_ok=True)
    
    # Create canvas for the first image to determine page size
    first_img = Image.open(image_files[0])
    img_width, img_height = first_img.size
    
    # Calculate page size (assuming 300 DPI)
    page_width = img_width * 72.0 / 300
    page_height = img_height * 72.0 / 300
    
    c = canvas.Canvas(output_pdf, pagesize=(page_width, page_height))
    
    # Process each image
    for i, image_file in enumerate(image_files, 1):
        print(f"Processing page {i}/{len(image_files)}...")
        
        if i > 1:
            c.showPage()  # Start new page
            
        # Draw image to fill the page with high quality
        c.drawImage(image_file, 0, 0, width=page_width, height=page_height, 
                   preserveAspectRatio=True, mask='auto')
    
    c.save()
    print(f"PDF created successfully: {output_pdf}")
    return True

def create_pdf_with_ocrmypdf(image_dir, output_pdf, language='eng', high_quality_mode=False):
    """
    Create a searchable PDF using OCRmyPDF - MUCH BETTER OCR QUALITY!
    This is the recommended approach for OCR.
    """
    # First create a basic PDF from images
    temp_pdf = output_pdf.replace('.pdf', '_temp.pdf')
    
    print("Step 1: Creating PDF from images...")
    if not create_pdf_without_ocr(image_dir, temp_pdf):
        return False
    
    # Check if OCRmyPDF is installed
    if not shutil.which('ocrmypdf'):
        print("❌ OCRmyPDF not found!")
        print("Install with: pip install ocrmypdf")
        print("Also install system dependencies:")
        print("  Windows: Install via conda or use WSL")
        print("  macOS: brew install ocrmypdf")
        print("  Linux: apt install ocrmypdf")
        return False
    
    print("Step 2: Running OCRmyPDF for superior OCR...")
    
    # Remove existing output file if it exists to avoid permission errors
    if os.path.exists(output_pdf):
        try:
            os.remove(output_pdf)
            print(f"Removed existing file: {output_pdf}")
        except PermissionError:
            print(f"⚠️  Warning: Could not remove existing file {output_pdf}")
            print("Please close any PDF viewers and try again, or use a different filename")
            # Try with timestamp to avoid conflicts
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_pdf = output_pdf.replace('.pdf', f'_{timestamp}.pdf')
            print(f"Using alternative filename: {output_pdf}")
    
    try:
        # Run OCRmyPDF with Windows-compatible settings (no unpaper dependency)
        if high_quality_mode:
            # High quality settings - prioritize OCR accuracy over file size
            cmd = [
                'ocrmypdf',
                '--optimize', '1',           # Light optimization (0 disables image quality settings)
                '--oversample', '450',       # Higher resolution for OCR processing (default 300)
                '--deskew',                  # Correct skewed pages
                '--clean',                   # Clean up image artifacts
                '--language', language,      # OCR language
                '--output-type', 'pdf',      # Regular PDF (not PDF/A) - editable by default
                '--rotate-pages',            # Auto-rotate pages
                '--force-ocr',              # OCR even if text exists
                '--jpeg-quality', '100',     # Maximum JPEG quality
                '--png-quality', '100',      # Maximum PNG quality
                temp_pdf,
                output_pdf
            ]
        else:
            # Balanced settings
            cmd = [
                'ocrmypdf',
                '--optimize', '1',           # Light optimization to preserve image quality
                '--deskew',                  # Correct skewed pages
                '--clean',                   # Clean up image artifacts (now that unpaper is installed)
                '--language', language,      # OCR language
                '--output-type', 'pdf',      # Regular PDF (not PDF/A) - editable by default
                '--rotate-pages',            # Auto-rotate pages
                '--force-ocr',              # OCR even if text exists
                '--jpeg-quality', '95',      # High JPEG quality (0-100, 95 = very high quality)
                '--png-quality', '95',       # High PNG quality  
                temp_pdf,
                output_pdf
            ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ OCR PDF created successfully: {output_pdf}")
            # Clean up temp file
            os.remove(temp_pdf)
            return True
        else:
            print(f"❌ OCRmyPDF failed: {result.stderr}")
            print("\n💡 Trying with minimal settings...")
            
            # Fallback: Try with absolutely minimal settings
            cmd_simple = [
                'ocrmypdf',
                '--language', language,
                '--force-ocr',
                temp_pdf,
                output_pdf
            ]
            
            result = subprocess.run(cmd_simple, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ OCR PDF created successfully with basic settings: {output_pdf}")
                os.remove(temp_pdf)
                return True
            else:
                print(f"❌ OCRmyPDF failed even with minimal settings: {result.stderr}")
                print("\n🔧 Alternative: Using Tesseract fallback...")
                return create_pdf_with_tesseract_fallback(image_dir, output_pdf, language)
                
    except Exception as e:
        print(f"❌ Error running OCRmyPDF: {str(e)}")
        print("🔧 Using Tesseract fallback...")
        return create_pdf_with_tesseract_fallback(image_dir, output_pdf, language)

def create_pdf_with_tesseract_default(image_dir, output_pdf, language='eng'):
    """
    Create a searchable PDF using Tesseract directly - RECOMMENDED DEFAULT METHOD.
    Provides excellent balance of quality, file size, and OCR accuracy.
    """
    try:
        import pytesseract
        from PyPDF2 import PdfWriter, PdfReader
        import io
        
        print("Using Tesseract for OCR (recommended)...")
        
        # Configure Tesseract path for Windows
        tesseract_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            r'C:\Users\Public\Tesseract-OCR\tesseract.exe'
        ]
        
        tesseract_found = False
        for path in tesseract_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                tesseract_found = True
                print(f"Found Tesseract at: {path}")
                break
        
        if not tesseract_found:
            print("❌ Tesseract not found! Please install Tesseract OCR")
            print("Download from: https://github.com/UB-Mannheim/tesseract/wiki")
            return False
        
        # Get all jpg files
        image_files = glob.glob(os.path.join(image_dir, 'page_*.jpg'))
        image_files.sort(key=lambda x: int(x.split('_')[-1].split('.')[0]))
        
        if not image_files:
            print(f"No JPG images found in {image_dir}")
            return False
        
        # Create output directory
        os.makedirs(os.path.dirname(output_pdf), exist_ok=True)
        
        # Create PDF with OCR
        pdf_writer = PdfWriter()
        
        for i, image_file in enumerate(image_files, 1):
            print(f"OCR processing page {i}/{len(image_files)}...")
            
            try:
                # Get OCR data with optimized settings
                img = Image.open(image_file)
                
                # Use Tesseract to create PDF with embedded text
                pdf_bytes = pytesseract.image_to_pdf_or_hocr(
                    img, 
                    extension='pdf', 
                    lang=language,
                    config='--psm 1 --oem 3'  # Optimized OCR settings
                )
                
                # Create PDF page from OCR
                pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
                pdf_writer.add_page(pdf_reader.pages[0])
                
            except Exception as e:
                print(f"Warning: OCR failed for page {i}: {str(e)}")
                # Fall back to image-only page
                temp_single_pdf = f"temp_page_{i}.pdf"
                if create_pdf_without_ocr(os.path.dirname(image_file), temp_single_pdf):
                    page_reader = PdfReader(temp_single_pdf)
                    pdf_writer.add_page(page_reader.pages[0])
                    os.remove(temp_single_pdf)
        
        # Save final PDF
        with open(output_pdf, 'wb') as output_file:
            pdf_writer.write(output_file)
        
        print(f"✅ Tesseract OCR PDF created: {output_pdf}")
        return True
        
    except ImportError:
        print("❌ PyPDF2 and pytesseract not available")
        print("Installing required dependencies...")
        try:
            subprocess.run(['pip', 'install', 'pytesseract', 'PyPDF2'], check=True)
            return create_pdf_with_tesseract_default(image_dir, output_pdf, language)
        except:
            print("❌ Failed to install dependencies")
            return False
    except Exception as e:
        print(f"❌ Tesseract OCR failed: {str(e)}")
        return False

def create_pdf_with_tesseract_fallback(image_dir, output_pdf, language='eng'):
    """
    Fallback OCR method using Tesseract directly when OCRmyPDF fails.
    Better than the original implementation but not as good as OCRmyPDF.
    """
    try:
        import pytesseract
        from PyPDF2 import PdfWriter, PdfReader
        import io
        from reportlab.lib.colors import Color
        
        print("Using Tesseract fallback for OCR...")
        
        # Configure Tesseract path for Windows
        tesseract_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            r'C:\Users\Public\Tesseract-OCR\tesseract.exe'
        ]
        
        tesseract_found = False
        for path in tesseract_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                tesseract_found = True
                print(f"Found Tesseract at: {path}")
                break
        
        if not tesseract_found:
            print("❌ Tesseract not found! Please install Tesseract OCR")
            print("Download from: https://github.com/UB-Mannheim/tesseract/wiki")
            return False
        
        # Get all jpg files
        image_files = glob.glob(os.path.join(image_dir, 'page_*.jpg'))
        image_files.sort(key=lambda x: int(x.split('_')[-1].split('.')[0]))
        
        if not image_files:
            print(f"No JPG images found in {image_dir}")
            return False
        
        # Create output directory
        os.makedirs(os.path.dirname(output_pdf), exist_ok=True)
        
        # Create PDF with OCR
        pdf_writer = PdfWriter()
        
        for i, image_file in enumerate(image_files, 1):
            print(f"OCR processing page {i}/{len(image_files)}...")
            
            try:
                # Get OCR data
                img = Image.open(image_file)
                pdf_bytes = pytesseract.image_to_pdf_or_hocr(img, extension='pdf', lang=language)
                
                # Create PDF page from OCR
                pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
                pdf_writer.add_page(pdf_reader.pages[0])
                
            except Exception as e:
                print(f"Warning: OCR failed for page {i}: {str(e)}")
                # Fall back to image-only page
                if not create_pdf_without_ocr(os.path.dirname(image_file), f"temp_page_{i}.pdf"):
                    continue
                page_reader = PdfReader(f"temp_page_{i}.pdf")
                pdf_writer.add_page(page_reader.pages[0])
                os.remove(f"temp_page_{i}.pdf")
        
        # Save final PDF
        with open(output_pdf, 'wb') as output_file:
            pdf_writer.write(output_file)
        
        print(f"✅ Fallback OCR PDF created: {output_pdf}")
        return True
        
    except ImportError:
        print("❌ PyPDF2 and pytesseract not available for fallback")
        print("Installing fallback dependencies...")
        subprocess.run(['pip', 'install', 'pytesseract', 'PyPDF2'], check=True)
        return create_pdf_with_tesseract_fallback(image_dir, output_pdf, language)
    except Exception as e:
        print(f"❌ Fallback OCR failed: {str(e)}")
        return False

def main():
    # Directory containing the downloaded images
    image_subfolder = '202501 Addi Corporate presentation'
    image_dir = f'downloaded_images/{image_subfolder}'

    # Configuration
    use_ocr = True  # Set to True for OCR, False for simple PDF
    use_premium_ocr = False  # Set to True for OCRmyPDF (premium quality), False for Tesseract (recommended)
    language = 'eng'  # OCR language: 'eng', 'fra', 'deu', etc.
    
    # Output PDF file
    if use_ocr:
        if use_premium_ocr:
            output_pdf = f'pdf_documents/{image_subfolder}_searchable_premium.pdf'
            print("🔍 Creating PREMIUM searchable PDF with OCRmyPDF...")
            success = create_pdf_with_ocrmypdf(image_dir, output_pdf, language, high_quality_mode=True)
        else:
            output_pdf = f'pdf_documents/{image_subfolder}.pdf'
            print("🔍 Creating searchable PDF with Tesseract (RECOMMENDED)...")
            success = create_pdf_with_tesseract_default(image_dir, output_pdf, language)
    else:
        output_pdf = f'pdf_documents/{image_subfolder}.pdf'
        print("📄 Creating simple PDF without OCR...")
        success = create_pdf_without_ocr(image_dir, output_pdf)
    
    if success:
        print(f"✅ Complete! Output: {output_pdf}")
        if use_ocr and not use_premium_ocr:
            print("💡 Tip: Set use_premium_ocr=True for even higher OCR quality (larger files)")
    else:
        print("❌ Failed to create PDF")

if __name__ == "__main__":
    main() 