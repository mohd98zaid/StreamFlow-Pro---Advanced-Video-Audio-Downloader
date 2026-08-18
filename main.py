import sys
import subprocess
import tkinter as tk
from tkinter import messagebox
import logging

# Configure logging centrally
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('downloader.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

def install_package(package_name):
    """Install a package via pip."""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        return True
    except Exception as e:
        logging.error(f"Failed to install {package_name}: {e}")
        return False

def check_dependencies():
    """Check for required packages and offer to install them."""
    missing = []
    
    try:
        import yt_dlp
    except ImportError:
        missing.append("yt-dlp")

    try:
        import static_ffmpeg
    except ImportError:
        missing.append("static-ffmpeg")
    
    # Optional but recommended packages
    try:
        import win10toast
    except ImportError:
        logging.warning("win10toast not found - notifications will be disabled")

    if missing:
        root = tk.Tk()
        root.withdraw()
        msg = f"The following required packages are missing:\n{', '.join(missing)}\n\n" \
              f"Installing them will verify 'static-ffmpeg' to handle high-quality video merging.\n" \
              f"Do you want to install them now?"
        
        if messagebox.askyesno("Missing Dependencies", msg):
            success = True
            for pkg in missing:
                if not install_package(pkg):
                    messagebox.showerror("Error", f"Failed to install {pkg}")
                    success = False
                    break
            
            if success:
                messagebox.showinfo("Success", "Dependencies installed! Starting app...")
                return True
            return False
        return False
    
    return True

def main():
    """Main entry point for the application"""
    if not check_dependencies():
        return

    # Initialize static-ffmpeg to add ffmpeg to PATH
    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
        logging.info("static-ffmpeg paths added.")
    except ImportError:
        logging.warning("static-ffmpeg not found, high quality merges might fail.")

    try:
        import customtkinter as ctk
        from gui import AdvancedDownloaderApp
    except ImportError as e:
        logging.error(f"Import error: {e}")
        messagebox.showerror("Error", f"Failed to import application: {e}")
        return

    try:
        root = ctk.CTk()
        app = AdvancedDownloaderApp(root)
        root.mainloop()
    except Exception as e:
        logging.error(f"Application error: {e}", exc_info=True)
        messagebox.showerror("Error", f"Application crashed: {e}")

if __name__ == "__main__":
    main()
