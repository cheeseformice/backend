# Using official pypy runtime base image
FROM pypy:3.7-slim

# Set the application directory
WORKDIR /src

# Install our requirements.txt
COPY requirements.txt /src/requirements.txt
RUN pypy3 -m pip install --no-cache-dir -r requirements.txt

# Unpack assets
COPY packed-assets /packed-assets
RUN pypy3 -u /packed-assets/unpack.py

# Copy our code from the current folder inside the container
COPY src/* /src/

# Define our command to be run when launching the container
CMD ["pypy3", "-u", "service.py"]
