# auto_guest_liker.py
# Free Fire Automated Guest Login & Like Bot for MSI App Player / BlueStacks
# Supports batch processing 100-200+ accounts from accounts.json

import os
import sys
import json
import time
import subprocess
from typing import List, Dict, Optional

# ==================== CONFIGURATION ====================
# Default path to your accounts.json file
ACCOUNTS_JSON_PATH = r"C:\Users\ujjal\OneDrive\Desktop\ff\accounts.json"

# List of player UIDs to give like to
TARGET_UIDS = [
    "1187994195",  # Replace with your target player UID 1
    # "1234567890",  # UID 2
    # "9876543210",  # UID 3
]

# MSI / BlueStacks ADB candidates
ADB_CANDIDATES = [
    r"C:\Program Files\BlueStacks_msi5\HD-Adb.exe",
    r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe",
    r"C:\Program Files\BlueStacks\adb.exe",
    "adb.exe"
]

ADB_PORTS = ["127.0.0.1:5555", "127.0.0.1:5556"]

# Normalized coordinates (ratio 0.0 to 1.0 based on 1600x900 resolution)
# Screen width * rx, Screen height * ry
COORDINATES = {
    # 1. Login Screen
    "login_guest_btn": (0.42, 0.78),       # "Guest" icon on login screen
    "tap_to_begin": (0.50, 0.70),          # "Tap to Begin" in title screen
    "close_announcement": (0.92, 0.12),    # 'X' button on lobby popups/events

    # 2. Lobby
    "lobby_friends_btn": (0.83, 0.05),     # Friends icon in lobby top-right

    # 3. Friends Screen
    "friends_add_tab": (0.05, 0.58),       # "ADD" tab on the left sidebar
    "search_input_box": (0.35, 0.20),      # Search text input box
    "search_submit_btn": (0.88, 0.20),     # Magnifying glass / search button
    "search_result_player": (0.28, 0.31),  # Click player card from search result

    # 4. Profile Modal (Right side)
    "profile_like_btn": (0.82, 0.25),      # Thumbs-up / Like button on profile
    "profile_close_outside": (0.25, 0.50), # Tap outside modal to close profile
    "friends_close_btn": (0.97, 0.05),     # 'X' icon top-right of Friends screen

    # 5. Logout
    "lobby_settings_btn": (0.96, 0.05),    # Gear icon top-right in lobby
    "settings_logout_btn": (0.88, 0.92),   # "LOG OUT" button in Basic settings
    "logout_confirm_ok": (0.60, 0.60),     # "OK" / Confirm on Logout dialog
}

# Delays in seconds
DELAYS = {
    "after_tap": 1.2,
    "app_loading": 12.0,
    "login_enter_lobby": 8.0,
    "search_result_wait": 2.5,
    "logout_wait": 3.0,
}

