#!/bin/bash
# Setup script for download service environment

MINICONDA_DIR="/home/$(whoami)/miniconda3/etc/profile.d"
source ${MINICONDA_DIR}/conda.sh

# Create environment if needed
if ! conda env list | grep -q "dl-svc"; then
    echo "Creating conda environment 'dl-svc'..."
    conda create --name dl-svc python=3.14 -y
else
    echo "Environment 'dl-svc' already exists."
fi

# Activate environment
conda activate dl-svc

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

echo "Setup complete! Run './run.sh' to start the service."
