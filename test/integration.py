import json
import subprocess
import shutil
import sys
import time
import os
import psutil
import pyautogui

# --- Configuration ---
TASK_TEXT = "Clean the kitchen"
TODOISM_COMMAND = "python3 -c \"import shutil, os; target='test/.todoism'; print(f'Safely cleaning {target}'); [os.remove(os.path.join(target, f)) for f in os.listdir(target) if os.path.isfile(os.path.join(target, f))]\" && python3 test/generate.py && python3 -m todoism --dev; exec zsh"
TODOISM_LAUNCH_WAIT = 1
KEY_DELAY = 0.2
ACTION_DELAY = 0.3
POST_TASK_VIEW_DELAY = 2.0

# --- Special Key Handling ---
def get_special_key_codes():
    """Get the special key codes from the settings file"""
    try:
        # First try the dev mode location
        settings_path = os.path.join("test", ".todoism", "settings.json")
        if not os.path.exists(settings_path):
            # If not found, try the user's home directory
            settings_path = os.path.expanduser("~/.todoism/settings.json")
        
        if os.path.exists(settings_path):
            with open(settings_path, 'r') as f:
                settings = json.load(f)
                return {
                    'ctrl_left': settings.get("ctrl+left", 0),
                    'ctrl_right': settings.get("ctrl+right", 0),
                    'ctrl_shift_left': settings.get("ctrl+shift+left", 0),
                    'ctrl_shift_right': settings.get("ctrl+shift+right", 0),
                    'alt_left': settings.get("alt+left", 0),
                    'alt_right': settings.get("alt+right", 0)
                }
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Warning: Could not load key codes from settings: {e}")
    
    # Return defaults if we couldn't load from settings
    return {'ctrl_left': 0, 'ctrl_right': 0, 'ctrl_shift_left': 0, 
            'ctrl_shift_right': 0, 'alt_left': 0, 'alt_right': 0}

def emulate_special_key(key_name):
    """Emulate a special key combination using the key code"""
    key_codes = get_special_key_codes()
    code = key_codes.get(key_name, 0)
    
    if code == 0:
        print(f"⚠️ Warning: No key code found for {key_name}, using fallback")
        # Fallback to standard PyAutoGUI key combinations
        if key_name == 'ctrl_left':
            pyautogui.hotkey('ctrl', 'left')
        elif key_name == 'ctrl_right':
            pyautogui.hotkey('ctrl', 'right')
        elif key_name == 'ctrl_shift_left':
            pyautogui.hotkey('ctrl', 'shift', 'left')
        elif key_name == 'ctrl_shift_right':
            pyautogui.hotkey('ctrl', 'shift', 'right')
        elif key_name == 'alt_left':
            pyautogui.hotkey('alt', 'left')
        elif key_name == 'alt_right':
            pyautogui.hotkey('alt', 'right')
    else:
        # If we have a key code, use it directly
        print(f"🔑 Sending special key {key_name} with code {code}")
        pyautogui.press(str(code))

# --- Keycode Recording Logic ---
def handle_keycode_recording():
    """Handle the keycode recording sequence if it appears"""
    print("🔑 Checking if keycode recording is needed...")
    time.sleep(TODOISM_LAUNCH_WAIT)
    press_key('enter', "🔑 Pressing Enter to start keycode recording (if needed)")
    time.sleep(ACTION_DELAY)
    key_combinations = [
        ('ctrl_left', ['ctrl', 'left']),
        ('ctrl_right', ['ctrl', 'right']),
        ('ctrl_shift_left', ['ctrl', 'shift', 'left']),
        ('ctrl_shift_right', ['ctrl', 'shift', 'right']),
        ('alt_left', ['alt', 'left']),
        ('alt_right', ['alt', 'right'])
    ]
    for name, keys in key_combinations:
        press_keys(keys, f"🔑 Emulating {name} key combination")
        time.sleep(KEY_DELAY)
        press_key('enter', "🔑 Pressing Enter to confirm")
    time.sleep(ACTION_DELAY)
    print("✅ Keycode recording complete")

