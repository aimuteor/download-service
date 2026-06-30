#!/bin/bash
# Unzip config.yaml from encrypted archive
# Usage: ./config/unzip_config.sh

CONFIG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARCHIVE_FILE="$CONFIG_DIR/config.yaml.7z"
CONFIG_FILE="$CONFIG_DIR/config.yaml"

echo "=== Unzip Config Script ==="

if [ ! -f "$ARCHIVE_FILE" ]; then
    echo "Error: Encrypted archive not found at $ARCHIVE_FILE"
    exit 1
fi

echo "Unzipping $ARCHIVE_FILE"
echo "You will be prompted for the password."

# Prompt for password
read -sp "Enter password: " PASSWORD
echo ""

# Extract the archive (overwrite if exists)
7z x -p"$PASSWORD" -y "$ARCHIVE_FILE" -o"$CONFIG_DIR"

if [ $? -eq 0 ]; then
    echo "Success! Extracted config.yaml"
else
    echo "Error: Failed to extract archive (wrong password?)"
    exit 1
fi
