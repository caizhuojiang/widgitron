"""
Script to create executable and add Widgitron to Windows startup
This script packages Widgitron as an exe with pyinstaller, copies necessary files to bin/,
and adds the exe to Windows registry for auto-start on boot
"""

import winreg
import os
import sys
import shutil
import subprocess
try:
    from PIL import Image
except ImportError:
    Image = None

def ensure_icon_exists():
    """Ensure .ico file exists, convert from .png if needed"""
    ico_path = "icons/widgitron.ico"
    png_path = "icons/widgitron.png"
    
    if os.path.exists(ico_path):
        return True
        
    if not os.path.exists(png_path):
        print(f"Warning: Icon source {png_path} not found")
        return False
        
    if Image is None:
        print("Warning: Pillow not installed, cannot convert icon. Please install it: pip install Pillow")
        return False

    try:
        print(f"Converting {png_path} to {ico_path}...")
        img = Image.open(png_path)
        icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        img.save(ico_path, format='ICO', sizes=icon_sizes)
        print("Icon conversion successful")
        return True
    except Exception as e:
        print(f"Error converting icon: {e}")
        return False

def create_exe():
    """Create executable with Nuitka"""
    try:
        print("Checking for Nuitka...")
        try:
            import nuitka
        except ImportError:
            print("Nuitka not found. Installing...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "nuitka"])

        # Ensure icon exists
        ensure_icon_exists()

        print("Cleaning previous build files...")
        
        # Clean up previous build
        cleanup_build_files()
        
        print("Creating executable with Nuitka (this may take a while)...")
        
        # Run Nuitka
        # Note: Nuitka requires a C compiler (like MinGW or MSVC)
        # It will ask to download one if not found
        cmd = [
            sys.executable, "-m", "nuitka",
            "--onefile",
            "--enable-plugin=pyqt5",
            "--include-package=widgets",
            "--output-dir=.",
            "--output-filename=widgitron.exe",
            "--include-data-dir=icons=icons", # Include icons for __file__ relative paths
            "--windows-disable-console", # Enable console for debugging
            "--assume-yes-for-downloads", # Auto download ccache/dependency walker if needed
            "--windows-icon-from-ico=icons/widgitron.ico", # Set application icon
            "widgitron.py"
        ]
        
        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=False) # Show output to see progress
        
        if result.returncode != 0:
            print("Nuitka build failed.")
            return False
        
        print("Executable created successfully!")
        return True
        
    except Exception as e:
        print(f"Error creating exe: {e}")
        return False

def setup_bin_directory():
    """Setup bin directory with exe and necessary files"""
    try:
        bin_dir = "bin"
        
        # Create bin directory
        if not os.path.exists(bin_dir):
            os.makedirs(bin_dir)
        
        # Copy exe
        exe_source = "widgitron.exe"
        exe_dest = os.path.join(bin_dir, "widgitron.exe")
        
        if os.path.exists(exe_source):
            shutil.copy2(exe_source, exe_dest)
            print(f"Copied exe to {exe_dest}")
        else:
            print(f"Error: {exe_source} not found")
            return False
        
        # Copy configs directory
        if os.path.exists("configs"):
            configs_dest = os.path.join(bin_dir, "configs")
            if os.path.exists(configs_dest):
                shutil.rmtree(configs_dest)
            shutil.copytree("configs", configs_dest)
            print(f"Copied configs to {configs_dest}")
        
        return True
        
    except Exception as e:
        print(f"Error setting up bin directory: {e}")
        return False

def add_exe_to_startup():
    """Add exe to Windows startup registry"""
    try:
        bin_dir = os.path.abspath("bin")
        exe_path = os.path.join(bin_dir, "widgitron.exe")
        
        # Ensure exe exists
        if not os.path.exists(exe_path):
            print(f"Error: exe not found at {exe_path}")
            return False
        
        # First, try to remove existing entry
        remove_from_startup()
        
        # Command to run: just the exe path
        command = f'"{exe_path}"'
        
        # Open the registry key for startup programs
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                           r"Software\Microsoft\Windows\CurrentVersion\Run", 
                           0, winreg.KEY_SET_VALUE)
        
        # Set the value
        winreg.SetValueEx(key, "Widgitron", 0, winreg.REG_SZ, command)
        
        # Close the key
        winreg.CloseKey(key)
        
        print("Widgitron exe has been added to startup successfully!")
        print(f"Registry entry: {command}")
        return True
        
    except Exception as e:
        print(f"Error adding exe to startup: {e}")
        return False

def cleanup_build_files():
    """Clean up build files after setup"""
    try:
        print("Cleaning up build files...")
        
        # Remove build directory (PyInstaller)
        if os.path.exists("build"):
            shutil.rmtree("build")
        
        # Remove spec file (PyInstaller)
        if os.path.exists("widgitron.spec"):
            os.remove("widgitron.spec")
            
        # Remove Nuitka build directories
        if os.path.exists("widgitron.build"):
            shutil.rmtree("widgitron.build")
        if os.path.exists("widgitron.onefile-build"):
            shutil.rmtree("widgitron.onefile-build")
        if os.path.exists("widgitron.dist"):
            shutil.rmtree("widgitron.dist")
            
        # Remove exe file (root directory) - we keep the one in bin/
        if os.path.exists("widgitron.exe"):
            os.remove("widgitron.exe")
            print("Removed root widgitron.exe")
        
        return True
        
    except Exception as e:
        print(f"Error cleaning up build files: {e}")
        return False

def remove_from_startup():
    """Remove Widgitron from Windows startup registry"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                           r"Software\Microsoft\Windows\CurrentVersion\Run", 
                           0, winreg.KEY_SET_VALUE)
        
        try:
            winreg.DeleteValue(key, "Widgitron")
            print("Widgitron has been removed from startup successfully!")
            return True
        except FileNotFoundError:
            print("Widgitron was not found in startup registry.")
            return False
        finally:
            winreg.CloseKey(key)
            
    except Exception as e:
        print(f"Error removing from startup: {e}")
        return False

def main():
    """Main function"""
    print("Setting up Widgitron executable and startup...")
    
    # Create exe
    if not create_exe():
        return
    
    # Setup bin directory
    if not setup_bin_directory():
        return
    
    # Clean up build files
    if not cleanup_build_files():
        return
    
    # Add to startup
    if not add_exe_to_startup():
        return
    
    print("\nSetup complete! Widgitron exe is ready and added to startup.")
    print("Restart your computer to test auto-start.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "remove":
        remove_from_startup()
    else:
        main()