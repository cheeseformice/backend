FROM mariadb:10.1.48

ENV MYSQL_DATABASE=${DB} \
	MYSQL_ROOT_PASSWORD=goaway \
	MYSQL_USER=${DB_USER} \
	MYSQL_PASSWORD=${DB_PASS}

ADD *.sql /docker-entrypoint-initdb.d

EXPOSE 3306