# 🚀 Synk

A lightning-fast command-line tool for tracking your time in Moco and JIRA. Spend less time logging, more time working.

## What is this?

Synk is a simple Python script that asks you a series of questions in your terminal (e.g., "What project?", "What task?") and uses your answers to create time entries in Moco and log work in JIRA simultaneously. It's designed to be efficient, smart, and easy to use.

## Features

* **Interactive CLI**: A beautiful and clear command-line interface.
* **Smart Project Fetching**: Automatically fetches and filters your active, assigned Moco projects and tasks.
* **JIRA Integration**: Validates JIRA ticket numbers and adds worklogs automatically.
* **Continuous Tracking**: The "last" command automatically uses the end time of your previous entry as the start time for the next.
* **Configurable Default Task**: Set a default task (e.g., "CH: Main") to make your most common entries even faster.
* **Looping**: Add multiple entries for a day without restarting the tool.

## Getting Started

Follow these steps to get Synk up and running on your machine.

### Step 1: Install Python

Synk is a Python script, so you need Python installed. On macOS, it's likely already there.

1.  Open the **Terminal** app.
2.  Type `python3 --version` and press Enter.
3.  If you see a version number (like `Python 3.9.6`), you're all set! If not, download and install the latest version of Python from the [official Python website](https://www.python.org/downloads/).

### Step 2: Download Synk

1.  Go to the Synk repository page.
2.  Click the green **`< > Code`** button.
3.  Select **Download ZIP**.
4.  Find the downloaded `synk-main.zip` file (usually in your Downloads folder) and double-click it to unzip it. You will now have a `synk-main` folder.

### Step 3: Install Dependencies

1.  Open the **Terminal** app.
2.  Type `cd ` (with a space after `cd`).
3.  Drag the `synk-main` folder you unzipped and drop it directly onto the Terminal window. The path to the folder will appear.
4.  Press **Enter**. Your terminal is now inside the Synk folder.
5.  Copy and paste the following command into your terminal and press **Enter**:
    ```bash
    pip3 install -r requirements.txt
    ```
    This will install all the libraries Synk needs to run.

### Step 4: Create Your Configuration File

Synk needs your personal API keys to connect to Moco and JIRA.

1. In the `synk-main` folder, find the file named `.env.example`.
2. **Rename** this file to just `.env`. (Note the dot at the beginning).
3. Open the new `.env` file with a text editor (like TextEdit on macOS).
4. Fill in your details for each variable.

```ini
# --- .env file ---

# -- Moco Configuration --
# Your company's Moco subdomain (the part before .mocoapp.com)
MOCO_SUBDOMAIN="one-inside"
# Your Moco API Key. Find it in Moco under your Profile -> API Access (https://one-inside.mocoapp.com/profile/integrations)
MOCO_API_KEY="your-moco-api-key"

# -- JIRA Configuration --
# Your company's JIRA URL
JIRA_SERVER="[https://your-domain.atlassian.net](https://your-domain.atlassian.net)"
# The email you use to log in to JIRA
JIRA_USER_EMAIL="your-email@example.com"
# Your JIRA API Token. Generate one here: [https://id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
JIRA_API_TOKEN="your-jira-api-token"

# -- Optional: Default Task Name --
# Use a regex pattern to match your most common task.
# Example: To match "CH: Main | ZT/...", use "^CH: Main"
DEFAULT_TASK_NAME="^CH: Main"
```

## How to Run Synk

1. Open your Terminal app.
2. Navigate to the Synk folder using the cd command as you did in Step 3.
3. Run the tool with this command:
```bash
python3 track_time.py
```

Synk will start, and you can begin tracking your time!