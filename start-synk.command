#!/bin/bash
# This script runs the main time-tracking tool using the virtual environment
cd "$(dirname "$0")"
./venv/bin/python track_time.py "$@"