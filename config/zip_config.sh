#!/bin/bash
# Zip config.yaml with password protection
# Usage: ./config/zip_config.sh

CONFIG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$CONFIG_DIR/config.yaml"
ARCHIVE_FILE="$CONFIG_DIR/config.yaml.7z"

echo "=== Zip Config Script ==="

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: config.yaml not found at $CONFIG_FILE"
    exit 1
fi

echo "Zipping $CONFIG_FILE to $ARCHIVE_FILE"
echo "You will be prompted for the password."

# Prompt for password (with confirmation)
read -sp "Enter password: " PASSWORD
echo ""
read -sp "Confirm password: " PASSWORD2
echo ""

if [ "$PASSWORD" != "$PASSWORD2" ]; then
    echo "Error: Passwords do not match!"
    exit 1
fi

# Create the encrypted archive
7z a -p"$PASSWORD" "$ARCHIVE_FILE" "$CONFIG_FILE"

if [ $? -eq 0 ]; then
    echo "Success! Created encrypted archive: $ARCHIVE_FILE"
else
    echo "Error: Failed to create archive"
    exit 1
fi
