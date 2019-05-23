FROM python:3.7.3-alpine
RUN mkdir /app

COPY requirements.txt /app
COPY banker.py /app

WORKDIR /app

RUN pip install -r requirements.txt

ENTRYPOINT ["python", "banker.py"]

