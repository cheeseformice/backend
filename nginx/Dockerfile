FROM nginx:mainline

# Install cron
RUN apt-get update
RUN apt-get install -y cron

COPY update-cloudflare.sh /update-cloudflare.sh
RUN chmod +x /update-cloudflare.sh

COPY update-cloudflare /etc/cron.d/update-cloudflare
RUN chmod 0644 /etc/cron.d/update-cloudflare
RUN touch /etc/nginx/conf.d/cloudflare-allow.conf

COPY nginx.conf /etc/nginx/nginx.conf
COPY forward.conf /etc/nginx/templates/forward.conf.template

COPY init.sh /docker-entrypoint.d/init.sh
RUN chmod +x /docker-entrypoint.d/init.sh
