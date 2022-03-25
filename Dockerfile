FROM python:3.10.4-alpine
RUN mkdir /app

RUN adduser app -D

USER app

WORKDIR /app
COPY requirements.txt /app
RUN pip install -r requirements.txt
COPY banker.py /app


ENTRYPOINT [ "python", "banker.py" ]

