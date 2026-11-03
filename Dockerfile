FROM python:3.12-slim
RUN useradd -m -u 1000 user
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY --chown=user backend backend
COPY --chown=user docs docs
RUN mkdir -p /app/data && chown user /app/data
USER user
ENV SMM_DB=/app/data/smm.db PORT=7860
WORKDIR /app/backend
EXPOSE 7860
CMD ["sh", "-c", "(python importer.py --source football-data --competition PL,ELC,BL1,SA,PD,FL1,DED,PPL,BSA,CL,EC,WC; while true; do sleep 21600; python importer.py --source football-data --competition PL,ELC,BL1,SA,PD,FL1,DED,PPL,BSA,CL,EC,WC; done) & uvicorn main:app --host 0.0.0.0 --port 7860"]
