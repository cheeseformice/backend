FROM redis:latest

RUN apt-get update && \
	apt-get install -y build-essential libmariadbclient-dev && \
	apt-get clean

COPY ranking.c /cfm/ranking.c
COPY redismodule.h /cfm/redismodule.h

# Build module
RUN gcc -Wall -fPIC -std=gnu99 -c -o /cfm/ranking.o /cfm/ranking.c
RUN ld -o /cfm/ranking.so /cfm/ranking.o -shared -Bsymbolic -lc -lmariadbclient