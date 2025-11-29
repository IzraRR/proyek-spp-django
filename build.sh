#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Kumpulkan file static (css/gambar)
python manage.py collectstatic --no-input

# Jalankan migrasi database
python manage.py migrate