#!/data/data/com.termux/files/usr/bin/sh
# تشغيل الخادم على Termux:  sh run.sh        (FastAPI)   |   sh run.sh lite   (بدون FastAPI)
cd "$(dirname "$0")/backend" || exit 1
if [ "$1" = "lite" ]; then exec python server_lite.py; fi
exec uvicorn main:app --host 127.0.0.1 --port 8000
