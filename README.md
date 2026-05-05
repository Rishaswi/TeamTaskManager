# ProjectFlow — Task & Project Management App

A full-stack project management app with role-based access control.

## Stack
- **Backend**: FastAPI + SQLAlchemy + SQLite (upgrades to PostgreSQL on Railway)
- **Frontend**: Vanilla HTML/CSS/JS (single file, zero dependencies)
- **Auth**: JWT (python-jose + bcrypt)
- **Deploy**: Railway

---

## Local Development

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
API docs: http://localhost:8000/docs

### Frontend
Just open `frontend/index.html` in a browser.
Or serve it:
```bash
cd frontend
python -m http.server 3000
```

---

## Railway Deployment (Step-by-Step)

### 1. Deploy the Backend

1. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub repo
2. Select your repo, set **root directory** to `backend/`
3. Railway auto-detects Python via Nixpacks
4. Add Environment Variables:
   - `SECRET_KEY` = `your-random-secret-here-use-openssl-rand-hex-32`
   - `PORT` = (Railway sets this automatically)
5. (Optional) Add a **PostgreSQL** plugin — Railway auto-injects `DATABASE_URL`
6. Deploy → Copy your Railway backend URL (e.g., `https://projectflow-backend.up.railway.app`)

### 2. Update Frontend URL

In `frontend/index.html`, find this line:
```js
: 'https://YOUR-RAILWAY-BACKEND-URL.up.railway.app';
```
Replace with your actual Railway backend URL.

### 3. Deploy the Frontend

**Option A — Railway (Static)**
1. New Service → GitHub → root directory = `frontend/`
2. Add start command: `npx serve . -p $PORT`
3. Deploy

**Option B — Netlify (Easiest)**
1. Drag & drop the `frontend/` folder to netlify.com/drop
2. Get instant public URL

**Option C — Vercel**
```bash
cd frontend
npx vercel --prod
```

---

## API Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/signup` | ❌ | Register user |
| POST | `/api/auth/login` | ❌ | Login |
| GET | `/api/auth/me` | ✅ | Current user |
| GET | `/api/users` | ✅ | List all users |
| POST | `/api/projects` | ✅ | Create project |
| GET | `/api/projects` | ✅ | List projects |
| GET | `/api/projects/{id}` | ✅ | Get project |
| PUT | `/api/projects/{id}` | Admin | Update project |
| DELETE | `/api/projects/{id}` | Admin | Delete project |
| POST | `/api/projects/{id}/members` | Admin | Add member |
| DELETE | `/api/projects/{id}/members/{uid}` | Admin | Remove member |
| POST | `/api/projects/{id}/tasks` | ✅ | Create task |
| GET | `/api/projects/{id}/tasks` | ✅ | List tasks |
| PUT | `/api/projects/{id}/tasks/{tid}` | ✅ | Update task |
| DELETE | `/api/projects/{id}/tasks/{tid}` | ✅ | Delete task |
| GET | `/api/dashboard` | ✅ | Dashboard stats |

---

## Role-Based Access Control

| Action | Admin (Global) | Project Admin | Member |
|--------|---------------|---------------|--------|
| Create project | ✅ | ✅ | ✅ |
| Edit/Delete project | ✅ | ✅ | ❌ |
| See all projects | ✅ | ❌ | ❌ |
| Add/remove members | ✅ | ✅ | ❌ |
| Create/edit tasks | ✅ | ✅ | ✅ |
| View all users | ✅ | ✅ | ✅ |

---

## Features
- ✅ JWT Authentication (Signup/Login)
- ✅ Role-based access (Global Admin + Project-level Admin/Member)
- ✅ Project CRUD with ownership
- ✅ Task creation, assignment, status tracking
- ✅ Priority levels (Low/Medium/High)
- ✅ Due dates with overdue detection
- ✅ Dashboard with stats (total, in-progress, done, overdue)
- ✅ My Tasks view
- ✅ Progress bar per project
- ✅ One-click task status toggle
- ✅ SQLite for local dev, PostgreSQL for production (Railway)
