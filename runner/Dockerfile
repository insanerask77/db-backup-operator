# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    gnupg \
    postgresql-client \
    supervisor \
    zstd \
    && rm -rf /var/lib/apt/lists/*

# Install MongoDB command line tools
RUN apt-get update && apt-get install -y wget gnupg ca-certificates && \
    wget -qO - https://www.mongodb.org/static/pgp/server-7.0.asc | gpg --dearmor -o /usr/share/keyrings/mongodb-server-7.0.gpg && \
    echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] http://repo.mongodb.org/apt/debian bullseye/mongodb-org/7.0 main" | tee /etc/apt/sources.list.d/mongodb-org-7.0.list && \
    apt-get update && \
    apt-get install -y mongodb-org-tools && \
    rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt ./

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container
COPY . .

# Create the log file to be able to run tail
RUN touch /var/log/cron.log

# Run the command on container startup
CMD ["/usr/bin/supervisord", "-c", "/usr/src/app/supervisord.conf"]
