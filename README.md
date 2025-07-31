# 🚀 Synk

A lightning-fast command-line tool for tracking your time in Moco and JIRA. Spend less time logging, more time working.

## What is this?

Synk is a simple Python script that asks you a series of questions in your terminal and uses your answers to create time entries in Moco and log work in JIRA simultaneously. It's designed to be efficient, smart, and easy to use.

## Features

* **Interactive CLI**: A beautiful and clear command-line interface.
* **Smart Project Fetching**: Automatically fetches and filters your active, assigned Moco projects and tasks.
* **JIRA Integration**: Validates JIRA ticket numbers and adds worklogs automatically.
* **Continuous Tracking**: The "last" command automatically uses the end time of your previous entry as the start time for the next.
* **Configurable Default Task**: Set a default task (e.g., "CH: Main") to make your most common entries even faster.
* **Looping**: Add multiple entries for a day without restarting the tool.

## Getting Started (Easy Method)

Follow these simple steps to get Synk up and running.

### Step 1: Install Python

Synk is a Python script, so you need Python installed. On macOS, it's likely already there.

1.  Open the **Terminal** app.
2.  Type `python3 --version` and press Enter.
3.  If you see a version number (like `Python 3.9.6`), you're all set! If not, download and install the latest version of Python from the [official Python website](https://www.python.org/downloads/).

### Step 2: Download Synk

1.  Go to the Synk repository page.
2.  Click the green **`Code`** button.
3.  Select **Download ZIP**.
4.  Find the downloaded `synk-main.zip` file (usually in your Downloads folder) and double-click it to unzip it. You will now have a `synk-main` folder.

### Step 3: Run the Installer

The installer will check for dependencies, help you create your configuration file, and make the scripts ready to use.

1.  Open the **Terminal** app.
2.  Type `cd ` (with a space after `cd`).
3.  Drag the `synk-main` folder you unzipped and drop it directly onto the Terminal window. The path to the folder will appear.
4.  Press **Enter**. Your terminal is now inside the Synk folder.
5.  Run the installer with this command:
    ```bash
    python3 install.py
    ```
6.  The installer will guide you through the rest of the setup.

## How to Run Synk

After running the installer, you can start using Synk by double-clicking the command files in the `synk-main` folder:

* **`start-synk.command`**: Opens a new terminal window and starts the interactive time tracker.
* **`start-watcher.command`**: Silently starts the background reminder process.
* **`stop-watcher.command`**: Stops the background reminder process.

---

## Manual Installation (Advanced)

If you prefer to set things up manually, follow these steps instead of running the installer.

1.  **Install Dependencies**:
    ```bash
    pip3 install -r requirements.txt
    ```
2.  **Create Configuration File**:
    * Rename `.env.example` to `.env`.
    * Open the `.env` file and fill in your Moco and JIRA credentials.
3.  **Make Scripts Executable**:
    ```bash
    chmod +x *.command
    ```