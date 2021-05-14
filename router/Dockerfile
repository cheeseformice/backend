FROM node:14-buster-slim

WORKDIR /

RUN apt-get update
RUN apt-get install -y git

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 80

# Download wait-for-it
ADD https://raw.githubusercontent.com/vishnubob/wait-for-it/master/wait-for-it.sh /wait-for-it.sh
RUN chmod +x /wait-for-it.sh

RUN chmod +x /start.sh

ENTRYPOINT ["/start.sh"]
CMD ["node", "index.js"]