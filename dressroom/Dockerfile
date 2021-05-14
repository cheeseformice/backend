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

# Download wait-for-it
ADD https://raw.githubusercontent.com/vishnubob/wait-for-it/master/wait-for-it.sh /wait-for-it.sh
RUN chmod +x /wait-for-it.sh

# Copy start.sh
COPY start.sh /
RUN chmod +x /start.sh

# Define our command to be run when launching the container
ENTRYPOINT ["/start.sh"]
CMD ["pypy3", "-u", "service.py"]