class FFAutoGuestLiker:
    def __init__(self, adb_path: str, accounts_file: str, target_uids: List[str]):
        self.adb_path = adb_path
        self.accounts_file = accounts_file
        self.target_uids = target_uids
        self.screen_width = 1600
        self.screen_height = 900
        self.guest_file_path = None

    def run_adb(self, args: str) -> str:
        cmd = f'"{self.adb_path}" {args}'
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            return (result.stdout or result.stderr).strip()
        except Exception as e:
            return f"Error: {e}"

    def connect(self) -> bool:
        print("[*] Connecting to MSI App Player via ADB...")
        # Check already attached
        dev_output = self.run_adb("devices")
        if "device" in dev_output and not "offline" in dev_output:
            for line in dev_output.splitlines():
                if "\tdevice" in line:
                    print(f"[+] Device connected: {line.split()[0]}")
                    self.detect_screen_size()
                    return True

        # Try connecting ports
        for port in ADB_PORTS:
            print(f"[*] Trying port {port}...")
            out = self.run_adb(f"connect {port}")
            if "connected" in out.lower() and "cannot" not in out.lower():
                print(f"[+] Successfully connected to {port}")
                self.detect_screen_size()
                return True

        print("[-] Could not connect to any ADB port. Make sure MSI App Player is running.")
        return False

    def detect_screen_size(self):
        output = self.run_adb("shell wm size")
        # e.g., "Physical size: 1600x900"
        if "Physical size:" in output:
            try:
                size_str = output.split("Physical size:")[-1].strip()
                w, h = size_str.split("x")
                self.screen_width = int(w)
                self.screen_height = int(h)
                print(f"[+] Screen resolution detected: {self.screen_width}x{self.screen_height}")
            except Exception:
                pass

    def tap(self, name: str, custom_rx: float = None, custom_ry: float = None, delay: float = None):
        if custom_rx is not None and custom_ry is not None:
            rx, ry = custom_rx, custom_ry
        else:
            rx, ry = COORDINATES[name]
        
        x = int(self.screen_width * rx)
        y = int(self.screen_height * ry)
        self.run_adb(f"shell input tap {x} {y}")
        time.sleep(delay if delay is not None else DELAYS["after_tap"])

    def type_text(self, text: str):
        self.run_adb(f"shell input text {text}")
        time.sleep(1.0)

    def press_key(self, keycode: int):
        self.run_adb(f"shell input keyevent {keycode}")
        time.sleep(1.0)

    def locate_guest_file(self) -> Optional[str]:
        output = self.run_adb("shell ls /sdcard/com.garena.msdk/guest*.dat")
        if "No such file" in output or not output:
            return None
        lines = [l.strip() for l in output.splitlines() if l.strip() and not l.startswith("ls:")]
        if lines:
            self.guest_file_path = lines[0]
            return self.guest_file_path
        return None

    def update_guest_credentials(self, uid: str, password: str) -> bool:
        if not self.guest_file_path:
            self.locate_guest_file()
            if not self.guest_file_path:
                print("[-] Guest dat file not found in /sdcard/com.garena.msdk/")
                return False

        payload = f'{{"guest_account_info":{{"com.garena.msdk.guest_uid":"{uid}","com.garena.msdk.guest_password":"{password}"}}}}'
        escaped_payload = payload.replace('"', '\\"')
        cmd = f'shell "echo {escaped_payload} > {self.guest_file_path}"'
        res = self.run_adb(cmd)
        if "Permission denied" in res or "Error" in res:
            print(f"[-] Failed to update guest info: {res}")
            return False
        return True

    def login_with_guest(self):
        print("  -> Tapping Guest login button...")
        self.tap("login_guest_btn", delay=2.5)
        print("  -> Tapping to enter lobby...")
        self.tap("tap_to_begin", delay=DELAYS["login_enter_lobby"])
        # Dismiss any popup banners
        self.tap("close_announcement", delay=1.0)
        self.tap("close_announcement", delay=1.0)

    def give_likes_to_targets(self):
        print("  -> Opening Friends screen...")
        self.tap("lobby_friends_btn", delay=2.0)
        print("  -> Selecting ADD tab...")
        self.tap("friends_add_tab", delay=1.5)

        for target_uid in self.target_uids:
            print(f"  -> Searching UID: {target_uid}...")
            # Tap input box
            self.tap("search_input_box", delay=1.0)
            # Clear or input text
            self.type_text(target_uid)
            # Submit search
            self.tap("search_submit_btn", delay=DELAYS["search_result_wait"])
            # Or press enter
            self.press_key(66)  # KEYCODE_ENTER
            time.sleep(1.0)

            # Click search result player
            print("  -> Opening player profile...")
            self.tap("search_result_player", delay=2.0)

            # Click Like button
            print(f"  -> [LIKE] Giving like to {target_uid}...")
            self.tap("profile_like_btn", delay=1.5)

            # Close profile modal
            self.tap("profile_close_outside", delay=1.0)

        # Close Friends window
        self.tap("friends_close_btn", delay=1.5)

    def logout(self):
        print("  -> Logging out...")
        self.tap("lobby_settings_btn", delay=1.5)
        self.tap("settings_logout_btn", delay=1.5)
        self.tap("logout_confirm_ok", delay=DELAYS["logout_wait"])

    def process_all_accounts(self):
        if not os.path.exists(self.accounts_file):
            print(f"[-] Accounts file not found: {self.accounts_file}")
            return

        with open(self.accounts_file, "r", encoding="utf-8") as f:
            accounts = json.load(f)

        total = len(accounts)
        print(f"[+] Loaded {total} accounts from {self.accounts_file}")
        print(f"[+] Target UIDs to like: {self.target_uids}")

        success_count = 0
        for idx, acc in enumerate(accounts, 1):
            uid = acc.get("uid")
            pwd = acc.get("password")
            nick = acc.get("nickname", "Unknown")

            if not uid or not pwd:
                print(f"[-] Skipping account #{idx}: Missing UID or Password.")
                continue

            print(f"\n==================================================")
            print(f"[{idx}/{total}] Processing: {nick} (UID: {uid})")
            print(f"==================================================")

            # 1. Update credentials in guest file
            if not self.update_guest_credentials(uid, pwd):
                print(f"[-] Could not update credentials for {uid}. Skipping.")
                continue

            # 2. Login
            self.login_with_guest()

            # 3. Give likes to targets
            try:
                self.give_likes_to_targets()
                success_count += 1
            except Exception as e:
                print(f"[-] Error while giving likes: {e}")

            # 4. Logout for next iteration
            self.logout()

        print("\n==================================================")
        print(f"[+] Finished batch run! Successfully processed {success_count}/{total} accounts.")
        print("==================================================")

def find_adb() -> Optional[str]:
    for path in ADB_CANDIDATES:
        if os.path.exists(path) or path == "adb.exe":
            return path
    return None

if __name__ == "__main__":
    adb = find_adb()
    if not adb:
        print("[-] Could not find HD-Adb.exe or adb.exe.")
        sys.exit(1)

    bot = FFAutoGuestLiker(
        adb_path=adb,
        accounts_file=ACCOUNTS_JSON_PATH,
        target_uids=TARGET_UIDS
    )

    if bot.connect():
        bot.process_all_accounts()
    else:
        print("[-] Exiting. Please open MSI App Player first.")
