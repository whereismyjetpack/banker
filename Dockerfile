FROM python:3.9.1-alpine
RUN mkdir /app

WORKDIR /app
COPY requirements.txt /app
RUN pip install -r requirements.txt
COPY banker.py /app


ENTRYPOINT [ "python", "banker.py" ]

