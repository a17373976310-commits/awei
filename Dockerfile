# Stage 1: Build Frontend
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
# Build the frontend. Vite will output to 'dist' by default.
# We need to ensure vite builds the 'frontend' directory.
# Since package.json is in root but index.html is in frontend/, 
# we might need to adjust the build command or vite config.
# Assuming standard vite setup where root has index.html:
# But here root index.html is a redirect.
# Let's try to build with root as root, but pointing to frontend/index.html?
# Actually, let's just copy the frontend source to root for the build? No, that's messy.
# Let's assume the user's dev setup works.
# If I run 'npm run build', it runs 'vite build'.
# If vite config is default, it looks for index.html in root.
# It will build the redirect file. That's bad.
# We need to tell vite to build 'frontend/index.html'.
# We can do this by passing the entry point or changing root.
RUN npx vite build frontend --outDir ../dist --emptyOutDir

# Stage 2: Run Backend
FROM python:3.9-slim
WORKDIR /app

# Install system dependencies if needed
# RUN apt-get update && apt-get install -y ...

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Backend Code
COPY backend ./backend

# Copy Built Frontend Assets from Stage 1
COPY --from=builder /app/dist ./dist

# Expose port
EXPOSE 8000

# Start Command
CMD ["python", "-m", "backend.main"]
