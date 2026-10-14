# Frontend image. The API address is baked in at build time because the BROWSER (on your machine) calls it.
FROM node:22-slim
ARG NEXT_PUBLIC_API_URL=http://localhost:8020
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build
USER node
EXPOSE 3000
CMD ["npm", "start", "--", "-p", "3000"]
