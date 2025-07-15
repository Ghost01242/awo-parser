FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    chromium wget unzip curl gnupg ca-certificates fonts-liberation \
    libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1 libxss1 \
    libappindicator1 libasound2 xdg-utils \
 && apt-get purge -y chromium-driver \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV CHROME_BIN=/usr/bin/chromium

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

COPY main.py /app/

CMD ["python", "main.py"]
