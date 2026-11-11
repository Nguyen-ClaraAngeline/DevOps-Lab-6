FROM python:3.12-slim-bookworm AS build
WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:$PATH"
RUN useradd --system --uid 10001 --no-create-home appuser
COPY --from=build /opt/venv /opt/venv
WORKDIR /app
COPY worker.py .
USER 10001
CMD ["python", "worker.py"]