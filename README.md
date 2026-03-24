# RadioRumble

**Live amateur radio contest scoreboard for Collegiate Amateur Radio Clubs.**

Built for K-State and the collegiate ham radio community. Operators run WSJT-X (or any ADIF-capable logger), and RadioRumble picks up every QSO over UDP in real time — no manual logging required.

## Features

- **Live Scoreboard** — per-operator and per-club rankings update in real time via WebSocket
- **WSJT-X Integration** — receives decoded QSOs over UDP (port 2237) with zero operator effort
- **Multi-Club Support** — multiple clubs compete head-to-head in a single contest
- **QSO Map (2D + 3D Globe)** — toggle between Leaflet 2D map and interactive 3D globe (react-globe.gl), with great circle paths showing every QSO connection between stations and contacts
- **Contest Stats** — band/mode breakdowns, QSO rate charts, multiplier tracking
- **Contest Management** — create/start/stop contests, configure scoring rules, manage clubs and operators
- **Mobile Friendly** — responsive bottom tab bar, compact scoreboard, works on phones for spectators and operators

## Quick Start (Docker)

```bash
git clone https://github.com/Atvriders/RadioRumble.git
cd RadioRumble
docker compose up -d
```

Open `http://localhost:7373` in your browser.

Pre-built multi-arch images (amd64, arm64, armv7) are pulled from GitHub Container Registry automatically.

### Docker Commands

```bash
# Seed with sample contest data (optional — run inside the container)
docker exec radiorumble node scripts/seed.js

# View logs
docker logs -f radiorumble

# Update to latest version
docker compose pull && docker compose up -d

# Stop
docker compose down
```

### docker-compose.yml

```yaml
services:
  radiorumble:
    image: ghcr.io/atvriders/radiorumble:latest
    ports:
      - "7373:7373"        # Web UI + API
      - "2237:2237/udp"    # WSJT-X UDP ingest
    volumes:
      - ./data:/app/data   # SQLite database persistence
    environment:
      - NODE_ENV=production
    restart: unless-stopped
```

## Quick Start (without Docker)

```bash
git clone https://github.com/Atvriders/RadioRumble.git
cd RadioRumble
npm install
npm run seed      # populate database with sample contest data
npm run dev       # starts both client (Vite) and server concurrently
```

The dev server runs at `http://localhost:5173` (Vite proxy) with the API on port 7373.

## WSJT-X Setup

1. Open WSJT-X and go to **File > Settings > Reporting**
2. Check **Enable logged QSO ADIF broadcast**
3. Set **UDP Server** to the IP address of the machine running RadioRumble
4. Set **UDP Server port number** to `2237`
5. Click **OK**

Every logged QSO will now appear on the RadioRumble scoreboard within seconds.

> **Tip:** If RadioRumble is running on the same machine as WSJT-X, use `127.0.0.1` as the UDP server address.

## API Endpoints

| Method   | Endpoint                                  | Description                        |
|----------|-------------------------------------------|------------------------------------|
| `GET`    | `/api/contests`                           | List all contests                  |
| `POST`   | `/api/contests`                           | Create a contest                   |
| `GET`    | `/api/contests/:id`                       | Get contest details                |
| `PATCH`  | `/api/contests/:id`                       | Update contest                     |
| `DELETE` | `/api/contests/:id`                       | Delete contest                     |
| `GET`    | `/api/contests/:id/clubs`                 | List clubs in a contest            |
| `POST`   | `/api/contests/:id/clubs`                 | Add a club to a contest            |
| `PATCH`  | `/api/clubs/:id`                          | Update a club                      |
| `DELETE` | `/api/clubs/:id`                          | Delete a club                      |
| `POST`   | `/api/clubs/:clubId/operators`            | Add operator to club               |
| `DELETE` | `/api/operators/:id`                      | Remove operator                    |
| `GET`    | `/api/contests/:id/qsos`                  | List QSOs (filterable by band/mode/station) |
| `GET`    | `/api/contests/:id/qsos/recent`           | Last 50 QSOs                       |
| `POST`   | `/api/contests/:id/qsos`                  | Manually add a QSO                 |
| `GET`    | `/api/contests/:id/scoreboard`            | Aggregated scoreboard              |
| `GET`    | `/api/contests/:id/stats`                 | Full stats overview                |
| `GET`    | `/api/contests/:id/stats/rate`            | QSO rate per hour                  |
| `GET`    | `/api/contests/:id/stats/bands`           | Band distribution                  |
| `GET`    | `/api/contests/:id/stats/modes`           | Mode distribution                  |
| `GET`    | `/api/contests/:id/map-data`              | QSOs with grid coordinates for map |
| `WS`     | `ws://host:7373`                          | Real-time QSO and scoreboard push  |

## Tech Stack

| Layer      | Technology                          |
|------------|-------------------------------------|
| Frontend   | React 18, Zustand, React Router, Leaflet, react-globe.gl |
| Backend    | Node.js, Express, WebSocket (ws)    |
| Database   | SQLite via better-sqlite3 (WAL mode)|
| UDP Ingest | Node dgram socket (ADIF parsing)    |
| Build      | Vite, TypeScript                    |
| Deploy     | Docker / Docker Compose             |

## Architecture

```
 WSJT-X / Logger
       |
       | UDP :2237 (ADIF)
       v
 +-----------------+       +-------------+
 |  Node.js server |<----->|   SQLite    |
 |  Express + WS   |       | (WAL mode)  |
 +-----------------+       +-------------+
       |
       | HTTP :7373 + WebSocket
       v
 +-----------------+
 |   React SPA     |
 |  (Vite build)   |
 +-----------------+
```

- **UDP Ingest** -- WSJT-X sends ADIF records to port 2237. The server parses them, inserts into SQLite, and broadcasts to all connected WebSocket clients.
- **REST API** -- full CRUD for contests, clubs, operators, and QSOs.
- **WebSocket** -- pushes new QSOs and scoreboard updates to the browser in real time.
- **React Frontend** -- Vite-built SPA served by Express in production. Live scoreboard, QSO log, interactive map, and stats dashboards.

---

Built with [Claude Code](https://claude.com/claude-code)
