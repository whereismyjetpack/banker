FROM python:3.9.6-alpine
RUN mkdir /app && \
  adduser app -D

USER app

WORKDIR /app
COPY requirements.txt /app
RUN pip install --no-cache-dir -r requirements.txt
COPY banker.py /app


ENTRYPOINT [ "python", "banker.py" ]

