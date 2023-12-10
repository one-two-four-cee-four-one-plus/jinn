FROM python:3.10

WORKDIR /app
COPY . /app

RUN pip install -r requirements.txt && mkdir -p /var/www/data

CMD ["uwsgi", "--ini", "uwsgi.ini"]
