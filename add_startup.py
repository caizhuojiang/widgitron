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

def create_exe():
    """Create executable with pyinstaller"""
    try:
        print("Cleaning previous build files...")
        
        # Clean up previous build
        if os.path.exists("build"):
            shutil.rmtree("build")
        if os.path.exists("widgitron.spec"):
            os.remove("widgitron.spec")
        if os.path.exists("widgitron.exe"):
            os.remove("widgitron.exe")
        
        print("Creating executable with pyinstaller...")
        
        # Run pyinstaller
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onefile",  # Single exe file
            "--windowed",  # No console window for GUI app
            "--icon", "icons/widgitron.png",  # Add icon to exe
            "--name", "widgitron",
            "--distpath", ".",  # Output to current directory
            "--add-data", "icons;icons",  # Include icons
            "--add-data", "configs;configs",  # Include configs
            "widgitron.py"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Pyinstaller failed: {result.stderr}")
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
        
        # Copy icons directory
        if os.path.exists("icons"):
            icons_dest = os.path.join(bin_dir, "icons")
            if os.path.exists(icons_dest):
                shutil.rmtree(icons_dest)
            shutil.copytree("icons", icons_dest)
            print(f"Copied icons to {icons_dest}")
        
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
        
        # Remove build directory
        if os.path.exists("build"):
            shutil.rmtree("build")
            print("Removed build directory")
        
        # Remove spec file
        if os.path.exists("widgitron.spec"):
            os.remove("widgitron.spec")
            print("Removed widgitron.spec")
        
        # Remove exe file (root directory)
        if os.path.exists("widgitron.exe"):
            os.remove("widgitron.exe")
            print("Removed widgitron.exe")
        
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