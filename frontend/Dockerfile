# Stage 1: Build the Svelte application
FROM node:20-alpine AS build-stage
WORKDIR /app

# Copy package.json and package-lock.json to install dependencies
COPY package*.json ./
RUN npm install

# Copy the rest of the frontend code and build the application
COPY . .
RUN npm run build

# Stage 2: Serve the built application with Nginx
FROM nginx:stable-alpine
# Копіюємо налаштування проксі
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Copy the built Svelte application from the build-stage
COPY --from=build-stage /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]