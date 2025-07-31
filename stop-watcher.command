#!/bin/bash
# This script finds and stops the watcher process
pkill -f "python3 -u watcher.py"
osascript -e 'display notification "The Synk Watcher has been stopped." with title "Synk Watcher"'