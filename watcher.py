import os
import re
import sys
import time
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

try:
    import pync
except ImportError:
    print("❌ Error: The 'pync' library is not installed.")
    print("Please install it by running: pip3 install pync")
    sys.exit(1)

# --- CONFIGURATION ---
# How often to check for new entries (in seconds)
CHECK_INTERVAL = 900  # 15 minutes

# How long to wait after the last entry before sending a notification (in seconds)
REMINDER_THRESHOLD = 900  # 15 minutes

# --- API HELPER FUNCTIONS ---
def get_moco_credentials():
    """Load Moco credentials from the .env file."""
    load_dotenv()
    subdomain = os.getenv("MOCO_SUBDOMAIN")
    api_key = os.getenv("MOCO_API_KEY")
    user_id = None  # We'll fetch this

    if not all([subdomain, api_key]):
        print("❌ Error: MOCO_SUBDOMAIN or MOCO_API_KEY not found in .env file.")
        print("Please ensure your .env file is configured correctly.")
        return None, None, None

    # Verify credentials and fetch user ID
    try:
        headers = {'Authorization': f'Bearer {api_key}'}
        session_url = f"https://{subdomain}.mocoapp.com/api/v1/session"
        response = requests.get(session_url, headers=headers)
        response.raise_for_status()
        user_id = response.json().get('id')
    except (requests.exceptions.RequestException, KeyError):
        return None, None, None

    return subdomain, api_key, user_id

def get_last_entry_end_time(subdomain, api_key, user_id):
    """
    Fetch the end time of the user's last entry for today.
    Returns a datetime object or None.
    """
    today_iso = datetime.now().date().isoformat()
    headers = {'Authorization': f'Bearer {api_key}'}
    params = {'user_id': user_id, 'from': today_iso, 'to': today_iso}
    
    try:
        response = requests.get(f"https://{subdomain}.mocoapp.com/api/v1/activities", headers=headers, params=params)
        response.raise_for_status()
        activities = response.json()
    except requests.exceptions.RequestException:
        return None # Fail silently, we'll try again later

    if not activities:
        return None

    activities.sort(key=lambda x: x.get('id', 0), reverse=True)
    description = activities[0].get("description", "")
    match = re.search(r'\((\d{2}:\d{2})-(\d{2}:\d{2})\)', description)

    if match:
        end_time_str = match.group(2)
        # Combine today's date with the parsed end time
        return datetime.strptime(f"{today_iso} {end_time_str}", "%Y-%m-%d %H:%M")
    
    return None

# --- MAIN WATCHER LOOP ---
def main():
    """Main function to run the watcher script."""
    print("🚀 Synk Watcher started.")
    print(f"🕒 Checking for new time entries every {CHECK_INTERVAL / 60:.0f} minutes.")
    print("Press Ctrl+C to stop.")

    subdomain, api_key, user_id = get_moco_credentials()
    if not user_id:
        print("❌ Could not verify Moco credentials. Exiting.")
        sys.exit(1)

    try:
        while True:
            last_entry_time = get_last_entry_end_time(subdomain, api_key, user_id)
            
            if last_entry_time:
                now = datetime.now()
                # Check if the last entry is still ongoing or in the past
                if last_entry_time > now:
                    print(f"[{now.strftime('%H:%M:%S')}] Current entry ends at {last_entry_time.strftime('%H:%M')}.")
                else:
                    time_since_last_entry = now - last_entry_time
                    print(f"[{now.strftime('%H:%M:%S')}] Last entry ended at {last_entry_time.strftime('%H:%M')}. ({time_since_last_entry.seconds / 60:.0f} mins ago)")

                    if time_since_last_entry.total_seconds() > REMINDER_THRESHOLD:
                        print("🔔 Sending notification...")
                        pync.notify(
                            "It's been a while since your last time entry.",
                            title="Time to Synk?",
                            subtitle="Don't forget to log your time!",
                            # This will re-focus your terminal window when you click it
                            activate='com.apple.Terminal' 
                        )
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] No entries found for today yet.")

            # Wait for the next check
            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("\n👋 Synk Watcher stopped. Goodbye!")
        sys.exit(0)
    except Exception as e:
        # Log any other unexpected errors
        pync.notify(f"An error occurred: {e}", title="Synk Watcher Error")
        print(f"❌ An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
