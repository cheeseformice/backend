# https://github.com/baleyko/docker-luvit/blob/master/Dockerfile
FROM ubuntu:xenial

# Install luvit
RUN apt-get update -yqq \
	&& apt-get install -yqq --no-install-recommends \
		ca-certificates \
		build-essential \
		curl \
	&& rm -rf /var/lib/apt/lists/*

RUN export LIT_VERSION=3.8.1 \
	&& export LUVI_VERSION=2.10.1 \
	&& curl -fsSL https://github.com/luvit/lit/raw/master/get-lit.sh | sh
RUN mv luvit /usr/bin && mv luvi /usr/bin && mv lit /usr/bin

WORKDIR /src

# Install our requirements
COPY package.lua ./package.lua
RUN lit install || true

# Copy our code from the current folder to our workdir inside the container
COPY src/* /src/

# Define our command to be run when launching the container
CMD ["luvit", "/src/bot.lua"]