# Using official python runtime base image
FROM pypy:3.7-slim

# Install cron
RUN apt-get update && \
	apt-get install -y cron && \
	apt-get clean

# Create our cron job
COPY periodic-run /etc/cron.d/periodic-run
RUN chmod 0644 /etc/cron.d/periodic-run

WORKDIR /src

# Install our requirements.txt
COPY requirements.txt /src/requirements.txt
RUN pypy3 -m pip install --no-cache-dir -r requirements.txt

# Copy our code from the current folder inside the container
COPY src/* /src

# Define our command to be run when launching the container
CMD ["cron", "-f"]