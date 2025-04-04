FROM node:18

WORKDIR /app

COPY my-app/package.json my-app/package-lock.json ./
RUN npm install

COPY my-app . 

RUN npm run build  

EXPOSE 3000  

CMD ["npm", "run", "start"]  
