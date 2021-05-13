FROM mariadb:10.1.48

ENV MYSQL_DATABASE=api_data \
	MYSQL_ROOT_PASSWORD=goaway \
	MYSQL_USER=test \
	MYSQL_PASSWORD=test

ADD *.sql /docker-entrypoint-initdb.d/

HEALTHCHECK --timeout=20s --retries=10 \
	CMD mysqladmin ping -h localhost -u ${MYSQL_USER} -p${MYSQL_PASSWORD}

EXPOSE 3306