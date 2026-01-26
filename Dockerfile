FROM python:3.14.2-slim

# Fix bug: https://stackoverflow.com/a/67404591
RUN apt-get update \
    && apt-get -y install libpq-dev gcc

# Explain: https://stackoverflow.com/a/59812588
ENV PYTHONUNBUFFERED=1

WORKDIR /project
COPY requirements.txt /project/
RUN pip install -r requirements.txt
COPY . /project/

# Expose ports without publishing them to the host machine 
# they’ll only be accessible to linked services
# Detail: https://stackoverflow.com/questions/40801772/what-is-the-difference-between-ports-and-expose-in-docker-compose
EXPOSE 8000