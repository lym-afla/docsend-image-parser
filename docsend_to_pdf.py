import os
import time
from docsend_image_downloader import DocSendImageDownloader, get_cookies_from_browser

# Import PDF compilation functions
from compile_to_pdf import (
    create_pdf_without_ocr,
    create_pdf_with_tesseract_default,
    create_pdf_with_ocrmypdf
)
from get_cookies_helper import extract_document_info_from_url

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
    document_url = "https://audeo.docsend.com/view/93wdni8fvi9ch8pd/d/kg8yan5n5mcz4nf9"
    document_id, view_id = extract_document_info_from_url(document_url)
    document_name = "Audeo Investment Memo - Plata Secondary"  # Name for output folder
    end_page = 3  # Set to None for all pages, or specify end page
    
    # Authentication settings - ADD YOUR COOKIES HERE
    cookies = {
        # Add your fresh cookies from browser here
        '_v_': 'ysi54HCS7kJ%2BYOt2yswB3QXHRQ2EgdCwQMSmafP1TBhr6yfdVa0liYH%2FWOv%2Fl36WoPZGLlckmo7GhQp%2FKVN%2FjSxDyMn4r%2BnZrmgNl2FmTG3xch92%2Bv%2Fd4To%3D--NgpsLZTipod58fYT--2wrXpp7oh3hTLeBa9Vr93w%3D%3D',
        '_dss_': '077ef6fb6a11fcc01f12fc7403961cde',
        '_us_': 'eyJfcmFpbHMiOnsibWVzc2FnZSI6IkluWnBaWGRsWkNCa2IyTWkiLCJleHAiOm51bGwsInB1ciI6ImNvb2tpZS5fdXNfIn19--d99e89135b29409ec95f7b01021ec543a463b2ba',
    }
    
    # OCR settings
    use_ocr = True  # Set to True for OCR, False for simple PDF
    use_premium_ocr = False  # Set to True for OCRmyPDF (premium quality), False for Tesseract (recommended)
    language = 'eng'  # OCR language: 'eng', 'fra', 'deu', 'spa', etc.
    
    # ============================================================================
    # AUTHENTICATION CHECK
    # ============================================================================
    
    if not cookies:
        print("❌ No authentication cookies provided!")
        print("💡 Please add your browser cookies to the 'cookies' dictionary above.")
        get_cookies_from_browser()
        return
    
    # ============================================================================
    # STEP 1: DOWNLOAD IMAGES FROM DOCSEND
    # ============================================================================
    
    print(f"\n📥 Step 1: Downloading images from DocSend...")
    print(f"Document: {document_name}")
    print(f"Pages: 1 to {end_page if end_page else 'end'}")
    
    # Create downloader with authentication
    downloader = DocSendImageDownloader(cookies=cookies)
    image_dir = f'downloaded_images/{document_name}'
    
    # Download images
    downloaded_count = downloader.download_document_images(
        document_id=document_id,
        view_id=view_id,
        start_page=1,
        end_page=end_page,
        output_dir=image_dir
    )
    
    # Check if images were downloaded
    if downloaded_count == 0:
        print("❌ No images were downloaded. Please check:")
        print("   1. Your document ID and view ID are correct")
        print("   2. Your authentication cookies are fresh and valid")
        print("   3. You have access to the document")
        return
    
    print(f"✅ Successfully downloaded {downloaded_count} images to {image_dir}")
    
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