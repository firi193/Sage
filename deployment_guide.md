# Sage API Key Manager - Cloud Deployment Guide

## 🌐 Deployment Architecture

```
Frontend (Static Site)     Backend (Web Service)
┌─────────────────────┐    ┌──────────────────────┐
│   Render Static     │    │   Render Web Service │
│   sage-ui.onrender  │────│   sage-api.onrender  │
│   .com              │    │   .com               │
└─────────────────────┘    └──────────────────────┘
```

## 📋 Prerequisites

1. GitHub repository with your code
2. Render account (free tier available)
3. Environment variables for production

## 🎯 Option 1: Two Separate Services (Recommended)

### Step 1: Deploy Frontend (Static Site)

1. **Create `sage_ui/package.json`** (for build detection):
```json
{
  "name": "sage-ui",
  "version": "1.0.0",
  "scripts": {
    "build": "echo 'No build needed for static site'"
  }
}
```

2. **Update API base URL** in `sage_ui/js/api.js`:
```javascript
// Change this line:
const API_BASE = window.location.port === '8080' ? 'http://localhost:8001/api/v1' : '/api/v1';

// To this:
const API_BASE = window.location.hostname === 'localhost' 
  ? 'http://localhost:8001/api/v1' 
  : 'https://your-backend-service.onrender.com/api/v1';
```

3. **Deploy on Render**:
   - Connect your GitHub repo
   - Choose "Static Site"
   - Set publish directory: `sage_ui`
   - Deploy

### Step 2: Deploy Backend (Web Service)

1. **Create `requirements.txt`**:
```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6
pydantic==2.5.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-dotenv==1.0.0
```

2. **Create FastAPI server** (`main.py`):
```python
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI(title="Sage API Key Manager", version="1.0.0")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Your existing Sage MCP integration here
# from sage.sage_mcp import SageMCP

@app.get("/api/v1/health")
async def health_check():
    return {"status": "healthy", "service": "sage-api"}

@app.get("/api/v1/keys")
async def list_keys():
    # Integrate with your existing Sage MCP service
    return {"keys": []}

@app.post("/api/v1/keys")
async def add_key(key_data: dict):
    # Integrate with your existing Sage MCP service
    return {"message": "Key added", "key_id": "new-key-id"}

# Add other endpoints...

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
```

3. **Deploy on Render**:
   - Connect your GitHub repo
   - Choose "Web Service"
   - Build command: `pip install -r requirements.txt`
   - Start command: `python main.py`
   - Add environment variables

## 🎯 Option 2: Single Service (Simpler)

1. **Create combined FastAPI app**:
```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI()

# Serve static files
app.mount("/static", StaticFiles(directory="sage_ui"), name="static")

# API routes
@app.get("/api/v1/keys")
async def list_keys():
    return {"keys": []}

# Serve frontend
@app.get("/")
async def serve_frontend():
    return FileResponse("sage_ui/index.html")
```

2. **Update API base URL**:
```javascript
const API_BASE = '/api/v1';  // Same domain
```

## 🔧 Configuration Files

### For Render Static Site (`sage_ui/_redirects`):
```
/*    /index.html   200
```

### For Render Web Service (`render.yaml`):
```yaml
services:
  - type: web
    name: sage-api
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python main.py
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
```

## 🔐 Environment Variables

Set these in Render dashboard:

**Backend Service:**
- `DATABASE_URL` (PostgreSQL connection string from Render)
- `SECRET_KEY` (for JWT tokens)
- `CORS_ORIGINS` (your frontend URL)
- `ENVIRONMENT=production`

**Database Setup:**
- Render provides PostgreSQL database with connection string
- Format: `postgresql://user:password@host:port/database`
- Your app automatically detects production environment and uses PostgreSQL

## 📝 Deployment Steps

### Quick Deploy (Option 1):

1. **Push to GitHub**:
```bash
git add .
git commit -m "Prepare for deployment"
git push origin main
```

2. **Deploy Frontend**:
   - Go to Render dashboard
   - "New Static Site"
   - Connect repo, set publish dir to `sage_ui`

3. **Deploy Backend**:
   - "New Web Service"
   - Connect repo, set build/start commands
   - Add environment variables

4. **Update Frontend API URL**:
   - Update `API_BASE` in `api.js` with your backend URL
   - Redeploy frontend

## 🧪 Testing Deployment

1. **Frontend**: Visit your static site URL
2. **Backend**: Visit `your-backend.onrender.com/docs` for API docs
3. **Integration**: Test API calls from frontend

## 💡 Pro Tips

- **Free Tier Limits**: Render free tier sleeps after 15 min inactivity
- **Custom Domains**: Available on paid plans
- **SSL**: Automatic HTTPS on Render
- **Logs**: Available in Render dashboard
- **Database**: PostgreSQL automatically configured for production
- **Migration**: Use `python migrate_to_postgres.py` to move SQLite data to PostgreSQL

## 🗄️ Database Migration

Your app supports both SQLite (development) and PostgreSQL (production):

1. **Development**: Uses SQLite files automatically
2. **Production**: Uses PostgreSQL when `ENVIRONMENT=production` and `DATABASE_URL` is set
3. **Migration**: Run migration script to move data from SQLite to PostgreSQL

```bash
# Set production environment
export ENVIRONMENT=production
export DATABASE_URL=postgresql://user:pass@host:port/db

# Run migration
python migrate_to_postgres.py
```

## 🔄 CI/CD

Render auto-deploys on git push to main branch. For more control:

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Deploy to Render
        run: echo "Render auto-deploys on push"
```

Would you like me to help you set up any of these deployment options?