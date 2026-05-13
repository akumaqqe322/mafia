# Telegram Mafia Platform Architecture

## Overview
This platform is a Telegram-based Mafia game with a web-based administration panel.

## Architecture
- **apps/bot**: Python 3.12 service using aiogram 3. Handles all Telegram interactions.
- **apps/web-admin**: Next.js service for administration, statistics, and dashboard.
- **infra**: Infrastructure configuration (Docker, PostgreSQL, Redis).

## Tech Stack
### Bot (apps/bot)
- **Framework**: aiogram 3
- **Database**: PostgreSQL with SQLAlchemy 2 (async)
- **Cache/State**: Redis
- **Migrations**: Alembic

### Web Admin (apps/web-admin)
- **Framework**: Next.js 15+
- **UI**: React, Tailwind CSS, Lucide icons

## Key Design Rules
- Game logic is centralized in the Python bot service.
- The Web Admin is a consumer of historical data and system configuration.
- Redis is the primary source of truth for active game sessions.
- PostgreSQL stores persistent data (users, chats, matches).
