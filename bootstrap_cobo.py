import os
import tkinter as tk
import webbrowser
from cobo_config import COBO_ENV_DIR, SYSTEM_DIR, ASYNC_INBOX, CASE_FILE, ENV_FILE

def open_api_guide():
    webbrowser.open('https://aistudio.google.com/app/apikey')
    webbrowser.open('https://console.anthropic.com/settings/keys')

def prompt_for_keys():
    if ENV_FILE.exists():
        return
    
    root = tk.Tk()
    root.title('Cobo v2 - First Run Setup')
    root.geometry('400x320')
    root.attributes('-topmost', True)
    
    tk.Label(root, text='Welcome to Cobo v2', font=('Arial', 14, 'bold')).pack(pady=10)
    tk.Label(root, text='Please paste your API Keys to continue:').pack()
    
    tk.Label(root, text='Gemini API Key:').pack(pady=5)
    gemini_entry = tk.Entry(root, width=45)
    gemini_entry.pack()
    
    tk.Label(root, text='Claude API Key:').pack(pady=5)
    claude_entry = tk.Entry(root, width=45)
    claude_entry.pack()
    
    def save_keys():
        with open(ENV_FILE, 'w') as f:
            f.write(f'GEMINI_API_KEY={gemini_entry.get()}\n')
            f.write(f'CLAUDE_API_KEY={claude_entry.get()}\n')
        root.destroy()
        
    tk.Button(root, text='Save Keys & Start', command=save_keys, bg='#4CAF50', fg='white').pack(pady=15)
    tk.Button(root, text='How do I get these keys?', command=open_api_guide, fg='blue').pack()
    
    root.mainloop()

def bootstrap_environment():
    print('Initializing Cobo v2 Environment...')
    directories = [COBO_ENV_DIR, SYSTEM_DIR]
    for d in directories:
        d.mkdir(parents=True, exist_ok=True)
        
    if not ASYNC_INBOX.exists():
        ASYNC_INBOX.touch()
        
    if not CASE_FILE.exists():
        CASE_FILE.write_text('# Cobo Case File\n\nActive system blueprint.')
        
    prompt_for_keys()

if __name__ == '__main__':
    bootstrap_environment()
