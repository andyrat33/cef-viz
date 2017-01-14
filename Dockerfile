FROM python:3.5
ADD . /app
WORKDIR /app
RUN pip install -r requirements.txt
ENTRYPOINT [ "python" ]
CMD [ "/app/cef-viz.py"]
