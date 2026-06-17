#!/bin/bash
if [ ! -d "venv" ]; then
    python -m venv venv
fi
source venv/Scripts/activate
pip install -r requirements.txt
uvicorn main:app --reload
