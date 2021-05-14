FROM node:14-buster-slim

WORKDIR /app

RUN apt-get update
RUN apt-get install -y git

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 80

COPY start.sh /
RUN chmod +x /start.sh

ENTRYPOINT ["/start.sh"]
CMD ["node", "index.js"]