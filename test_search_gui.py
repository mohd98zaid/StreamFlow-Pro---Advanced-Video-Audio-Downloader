"""
Minimal YouTube search test GUI to diagnose the issue
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
import yt_dlp

def search_youtube():
    query = search_entry.get().strip()
    if not query:
        messagebox.showwarning("Input Required", "Enter search query")
        return
    
    log(f"🔍 Searching for: {query}")
    
    def run_search():
        try:
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
                'no_warnings': True,
                'ignoreerrors': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch15:{query}", download=False)
            
            if not info:
                root.after(0, lambda: log("❌ No response"))
                return
            
            entries = [e for e in info.get('entries', []) if e is not None]
            root.after(0, lambda: log(f"✅ Got {len(entries)} results"))
            root.after(0, lambda: display_results(entries))
            
        except Exception as e:
            root.after(0, lambda: log(f"❌ Error: {e}"))
    
    threading.Thread(target=run_search, daemon=True).start()

def display_results(entries):
    tree.delete(*tree.get_children())
    
    if not entries:
        log("No entries to display")
        return
    
    log(f"Displaying {len(entries)} entries...")
    
    for entry in entries:
        try:
            title = entry.get('title', 'Unknown')
            channel = entry.get('uploader', 'Unknown')
            video_id = entry.get('id', '')
            url = f"https://www.youtube.com/watch?v={video_id}" if video_id else "N/A"
            
            tree.insert("", "end", values=(title, channel, url))
            
        except Exception as e:
            log(f"Error adding entry: {e}")
    
    log(f"✅ All {len(entries)} results displayed")
    tree.update_idletasks()

def log(msg):
    log_text.config(state='normal')
    log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    log_text.see(tk.END)
    log_text.config(state='disabled')

# Create window
root = tk.Tk()
root.title("YouTube Search Test")
root.geometry("800x600")

# Search section
search_frame = ttk.Frame(root, padding=10)
search_frame.pack(fill=tk.X)

ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=5)
search_entry = ttk.Entry(search_frame, width=40)
search_entry.pack(side=tk.LEFT, padx=5)
search_entry.bind('<Return>', lambda e: search_youtube())

ttk.Button(search_frame, text="Search", command=search_youtube).pack(side=tk.LEFT, padx=5)

# Results tree
tree_frame = ttk.Frame(root, padding=10)
tree_frame.pack(fill=tk.BOTH, expand=True)

columns = ("Title", "Channel", "URL")
tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)
for col in columns:
    tree.heading(col, text=col)
tree.column("Title", width=400)
tree.column("Channel", width=200)
tree.column("URL", width=0, stretch=False)

vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
tree.configure(yscrollcommand=vsb.set)

tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
vsb.pack(side=tk.RIGHT, fill=tk.Y)

# Log
log_frame = ttk.Frame(root, padding=10)
log_frame.pack(fill=tk.BOTH, expand=True)

ttk.Label(log_frame, text="Log:").pack(anchor=tk.W)
log_text = scrolledtext.ScrolledText(log_frame, height=8, state='disabled')
log_text.pack(fill=tk.BOTH, expand=True)

log("Ready. Enter a search query and click Search.")

root.mainloop()
