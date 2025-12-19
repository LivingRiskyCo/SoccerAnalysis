"""
Helper script to download and place OpenH264 DLL in the correct location.
"""
import os
import sys
import urllib.request
import shutil

def download_openh264():
    """Download OpenH264 DLL and place it in the virtual environment."""
    
    # Find virtual environment directory
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        # We're in a virtual environment
        venv_dir = os.path.dirname(sys.executable)
    else:
        # Check if we're in a project with a virtual environment
        script_dir = os.path.dirname(os.path.abspath(__file__))
        venv_scripts = os.path.join(script_dir, 'env', 'Scripts')
        if os.path.exists(venv_scripts):
            venv_dir = venv_scripts
        else:
            # Use Python executable directory as fallback
            venv_dir = os.path.dirname(sys.executable)
    
    print(f"Target directory: {venv_dir}")
    
    # OpenH264 download URL (version 2.4.0)
    # Try multiple possible URLs
    dll_urls = [
        "https://github.com/cisco/openh264/releases/download/v2.4.0/openh264-2.4.0-win64.dll.bz2",
        "https://github.com/cisco/openh264/releases/download/v2.4.0/openh264-2.4.0-win64.dll",
        "https://github.com/cisco/openh264/releases/download/v2.3.1/openh264-2.3.1-win64.dll.bz2",
    ]
    dll_name = "openh264-2.4.0-win64.dll"
    dll_path = os.path.join(venv_dir, dll_name)
    
    # Check if already exists
    if os.path.exists(dll_path):
        print(f"✓ OpenH264 DLL already exists at: {dll_path}")
        response = input("Do you want to overwrite it? (y/n): ")
        if response.lower() != 'y':
            print("Skipping download.")
            return
        os.remove(dll_path)
    
    print(f"\nDownloading OpenH264 DLL from GitHub...")
    
    downloaded = False
    for dll_url in dll_urls:
        try:
            print(f"Trying URL: {dll_url}")
            # Download the file
            if dll_url.endswith('.bz2'):
                compressed_path = dll_path + ".bz2"
                print("Downloading compressed file...")
                urllib.request.urlretrieve(dll_url, compressed_path)
                print(f"✓ Downloaded to: {compressed_path}")
                downloaded = True
                break
            else:
                # Direct DLL download
                print("Downloading DLL directly...")
                urllib.request.urlretrieve(dll_url, dll_path)
                print(f"✓ Downloaded to: {dll_path}")
                downloaded = True
                break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print(f"  URL not found (404), trying next...")
                continue
            else:
                raise
        except Exception as e:
            print(f"  Error: {e}, trying next URL...")
            continue
    
    if not downloaded:
        raise Exception("Could not download from any URL")
    
    try:
        
        # Note: The file is bz2 compressed, but we need to extract it
        # For simplicity, let's provide manual instructions
        print("\n⚠ The downloaded file is compressed (.bz2 format).")
        print("You need to extract it manually:")
        print(f"1. Extract {compressed_path}")
        print(f"2. Rename the extracted file to: {dll_name}")
        print(f"3. Place it in: {venv_dir}")
        print("\nOr download the DLL directly from:")
        print("https://github.com/cisco/openh264/releases/download/v2.4.0/openh264-2.4.0-win64.dll.bz2")
        print("Then extract it using 7-Zip, WinRAR, or Windows built-in extraction.")
        
        # Try to use bz2 module if available
        try:
            import bz2
            print("\nAttempting to extract using Python bz2 module...")
            with bz2.open(compressed_path, 'rb') as f_in:
                with open(dll_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            os.remove(compressed_path)
            print(f"✓ Successfully extracted to: {dll_path}")
            print(f"✓ OpenH264 DLL is now in the correct location!")
            return
        except ImportError:
            print("Python bz2 module not available. Please extract manually.")
            return
        
    except Exception as e:
        print(f"❌ Error downloading: {e}")
        print("\nManual download instructions:")
        print("1. Go to: https://github.com/cisco/openh264/releases")
        print("2. Download: openh264-2.4.0-win64.dll.bz2 (or newer version)")
        print("3. Extract the .bz2 file to get the .dll")
        print(f"4. Place the DLL in: {venv_dir}")
        return
    
    print(f"\n✓ OpenH264 DLL should now be at: {dll_path}")
    print("Restart your analysis to see if the OpenH264 errors are gone.")

if __name__ == "__main__":
    download_openh264()

