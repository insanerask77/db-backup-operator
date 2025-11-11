# Use a lightweight Alpine Linux base image
FROM alpine:3.18

# Install necessary packages
RUN apk update && apk add --no-cache \
    bash \
    postgresql-client \
    mongodb-tools \
    yq \
    dcron \
    coreutils \
    zip

# Create a directory for the application
WORKDIR /app

# Copy the scripts into the container
COPY scripts/ /app/scripts/
RUN chmod +x /app/scripts/*.sh

# Set up cron
RUN echo "root:x:0:0:root:/root:/bin/bash" > /etc/passwd
RUN touch /var/log/cron.log

# Create a directory for backups and configuration
RUN mkdir -p /backups /config

# Expose volumes for configuration and backups
VOLUME ["/config", "/backups"]

# Set the entrypoint
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
