FROM node:18-alpine as build

WORKDIR /app

# Kopioi package files
COPY frontend/package*.json ./

# Asenna riippuvuudet
RUN npm install

# Kopioi lähdekoodi
COPY frontend/ ./

# Rakenna tuotantobuild
RUN npm run build

# Production stage
FROM nginx:alpine

# Kopioi build
COPY --from=build /app/dist /usr/share/nginx/html

# Kopioi nginx config
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

