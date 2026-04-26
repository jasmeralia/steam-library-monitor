FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app && mkdir /data && chown app:app /data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir .

USER app

CMD ["python", "-m", "steam_library_monitor"]
