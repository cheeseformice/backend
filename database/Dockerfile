FROM mariadb:10.1.48

RUN apt-get update && \
	apt-get install -y sshpass && \
	apt-get clean

ENV MYSQL_DATABASE=api_data \
	MYSQL_ROOT_PASSWORD=goaway \
	MYSQL_USER=test \
	MYSQL_PASSWORD=test

ADD *.sql /docker-entrypoint-initdb.d/
ADD /backup.sh /
ADD /run-til-midnight.sh /
RUN chmod +x /backup.sh
RUN chmod +x /run-til-midnight.sh

HEALTHCHECK --timeout=20s --retries=10 \
	CMD mysqladmin ping -h localhost -u ${MYSQL_USER} -p${MYSQL_PASSWORD}

EXPOSE 3306
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["/run-til-midnight.sh", "mysqld"]