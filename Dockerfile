FROM python:3.7.3-alpine
RUN mkdir /app

COPY requirements.txt /app
RUN pip install -r requirements.txt
COPY banker.py /app

WORKDIR /app


ENTRYPOINT ["python", "banker.py"]

