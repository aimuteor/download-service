#!/bin/bash
# Setup cronjob for download service
# Run this script to install the cron job

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_PATH=$(which python3)
DOWNLOAD_SERVICE_DIR="$SCRIPT_DIR"

# Default cron schedule: every 5 minutes
CRON_SCHEDULE="*/5 * * * *"

echo "=== Download Service Cron Setup ==="
echo ""
echo "This script will set up a cron job to run the download service."
echo ""
echo "Current settings:"
echo "  Schedule: $CRON_SCHEDULE (every 5 minutes)"
echo "  Working directory: $DOWNLOAD_SERVICE_DIR"
echo "  Python: $PYTHON_PATH"
echo ""

# Ask for confirmation
read -p "Install cron job? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 1
fi

# Create the cron command
CRON_CMD="*/5 * * * * cd $DOWNLOAD_SERVICE_DIR && $PYTHON_PATH -m src.main >> logs/cron.log 2>&1"

# Install cron job
(crontab -l 2>/dev/null | grep -v "src.main$"; echo "$CRON_CMD") | crontab -

echo ""
echo "Cron job installed successfully!"
echo ""
echo "To verify, run: crontab -l"
echo ""
echo "Log file: $DOWNLOAD_SERVICE_DIR/logs/cron.log"
echo ""
echo "To remove the cron job, run:"
echo "  crontab -e"
echo "Then delete the line containing 'src.main'"
