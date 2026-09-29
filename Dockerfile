FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MPLCONFIGDIR=/tmp/mpl \
    PORT=5000

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY vulture ./vulture

# Hugging Face Spaces runs containers as a non-root user
RUN useradd -m -u 1000 wps && mkdir -p /tmp/vulture-mock /tmp/mpl && chown -R wps /tmp/vulture-mock /tmp/mpl
USER wps

EXPOSE 5000
CMD gunicorn -b 0.0.0.0:${PORT} -w 1 --threads 4 --timeout 120 vulture.wsgi:application
