#!/bin/bash
# This script starts the watcher in the background
cd "$(dirname "$0")"
nohup python3 -u watcher.py &
osascript -e 'display notification "The Synk Watcher has started." with title "Synk Watcher"'