# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CWatcher is a Linux system monitoring platform designed to provide real-time server monitoring through a web interface. The project is currently in the planning and prototyping phase.

## Project Structure

- `Docs/` - Project documentation
  - `prd.md` - Complete Product Requirements Document (in Chinese)
  - `TODO.md` - Detailed development plan with TDD approach
- `UI/` - User interface prototypes
  - `prototype-1/` - HTML/CSS/JS prototype with dashboard interface
  - `prototype-2/` - Alternative UI design
- `trash/` - Archive folder for deprecated files

## Architecture Overview

**Target Technology Stack** (as defined in PRD):
- **Backend**: Python + FastAPI
  - SSH connections: paramiko library
  - Real-time communication: WebSocket
  - Database: InfluxDB/TimescaleDB (time series) + PostgreSQL (relational)
  - Task scheduling: Celery
- **Frontend**: React 18 + TypeScript
  - UI Framework: Tailwind CSS (already used in prototypes)
  - Charts: Chart.js (implemented in prototype)
  - State Management: Redux Toolkit
  - Real-time updates: Socket.io-client

## Core Functionality

The system monitors four key metrics via SSH connections to Linux servers:
1. **CPU Usage** - Real-time utilization, core count, frequency
2. **Memory Usage** - RAM utilization, swap usage, detailed breakdown
3. **Disk Usage** - Space utilization, I/O metrics, filesystem info
4. **Network Traffic** - Upload/download speeds, interface status

## Development Phases

1. **Phase 1 (P0)**: MVP core functionality
   - SSH connection management
   - Basic metric collection (CPU/Memory/Disk/Network)
   - Real-time data display with basic charts
   - Basic web UI

2. **Phase 2 (P1)**: Enhanced user experience
   - Detailed system information display
   - Multi-timeframe charts
   - Responsive design optimization
   - Server status management

3. **Phase 3 (P2)**: Enterprise features
   - Alert/notification system
   - Historical data analysis
   - User management and permissions
   - Data export functionality

## Development Approach

**Test-Driven Development (TDD)**: The project follows TDD methodology with comprehensive test coverage requirements:
- Unit tests (≥80% coverage)
- Integration tests (≥70% coverage)
- End-to-end tests for critical user flows

## Current Status

- ✅ Requirements analysis and PRD completed
- ✅ UI prototypes designed (HTML/CSS/JS with Chart.js)
- ⏳ Implementation not yet started
- ⏳ No backend code exists yet
- ⏳ No production frontend code exists yet

## Key Implementation Notes

1. **SSH Security**: Use key-based authentication, encrypt stored credentials with AES
2. **Real-time Updates**: Default 30-second refresh rate (configurable 10-300s)
3. **Performance**: Support 100+ concurrent users, monitor up to 50 servers per instance
4. **UI Theme**: Dark theme with neon accents (cyan/blue), glass-morphism effects
5. **Responsive Design**: Desktop-first with mobile/tablet adaptations

## Non-Functional Requirements

- **Response Time**: Page load <3s, data updates <5s
- **Availability**: 99.5% uptime target
- **Security**: HTTPS/WSS encryption, RBAC, audit logging
- **Browser Support**: Modern browsers with WebSocket support

## Deployment

**Target Environment**:
- Containerized deployment (Docker + Docker Compose)
- Nginx reverse proxy
- HTTPS with Let's Encrypt or self-signed certificates
- Minimum requirements: 2 CPU cores, 4GB RAM, 20GB storage

## Supported Linux Distributions

- Ubuntu 18.04+
- CentOS/RHEL 7+
- Debian 9+
- SUSE Linux Enterprise 12+

## Documentation Language

Primary documentation is in Traditional Chinese (zh-TW). When creating new documentation, follow the existing language patterns unless specifically requested otherwise.