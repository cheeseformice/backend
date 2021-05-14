# Using official pypy runtime base image
FROM pypy:3.7-slim

# Set the application directory
WORKDIR /src

# Install build-essential for argon2-cffi
RUN apt-get update && \
	apt-get install -y build-essential && \
	apt-get clean

# Install our requirements.txt
COPY requirements.txt /src/requirements.txt
RUN pypy3 -m pip install --no-cache-dir -r requirements.txt

# Copy our code from the current folder inside the container
COPY src/* /src/

# Define our command to be run when launching the container
CMD ["pypy3", "-u", "service.py"]
