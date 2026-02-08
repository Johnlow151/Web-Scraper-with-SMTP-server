import json      # For handling API data
import smtplib   # For sending the email
import ssl       # For a secure email connection
from email.message import EmailMessage # For building the email
import os
import webbrowser  # For opening HTML files in browser
import datetime    # For timestamping saved files
import re
import html as _html_module
import markdown
from tavily import TavilyClient  # Tavily's official Python SDK
from dotenv import load_dotenv   # For loading .env files
import tkinter as tk
from tkinter import scrolledtext
import threading
import sys
from io import StringIO
load_dotenv()

# --- 1. SETTINGS: FILL THESE IN! ---

# Your full Gmail address (e.g., "my_email@gmail.com")
YOUR_GMAIL_EMAIL = "JDSDAutomated@gmail.com"

# The 16-character "App Password" you generated from Google
# (e.g., "abcd efgh ijkl mnop")
YOUR_GMAIL_APP_PASSWORD = os.environ.get('YOUR_GMAIL_APP_PASSWORD')
if not YOUR_GMAIL_APP_PASSWORD:
    print("❌ No SMTP server key found in environment variables")

# --- Helper: minimal Markdown to HTML converter (used for saved previews) ---
def convert_markdown_to_html(md_text: str) -> str:
    """
    Minimal converter that handles headings ('# ...'), horizontal rules (---),
    fenced code blocks (```), and inline code. Returns an HTML fragment.
    """
    # Extract fenced code blocks
    code_blocks = []

    def _code_block_repl(m):
        code_blocks.append(m.group(1))
        return f"@@CODEBLOCK{len(code_blocks)-1}@@"

    text = re.sub(r"```\n?(.*?)\n?```", _code_block_repl, md_text, flags=re.DOTALL)

    # Escape remaining text
    escaped = _html_module.escape(text)

    # Handle inline code
    inline_codes = []
    def _inline_repl(m):
        inline_codes.append(m.group(1))
        return f"@@INLINE{len(inline_codes)-1}@@"

    escaped = re.sub(r"`([^`]+?)`", _inline_repl, escaped)

    # Convert lines
    out_lines = []
    for line in escaped.splitlines():
        if line.startswith('@@CODEBLOCK'):
            m = re.match(r"@@CODEBLOCK(\d+)@@", line)
            if m:
                idx = int(m.group(1))
                code = _html_module.escape(code_blocks[idx])
                out_lines.append(f"<pre><code>{code}</code></pre>")
            else:
                out_lines.append(line)
        elif line.startswith('# '):
            out_lines.append(f"<h1>{line[2:].strip()}</h1>")
        elif line.startswith('## '):
            out_lines.append(f"<h2>{line[3:].strip()}</h2>")
        elif line.startswith('### '):
            out_lines.append(f"<h3>{line[4:].strip()}</h3>")
        elif line.strip() == '---':
            out_lines.append('<hr/>')
        elif line.strip() == '':
            out_lines.append('')
        else:
            # Restore inline code placeholders
            restored = line
            for i, code in enumerate(inline_codes):
                restored = restored.replace(f"@@INLINE{i}@@", f"<code>{_html_module.escape(code)}</code>")
            out_lines.append(f"<p>{restored}</p>")

    return "\n".join(out_lines)

