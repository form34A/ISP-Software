# ---- Stage 1: build dashboard ----
FROM node:20-slim AS dashboard
WORKDIR /app
ARG VITE_API_URL=https://surfzone.stormclouds.co.ke
ENV VITE_API_URL=${VITE_API_URL}
COPY Frontend/Dashboard/package.json Frontend/Dashboard/package-lock.json ./
RUN npm install
COPY Frontend/Dashboard/ ./
RUN NODE_OPTIONS=--max-old-space-size=4096 npm run build -- --outDir dist --emptyOutDir

# ---- Stage 2: build landing ----
FROM node:20-slim AS landing
WORKDIR /app
ARG VITE_API_BASE_URL=https://surfzone.stormclouds.co.ke
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
COPY Frontend/Landingpage/package.json Frontend/Landingpage/package-lock.json ./
RUN npm install
COPY Frontend/Landingpage/ ./
RUN NODE_OPTIONS=--max-old-space-size=4096 npm run build -- --outDir dist --emptyOutDir

# ---- Stage 3: nginx serving both + proxy to backend ----
FROM nginx:alpine
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx/nginx.conf /etc/nginx/nginx.conf
# landing at web root, dashboard under /dashboard/
COPY --from=landing   /app/dist            /usr/share/nginx/html/
COPY --from=dashboard /app/dist            /usr/share/nginx/html/dashboard/
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
