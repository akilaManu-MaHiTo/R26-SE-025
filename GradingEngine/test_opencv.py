import cv2
import os
from app.services.ocr_service import _process_image_to_clean_version

# 1. Define the path to your photo
input_image = "test_handwriting.jpeg"

if not os.path.exists(input_image):
    print(f"Error: {input_image} not found! Put a photo in this folder.")
else:
    # 2. Run your DIP Preprocessor
    print("Processing image with OpenCV...")
    processed_path = _process_image_to_clean_version(input_image)
    
    # 3. Load both images to compare
    original = cv2.imread(input_image)
    processed = cv2.imread(processed_path)
    
    # 4. Resize for your screen (Important for low-spec/small monitors)
    # This ensures the popup window isn't huge
    display_original = cv2.resize(original, (600, 800))
    display_processed = cv2.resize(processed, (600, 800))
    
    # 5. Display the windows
    cv2.imshow("Original Handwriting", display_original)
    cv2.imshow("DIP Cleaned (Black & White)", display_processed)
    
    print("Success! Windows opened. Press ANY KEY to close them.")
    
    # 6. Wait for a key press, then clean up
    cv2.waitKey(0) # 0 means wait forever until a key is pressed
    cv2.destroyAllWindows()