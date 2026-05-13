# Mafia Platform Monorepo

This repository contains the full stack for the Telegram Mafia platform.

## Structure

- `apps/web-admin`: Next.js-based administrative dashboard.
- `apps/bot`: Python-based Telegram bot service (aiogram 3).
- `infra`: Infrastructure configurations including Docker Compose, PostgreSQL, and Redis.
- `docs`: Architecture and design documentation.

## Running the Web Admin

The Web Admin is the primary interface for this AI Studio environment. It is configured as the default workspace and runs on port 3000.

To start the development server:
```bash
npm run dev
```

## Running the Bot

The bot is a Python service. In a local environment, you would use:
```bash
cd apps/bot
pip install .
python -m app.main
```

## Infrastructure

Use Docker Compose in the `infra` directory to start supporting services:
```bash
cd infra
docker-compose up -d
```
