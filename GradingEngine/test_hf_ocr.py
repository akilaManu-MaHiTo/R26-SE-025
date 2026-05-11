import asyncio
import os
from app.services.ocr_service import query_ocr_space

async def run_test():
    # 1. Path to your processed image from the last step
    image_to_test = "proc_test_handwriting.jpeg" # Change this to your actual filename
    
    if not os.path.exists(image_to_test):
        print(f"Error: {image_to_test} not found!")
        return

    print(f"Sending '{image_to_test}' to OCR.Space...")
    
    try:
        # 2. Run the AI
        extracted_text = await query_ocr_space(image_to_test)
        
        # 3. Display the result
        print("\n" + "="*30)
        print("EXTRACTED HANDWRITTEN TEXT:")
        print("="*30)
        print(extracted_text if extracted_text else "No text found or AI failed.")
        print("="*30 + "\n")
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(run_test())