FROM python:3.5
ADD . /app
WORKDIR /app
RUN pip install -r requirements.txt

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/gunicorn", "--config", "/app/gunicorn.conf", "--bind", ":8080", "cef-viz:app"]
