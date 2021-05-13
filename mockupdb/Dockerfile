FROM mariadb:10.1.48

ENV MYSQL_DATABASE=${A801_DB} \
	MYSQL_ROOT_PASSWORD=goaway \
	MYSQL_USER=${A801_USER} \
	MYSQL_PASSWORD=${A801_PASS}

ADD *.sql /docker-entrypoint-initdb.d/

HEALTHCHECK --timeout=20s --retries=10 \
	CMD mysqladmin ping -h localhost -u ${MYSQL_USER} -p${mysql_PASS}

EXPOSE 3306