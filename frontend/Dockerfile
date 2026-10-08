# Vite 8 requires Node 20.19+/22.12+; pin 22 so the tag can't drift below that.
FROM node:22

WORKDIR /app

COPY package*.json ./

RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
