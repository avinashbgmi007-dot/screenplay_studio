# screenplay_studio/webapp_server.py

## Purpose
Flask web application server for the screenplay studio. Provides HTTP API endpoints for the web interface.

## Key Functions

### `app` (Flask instance)
The Flask application instance.

### API Endpoints
- `GET /` — Home page
- `POST /api/parse` — Parse a screenplay
- `POST /api/analyze` — Analyze a screenplay
- `POST /api/chat` — Send a chat message
- `GET /api/status` — Get project status
- `GET /api/sessions` — List chat sessions

## Dependencies
- `flask` (web framework)
- `screenplay_studio.orchestrator` (Orchestrator)
- `screenplay_studio.manifest` (ProjectManifest)
- `screenplay_cowriter.engine` (CoWriterEngine)

## Usage Example
```bash
# Start the web server
python -m screenplay_studio.webapp_server

# Access at http://localhost:5000
```

## Graph Notes
- Web app connects to `Orchestrator` and `ProjectManifest`
- Part of the `Studio Manifest & Tests` community
