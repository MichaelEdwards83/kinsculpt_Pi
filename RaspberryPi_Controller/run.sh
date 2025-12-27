#!/bin/bash
echo "Installing Dependencies..."
pip3 install -r requirements.txt

echo "Starting Controller..."
python3 main.py
