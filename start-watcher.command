#!/bin/bash
# This script starts the watcher in the background using the virtual environment
cd "$(dirname "$0")"
nohup ./venv/bin/python -u watcher.py &
osascript -e 'display notification "The Synk Watcher has started." with title "Synk Watcher"'