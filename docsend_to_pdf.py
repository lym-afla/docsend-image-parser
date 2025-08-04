import os
import time
from docsend_image_downloader import DocSendImageDownloader

# Import PDF compilation functions
from compile_to_pdf import (
    create_pdf_without_ocr,
    create_pdf_with_tesseract_default,
    create_pdf_with_ocrmypdf
)

def main():
    """
    Combined DocSend to PDF converter - downloads images and creates searchable PDF in one go.
    """
    print("🚀 DocSend to PDF Converter")
    print("=" * 50)
    
    # ============================================================================
    # CONFIGURATION - UPDATE THESE VALUES FOR YOUR DOCUMENT
    # ============================================================================
    
    # Document settings
    document_id = "3km9ubygyb79q4mk"  # From DocSend URL
    view_id = "v7uv3jhnedit8h79"      # From DocSend URL
    document_name = "GP Formation Certificate (Delaware)"  # Name for output folder
    end_page = 2  # Set to None for all pages, or specify end page
    
    # OCR settings
    use_ocr = True  # Set to True for OCR, False for simple PDF
    use_premium_ocr = False  # Set to True for OCRmyPDF (premium quality), False for Tesseract (recommended)
    language = 'eng'  # OCR language: 'eng', 'fra', 'deu', 'spa', etc.
    
    # ============================================================================
    # STEP 1: DOWNLOAD IMAGES FROM DOCSEND
    # ============================================================================
    
    print(f"\n📥 Step 1: Downloading images from DocSend...")
    print(f"Document: {document_name}")
    print(f"Pages: 1 to {end_page if end_page else 'end'}")
    
    downloader = DocSendImageDownloader()
    image_dir = f'downloaded_images/{document_name}'
    
    # Download images
    downloader.download_document_images(
        document_id=document_id,
        view_id=view_id,
        start_page=1,
        end_page=end_page,
        output_dir=image_dir
    )
    
    # Check if images were downloaded
    if not os.path.exists(image_dir):
        print("❌ No images were downloaded. Please check your document ID and view ID.")
        return
    
    image_files = [f for f in os.listdir(image_dir) if f.endswith('.jpg')]
    if not image_files:
        print("❌ No images found in the downloaded directory.")
        return
    
    print(f"✅ Downloaded {len(image_files)} images to {image_dir}")
    
    # ============================================================================
    # STEP 2: CREATE SEARCHABLE PDF
    # ============================================================================
    
    print(f"\n📄 Step 2: Creating searchable PDF...")
    
    # Determine output filename based on settings
    if use_ocr:
        if use_premium_ocr:
            output_pdf = f'pdf_documents/{document_name}_searchable_premium.pdf'
            print("🔍 Creating PREMIUM searchable PDF with OCRmyPDF...")
            success = create_pdf_with_ocrmypdf(image_dir, output_pdf, language, high_quality_mode=True)
        else:
            output_pdf = f'pdf_documents/{document_name}_searchable.pdf'
            print("🔍 Creating searchable PDF with Tesseract (RECOMMENDED)...")
            success = create_pdf_with_tesseract_default(image_dir, output_pdf, language)
    else:
        output_pdf = f'pdf_documents/{document_name}.pdf'
        print("📄 Creating simple PDF without OCR...")
        success = create_pdf_without_ocr(image_dir, output_pdf)
    
    # ============================================================================
    # RESULTS
    # ============================================================================
    
    if success:
        print(f"\n🎉 SUCCESS! Complete workflow finished.")
        print(f"📁 Images: {image_dir}")
        print(f"📄 PDF: {output_pdf}")
        
        # Show file size
        if os.path.exists(output_pdf):
            size_mb = os.path.getsize(output_pdf) / (1024 * 1024)
            print(f"📊 File size: {size_mb:.1f} MB")
        
        if use_ocr and not use_premium_ocr:
            print("\n💡 Tip: Set use_premium_ocr=True for even higher OCR quality (larger files)")
    else:
        print("❌ Failed to create PDF")
        print("💡 Check that Tesseract is installed for OCR functionality")

if __name__ == "__main__":
    main()