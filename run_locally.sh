#!/bin/bash
source .venv/bin/activate

gunicorn main:app --reload --bind 0.0.0.0:5000 
cd frontend/
npm run dev &
