FROM node:14-buster-slim

WORKDIR /app

RUN apt-get update
RUN apt-get install -y git

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 80

CMD ["node", "index.js"]