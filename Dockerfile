FROM python:3.10-slim

WORKDIR /app

COPY main.py /app/
COPY requirements.txt /app/

RUN pip install -r /app/requirements.txt

CMD ["python", "main.py"]