# --- 2. GUI CLASS FOR SEARCH INTERFACE ---
class SearchGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("TavilySSS")
        self.root.geometry("700x700")
        self.root.resizable(True, True)
        
        # Store user input from the entry field
        self.user_input = None
        self.input_event = threading.Event()
        
        # --- Title field at top ---
        title_frame = tk.Frame(root, bg="#007acc", height=50)
        title_frame.pack(fill=tk.X)
        title_label = tk.Label(
            title_frame,
            text="Tavily Search, Save, Send",
            font=("Arial", 18, "bold"),
            bg="#007acc",
            fg="white",
            pady=10
        )
        title_label.pack()
        
        # --- Scrolling text display in middle ---
        self.text_display = scrolledtext.ScrolledText(
            root,
            wrap=tk.WORD,
            font=("Courier", 9),
            bg="#6e6e6e",
            fg="#111"
        )
        self.text_display.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.text_display.config(state=tk.DISABLED)
        
        # --- Input frame at bottom ---
        input_frame = tk.Frame(root)
        input_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.input_field = tk.Entry(input_frame, font=("Arial", 10))
        self.input_field.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        self.input_field.bind("<Return>", lambda e: self.submit_input())
        
        submit_button = tk.Button(
            input_frame,
            text="Enter",
            font=("Arial", 10),
            bg="#007acc",
            fg="white",
            command=self.submit_input,
            width=8
        )
        submit_button.pack(side=tk.RIGHT)
    
    def append_text(self, text):
        """Append text to the scrolled text display."""
        self.text_display.config(state=tk.NORMAL)
        self.text_display.insert(tk.END, text)
        self.text_display.see(tk.END)
        self.text_display.config(state=tk.DISABLED)
        self.root.update()
    
    def submit_input(self):
        """Called when user clicks Enter button or presses Return key."""
        self.user_input = self.input_field.get()
        self.input_field.delete(0, tk.END)
        self.input_event.set()
    
    def get_input(self, prompt=""):
        """Replaces the built-in input() function."""
        self.append_text(prompt)
        self.input_event.clear()
        self.user_input = None
        
        # Wait for user to submit input
        while not self.user_input:
            self.root.update()
            self.input_event.wait(timeout=0.1)
        
        result = self.user_input
        self.append_text(result + "\n")
        return result

# --- Redirect print() and input() to GUI ---
gui_instance = None

def setup_gui_redirection(gui):
    """Redirect print and input to GUI."""
    global gui_instance
    gui_instance = gui
    
    # Redirect input() calls
    import builtins
    original_input = builtins.input
    
    def gui_input(prompt=""):
        if gui_instance:
            return gui_instance.get_input(prompt)
        else:
            return original_input(prompt)
    
    builtins.input = gui_input
    
    # Redirect print() to GUI
    original_stdout = sys.stdout
    
    class GUIStdout:
        def __init__(self):
            self.buffer = ""
        
        def write(self, text):
            if gui_instance:
                gui_instance.append_text(text)
            else:
                original_stdout.write(text)
            return len(text)
        
        def flush(self):
            pass
    
    sys.stdout = GUIStdout()


def send_email(subject, body, to_email):
    """
    Connects to Gmail and sends the email.
    """
    print(f"📤 Connecting to Gmail to send email to {to_email}...")
    # Create the email message object
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = YOUR_GMAIL_EMAIL
    msg['To'] = to_email
    # Set the plain-text fallback
    msg.set_content(body)
    # Add HTML alternative for rich formatting using the `markdown` package
    # Enable common useful extensions for fenced code blocks, tables, and code highlighting
    try:
        html_body = markdown.markdown(body or "", extensions=["fenced_code", "tables", "codehilite"])
    except Exception:
        # Fallback to escaping the body inside a <pre> block
        html_body = f"<pre>{_html_module.escape(body or '')}</pre>"
    msg.add_alternative(html_body, subtype='html')
    # Create a secure SSL context
    context = ssl.create_default_context()
    try:
        # Connect to Gmail's SMTP server over SSL (Port 465)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(YOUR_GMAIL_EMAIL, YOUR_GMAIL_APP_PASSWORD)
            print("✅ Logged in to Gmail.")
            server.send_message(msg)
            print(f"🎉 Email sent successfully to {to_email}!")
    except smtplib.SMTPAuthenticationError:
        print("\n❌ CRITICAL ERROR: Gmail login failed.")
        print("   Please check:")
        print("   1. YOUR_GMAIL_EMAIL is correct.")
        print("   2. YOUR_GMAIL_APP_PASSWORD is the 16-character code (not your regular password).")
    except Exception as e:
        print(f"❌ Error sending email: {e}")
