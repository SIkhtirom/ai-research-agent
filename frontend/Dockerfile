# Local development image for the Next.js frontend.
# The backend API origin is compiled in via NEXT_PUBLIC_API_URL (build arg).
# NEXT_PUBLIC_API_BASE_URL is kept for backward compatibility.
FROM node:20-alpine

ENV NEXT_TELEMETRY_DISABLED=1

WORKDIR /app

COPY package.json package-lock.json* ./
# npm ci is preferred; fall back to npm install if there is no lockfile.
RUN npm ci 2>/dev/null || npm install

COPY . .

ARG NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
ARG NEXT_PUBLIC_API_BASE_URL=
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL

RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "start"]