# --- Supported Terminals ---
TERMINALS = [
    ("gnome-terminal", ["gnome-terminal", "--title=todoism-dev", "--", "zsh", "-c", "TODOISM_COMMAND"]),
    ("kitty", ["kitty", "-T", "todoism-dev", "zsh", "-c", "TODOISM_COMMAND"]),
    ("alacritty", ["alacritty", "-t", "todoism-dev", "-e", "zsh", "-c", "TODOISM_COMMAND"]),
    ("xterm", ["xterm", "-T", "todoism-dev", "-e", "zsh", "-c", "TODOISM_COMMAND"]),
    ("konsole", ["konsole", "--new-tab", "-p", "tabtitle=todoism-dev", "-e", "zsh", "-c", "TODOISM_COMMAND"]),
    ("iterm2", ["iterm2", "-T", "todoism-dev", "zsh", "-c", "TODOISM_COMMAND"]),
]

def detect_current_terminal():
    """
    Attempt to detect the current terminal emulator by traversing the parent process tree.
    Returns the terminal name if detected, else None.
    """
    try:
        p = psutil.Process(os.getppid())
        while p:
            name = p.name().lower()
            for term, _ in TERMINALS:
                if term in name:
                    return term
            p = p.parent()
    except Exception as e:
        print(f"[WARN] Could not detect terminal emulator: {e}")
    return None

def find_terminal():
    # Try to detect the current terminal emulator first
    detected = detect_current_terminal()
    if detected:
        for name, cmd in TERMINALS:
            if name == detected and shutil.which(name):
                print(f"[INFO] Detected current terminal emulator: {name}")
                # Replace placeholder with actual command if present
                actual_cmd = [c if c != "TODOISM_COMMAND" else TODOISM_COMMAND for c in cmd]
                return (name, actual_cmd)
        print(f"[WARN] Detected terminal '{detected}' not found in system. Falling back.")
    # Fallback to first available terminal
    for name, cmd in TERMINALS:
        if shutil.which(name):
            actual_cmd = [c if c != "TODOISM_COMMAND" else TODOISM_COMMAND for c in cmd]
            return (name, actual_cmd)
    print("\033[91m[ERROR] No supported terminal emulator found.\033[0m")
    sys.exit(1)

def focus_window(window_title_substring="todoism-dev"):
    try:
        output = subprocess.check_output(["wmctrl", "-l"]).decode()
        for line in output.splitlines():
            if window_title_substring.lower() in line.lower():
                win_id = line.split()[0]
                subprocess.run(["wmctrl", "-ia", win_id])
                return
        print("\033[91m[ERROR] Target window not found. Aborting test.\033[0m")
        sys.exit(1)
    except Exception as e:
        print(f"❌ wmctrl failed: {e}")
        sys.exit(1)

def press_key(key, desc=None):
    if desc:
        print(desc)
    focus_window()
    pyautogui.press(key)
    time.sleep(KEY_DELAY)

def press_str(str, desc=None):
    if desc:
        print(desc)
    for char in str:
        focus_window()
        pyautogui.write(char)
    time.sleep(KEY_DELAY)

def press_keys(keys, desc=None):
    if desc:
        print(desc)
    focus_window()
    for key in keys:
        pyautogui.press(key)
    time.sleep(KEY_DELAY)

def launch_todoism():
    cmd = find_terminal()
    print(f"🚀 Launching: {' '.join(cmd[1])}")
    subprocess.Popen(cmd[1])

def keycode_needs_recording():
    """Check if keycodes need to be recorded"""
    try:
        settings_path = os.path.join("test", ".todoism", "settings.json")
        if not os.path.exists(settings_path):
            settings_path = os.path.expanduser("~/.todoism/settings.json")
        
        if not os.path.exists(settings_path):
            return True
            
        with open(settings_path, 'r') as f:
            settings = json.load(f)
            # Check if any of the key codes are 0
            return (settings.get("ctrl+left", 0) == 0 and
                   settings.get("ctrl+right", 0) == 0 and
                   settings.get("ctrl+shift+left", 0) == 0 and
                   settings.get("ctrl+shift+right", 0) == 0 and
                   settings.get("alt+left", 0) == 0 and
                   settings.get("alt+right", 0) == 0)
    except Exception as _:
        return True

