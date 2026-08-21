FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-cloud.txt .
RUN pip install --no-cache-dir -r requirements-cloud.txt

COPY analyze_labeled_multispectral.py plantspec_quickviewer.py ./
COPY api/ api/

ENV PORT=8080
ENV PYTHONUNBUFFERED=1
ENV MPLBACKEND=Agg

EXPOSE 8080

CMD exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT} --workers 1
