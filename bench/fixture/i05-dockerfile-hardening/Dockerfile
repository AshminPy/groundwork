FROM python:latest
ADD https://example.com/tools/healthcheck.sh /usr/local/bin/healthcheck.sh
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
EXPOSE 8000
CMD python -m app
