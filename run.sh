#!/bin/bash
# Run script for download service

MINICONDA_DIR="/home/$(whoami)/miniconda3/etc/profile.d"
source ${MINICONDA_DIR}/conda.sh

conda activate dl-svc

python -m src.main
