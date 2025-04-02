FROM python:3.11.3-slim-bullseye
# Fix bug: https://stackoverflow.com/a/76560124
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y gcc default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*
# Explain: https://stackoverflow.com/a/59812588
ENV PYTHONUNBUFFERED=1

WORKDIR /project
COPY requirements.txt /project/
RUN pip install -r requirements.txt
COPY . /backend/

# Expose ports without publishing them to the host machine 
# they’ll only be accessible to linked services
# Detail: https://stackoverflow.com/questions/40801772/what-is-the-difference-between-ports-and-expose-in-docker-compose
EXPOSE ${BACKEND_DOCKER_PORT}