def save_to_html(content, title, url):
    """
    Save search result to an HTML file in the saved_html folder and open it.
    
    Args:
        content (str): The full content to save
        title (str): The title of the result
        url (str): The source URL of the result
    """
    try:
        # Get the directory where gmail.py is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        saved_folder = os.path.join(script_dir, 'saved_html')
        
        # Create the folder if it doesn't exist
        os.makedirs(saved_folder, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"result_{timestamp}.html"
        filepath = os.path.join(saved_folder, filename)
        
        # Convert Markdown-like content to HTML fragment so headings
        # (lines starting with #) and fenced code blocks render properly.
        try:
            # Use the `markdown` library to convert the content to HTML
            body_fragment = markdown.markdown(content or "", extensions=["fenced_code", "tables", "codehilite"])
        except Exception:
            # Fallback: escape the content and preserve line breaks
            body_fragment = f"<pre>{_html_module.escape(content)}</pre>"

        # Create formatted HTML document
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            color: #111;
            line-height: 1.6;
            padding: 20px;
            max-width: 900px;
            margin: 0 auto;
            background: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #222;
            margin-top: 0;
            border-bottom: 3px solid #007acc;
            padding-bottom: 10px;
        }}
        .metadata {{
            background: #f0f4f8;
            padding: 15px;
            border-radius: 4px;
            margin: 20px 0;
            border-left: 4px solid #007acc;
        }}
        .metadata p {{
            margin: 5px 0;
        }}
        .metadata strong {{
            color: #007acc;
        }}
        .source-url {{
            word-break: break-all;
            font-family: 'Courier New', monospace;
            font-size: 12px;
        }}
        .content {{
            margin-top: 30px;
            line-height: 1.8;
            word-break: break-word;
            overflow-wrap: anywhere;
            white-space: pre-line;
            max-width: 100%;
        }}
        .timestamp {{
            text-align: right;
            color: #999;
            font-size: 12px;
            margin-top: 40px;
            border-top: 1px solid #eee;
            padding-top: 10px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        <div class="metadata">
            <p><strong>Source URL:</strong></p>
            <p class="source-url"><a href="{url}" target="_blank">{url}</a></p>
            <p><strong>Content Length:</strong> {len(content)} characters</p>
        </div>
        <div class="content">
    {body_fragment}
        </div>
        <div class="timestamp">
            Saved on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
</body>
</html>"""
        
        # Write to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"\n✅ File saved to: {filepath}")
        
        # Open the file in the default browser
        webbrowser.open('file://' + filepath)
        print(f"🌐 Opening file in browser...")

        return filepath
    except Exception as e:
        print(f"❌ Error saving file: {str(e)}")
        return None

def search_agent(query, max_results=5):
   
    # Initialize Tavily client
    api_key = os.environ.get('TAVILY_API_KEY')
    if not api_key:
        print("❌ No TAVILY_API_KEY found in environment variables")
        return None
    
    client = TavilyClient(api_key=api_key)
    
    # Print a header with emoji for user-friendly output
    print(f"\n🔍 SEARCH AGENT: Searching for '{query}'...\n")
    
    try:
        # Make the API call to Tavily's search endpoint
        # search_depth="advanced" gives us more comprehensive results
        # include_raw_content=True ensures we get full content, not summaries
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",  # Can be "basic" or "advanced"
            include_raw_content=True  # Get full page content
        )
    
        # Extract the results list from the response dictionary
        # .get() is safer than [] - returns None if key doesn't exist
        results = response.get('results', [])
        
        # Display count of results found
        print(f"Found {len(results)} results:\n")
        
        # Iterate through results with enumerate
        # enumerate(list, 1) starts counting from 1 instead of 0
        for i, result in enumerate(results, 1):
            # Each result is a dictionary with keys like 'title', 'url', 'content'
            print(f"\n{'='*70}")
            print(f"Result #{i}")
            print(f"{'='*70}")
            print(f"📌 Title: {result['title']}")
            print(f"🔗 URL: {result['url']}")
            
            # Show relevance score (if available)
            print(f"⭐ Relevance Score: {result.get('score', 'N/A')}")
            
            # Display FULL content - try raw_content first, then content
            full_content = result.get('raw_content', '') or result.get('content', '')
            content_length = len(full_content)
            print(f"📊 Content Length: {content_length} characters")
            
            print(f"\n📄 Full Content:")
            print(f"{'-'*70}")
            # Print the complete content without truncation
            print(full_content)
            print(f"{'-'*70}")
            print()  # Extra blank line for readability
            
            # Debug: Show what keys are available in the result
            print(f"🔍 Available data fields: {', '.join(result.keys())}")
            print()

            save_prompt = input("Do you want to save this result to a file? (y/n): ").strip()
            if save_prompt.lower() == 'y':
                # User wants to save - format as HTML and save to saved_html folder
                save_to_html(full_content, result['title'], result['url'])
                SRAM = input("Would you like to send this response via email? (y/n): ").strip()
                if SRAM.lower() == 'y':
                    RECIPIENT_EMAIL = input("Enter recipient email address: ").strip()
                    send_email(f"Search Result: {result['title']}", full_content, RECIPIENT_EMAIL)
                    return response
                else:
                    return response
            else:
                SRAM = input("Would you like to send this response via email? (y/n): ").strip()
                if SRAM.lower() == 'y':
                    RECIPIENT_EMAIL = input("Enter recipient email address: ").strip()
                    send_email(f"Search Result: {result['title']}", full_content, RECIPIENT_EMAIL)
                    return response 
                else:
                    return response   
                
        # Return the full response for potential further processing
        
        
    except Exception as e:
        # Catch any errors (network issues, API errors, etc.)
        # Always good practice to handle exceptions with APIs
        print(f"❌ Error in search: {str(e)}")
        return None





def main():
    """
    Main function: Entry point of the program
    
    This demonstrates:
    - Program structure and flow control
    - User input handling
    - Menu-driven interfaces
    - While loops for continuous operation
    
    Teaching Notes:
    - main() is a common convention for the program's entry point
    - We use while True for an infinite loop that runs until user chooses to exit
    - The menu pattern is common in CLI applications
    """
    # Print a nice header using string multiplication for the line
    print("=" * 60)
    print("🤖 TAVILY Research Document Creator")
    print("=" * 60)
    
    # Debug: Check if API key is loaded
    api_key = os.environ.get('TAVILY_API_KEY')
    if api_key:
        print(f"✅ API Key loaded: {api_key[:10]}..." if len(api_key) > 10 else "✅ API Key loaded")
    else:
        print("❌ No API key found in environment variables")
        print("\n🔍 Debugging Info:")
        print(f"   Current directory: {os.getcwd()}")
        print(f"   .env file exists: {os.path.exists('.env')}")
        if os.path.exists('.env'):
            print("\n   Contents of .env file:")
            with open('.env', 'r') as f:
                for line in f:
                    if 'TAVILY' in line:
                        print(f"   {line.strip()}")
    
# Initialize the GUI and run the application
if __name__ == "__main__":
    root = tk.Tk()
    gui = SearchGUI(root)
    setup_gui_redirection(gui)
    
    gui.append_text("=" * 60 + "\n")
    gui.append_text("🤖 TAVILY Research Document Creator\n")
    gui.append_text("=" * 60 + "\n\n")
    
    # Debug: Check if API key is loaded
    api_key = os.environ.get('TAVILY_API_KEY')
    if api_key:
        gui.append_text(f"✅ API Key loaded: {api_key[:10]}...\n\n" if len(api_key) > 10 else "✅ API Key loaded\n\n")
    else:
        gui.append_text("❌ No API key found in environment variables\n")
        gui.append_text("\n🔍 Debugging Info:\n")
        gui.append_text(f"   Current directory: {os.getcwd()}\n")
        gui.append_text(f"   .env file exists: {os.path.exists('.env')}\n")
        if os.path.exists('.env'):
            gui.append_text("\n   Contents of .env file:\n")
            with open('.env', 'r') as f:
                for line in f:
                    if 'TAVILY' in line:
                        gui.append_text(f"   {line.strip()}\n")
    
    # Run the search loop in a separate thread so the GUI remains responsive
    def run_search_loop():
        repeat_search = True
        while repeat_search:
            query = input("\nEnter a search query (or 'quit' to exit): ").strip()
            if query.lower() == "quit":
                repeat_search = False
                gui.append_text("\n👋 Goodbye!\n")
                root.quit()
            elif query:
                search_agent(query)
            else:
                gui.append_text("❌ Search query cannot be empty!\n")
    
    search_thread = threading.Thread(target=run_search_loop, daemon=True)
    search_thread.start()
    
    root.mainloop()
