"""
Audio Feature Extraction Setup and Configuration
This script helps verify and set up the audio analysis environment
"""

import subprocess
import sys
import os
from pathlib import Path

def check_ffmpeg():
    """Check if ffmpeg is installed"""
    try:
        result = subprocess.run(['ffmpeg', '-version'],
                              capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError, TimeoutError):
        return False

def check_praat():
    """Check if Praat is installed"""
    try:
        import parselmouth
        return True
    except ImportError:
        return False

def verify_directories():
    """Verify required directories exist"""
    required_dirs = ['videos', 'outputs']
    
    for dir_name in required_dirs:
        if not os.path.exists(dir_name):
            print(f"Creating directory: {dir_name}")
            os.makedirs(dir_name, exist_ok=True)
    
    return True

def verify_python_packages():
    """Verify key Python packages are installed"""
    required_packages = [
        'torch',
        'torchvision',
        'torchaudio',
        'librosa',
        'parselmouth',
        'whisper',
        'numpy',
        'soundfile',
        'cv2',
        'mediapipe',
        'timm',
        'scipy',
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ✗ {package} - NOT INSTALLED")
            missing.append(package)
    
    return len(missing) == 0, missing

def main():
    """Run setup verification"""
    print("=" * 60)
    print("Audio Feature Extraction - Setup Verification")
    print("=" * 60)
    print()
    
    # Check directories
    print("1. Checking directories...")
    if verify_directories():
        print("   ✓ All required directories exist")
    print()
    
    # Check system dependencies
    print("2. Checking system dependencies...")
    if check_ffmpeg():
        print("   ✓ ffmpeg is installed")
    else:
        print("   ✗ ffmpeg is NOT installed")
        print("   Install with: choco install ffmpeg (on Windows)")
    print()
    
    # Check Python packages
    print("3. Checking Python packages...")
    all_installed, missing = verify_python_packages()
    
    if all_installed:
        print("   ✓ All required packages are installed")
    else:
        print(f"   ✗ Missing packages: {', '.join(missing)}")
        print(f"\n   Install missing packages with:")
        install_names = ["praat-parselmouth" if package == "parselmouth" else package for package in missing]
        print(f"   pip install {' '.join(install_names)}")
    
    print()
    print("=" * 60)
    if all_installed and check_ffmpeg():
        print("✓ Setup verification completed successfully!")
        print("\nYou can now run:")
        print("  python main.py --video videos/your_clip.mp4")
        print("  python main.py --video videos/your_clip.mp4 --video-only")
        return 0
    else:
        print("⚠ Some dependencies are missing. Please install them.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