def emulate_keys():
    print("[INFO] Actions will be printed here in this terminal window.")
    time.sleep(TODOISM_LAUNCH_WAIT)
    print(f"⏳ Waiting for todoism to load...")
    time.sleep(TODOISM_LAUNCH_WAIT)
    
    # First handle keycode recording if needed
    if keycode_needs_recording():
        handle_keycode_recording()
    
    # Resume waiting to ensure the main todoism interface is loaded
    print(f"⏳ Waiting for main interface...")
    time.sleep(TODOISM_LAUNCH_WAIT)

    print("\n🤖 Sending keys with pyautogui...")

    arrow_keys = ['down', 'up', 'down', 'down', "down", "down", "down", "up"]
    for key in arrow_keys:
        press_key(key, f"🔸 Pressing Arrow {key}")

    # Open help with :help
    press_key(':', "❓ Opening help with :help")
    press_str("help", "🔑 Typing 'help'")
    press_key('enter', "❓ Pressing Enter to submit command")
    # Close help with 'q'
    press_key('q', "❌ Closing help with 'q'")

    # Open settings (preference panel) with :pref
    press_key(':', "⚙️ Opening settings with :pref")
    press_str("pref", "🔑 Typing 'pref'")
    press_key('enter', "⚙️ Pressing Enter to submit command")

    # Change and toggle multiple settings using Up/Down to navigate and Tab to toggle
    focus_window()
    print("📝 Navigating and toggling all settings in preferences (Up/Down to move, Tab to toggle)")
    settings = [
        "Strikethrough",
        "Bold Text",
        "Tag in All Tasks",
        "Theme",
        "Date format",
        "Sort by flagged",
        "Sort by done"
    ]
    # Always start at Strikethrough (first option)
    for i, setting in enumerate(settings):
        if i > 0:
            press_key('down', f"↳ Moving Down to {setting}")
        press_key('tab', f"↳ Toggling {setting} (Tab)")

    # Wrap around to first setting and toggle again
    for _ in range(len(settings)-1):
        press_key('up', "↳ Wrapping to first setting (Up)")
    press_key('tab', "↳ Toggling Strikethrough again (Tab)")
    # Close settings with 'q'
    press_key('q', "❌ Closing settings with 'q'")

    # Switch focus to sidebar (categories) with Tab
    press_key('tab', "🗂️ Switching focus to sidebar (Tab)")
    # Move up/down in categories
    press_key('down', "⬇️ Moving down in categories")
    press_key('up', "⬆️ Moving up in categories")

    # Add new category (cat) with 'a'
    press_key('a', "➕ Adding new category with 'a'")

    # Type category name
    new_cat_name = "Test Cat"
    press_str(new_cat_name, f"🔤 Typing new category name: {new_cat_name}")
    press_key('enter', "✅ Submitting category with Enter")

    # Switch focus back to tasks with Tab
    press_key('tab', "📋 Switching focus back to tasks (Tab)")

    # Add a new task
    press_key('a', "📝 Pressing 'a' to add task...")
    press_str(TASK_TEXT, f"🔤 Typing task char by char: {TASK_TEXT}")
    press_key('enter', "✅ Submitting task with Enter")

    # Switch focus to sidebar (categories) with Tab
    press_key('tab', "🗂️ Switching focus to sidebar (Tab)")
    press_key('up', "⬆️ Moving up 1 category")
    press_key('up', "⬆️ Moving up 1 category")
    press_key('tab', "↳ Moving to category")

    # --- Task edit, flag, done ---
    # Edit task
    press_key('e', "✏️ Editing task with 'e'")
    new_task_part = "Edited Task "
    print(f"🔤 Typing new task: {new_task_part}")
    press_str(new_task_part, f"🔤 Typing new task: {new_task_part}")
    press_key('enter', "✅ Submitting new task with Enter")
    press_key('f', "⚑ Attempting to flag task with 'f'")
    press_key('d', "✓ Attempting to mark task as done with 'd'")

    # Quit app
    press_key('q', "🚪 Pressing 'q' to quit")
    print("\n✅ All done!")

if __name__ == "__main__":
    print("\033[38;5;202m[INFO] The test window will be focused. Please do not interact with other windows, as real key inputs will be emulated!\033[0m")
    print("[INFO] Make sure Caps Lock is OFF")
    print("[INFO] Press ENTER to confirm and start the test...")
    
    while True:
        try:
            user_input = input()
            if user_input == '':
                break
            else:
                print("\033[38;5;202m[INFO] Please press only ENTER to start.\033[0m")
        except KeyboardInterrupt:
            print("\nAborted by user.")
            exit(1)
    launch_todoism()
    time.sleep(TODOISM_LAUNCH_WAIT)
    emulate_keys()
