FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py .
COPY profile.yml .
RUN python -c "from builder_profile import load_profile; load_profile()"
ENV PYTHONUNBUFFERED=1 OUT_DIR=/app/out
ENTRYPOINT ["python", "digest.py"]
