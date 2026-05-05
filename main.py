from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional

import models, schemas, auth
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="ProjectFlow API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════════════════
# AUTH ROUTES
# ═══════════════════════════════════════════════════════

@app.post("/api/auth/signup", response_model=schemas.Token)
def signup(data: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == data.email).first():
        raise HTTPException(400, "Email already registered")
    user = models.User(
        name=data.name,
        email=data.email,
        hashed_password=auth.hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = auth.create_access_token({"sub": str(user.id)})
    return schemas.Token(access_token=token, user=schemas.UserOut.model_validate(user))

@app.post("/api/auth/login", response_model=schemas.Token)
def login(data: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == data.email).first()
    if not user or not auth.verify_password(data.password, user.hashed_password):
        raise HTTPException(401, "Invalid credentials")
    token = auth.create_access_token({"sub": str(user.id)})
    return schemas.Token(access_token=token, user=schemas.UserOut.model_validate(user))

@app.get("/api/auth/me", response_model=schemas.UserOut)
def me(current_user=Depends(auth.get_current_user)):
    return current_user

# ═══════════════════════════════════════════════════════
# USER ROUTES (Admin only)
# ═══════════════════════════════════════════════════════

@app.get("/api/users", response_model=List[schemas.UserOut])
def list_users(db: Session = Depends(get_db), current_user=Depends(auth.get_current_user)):
    return db.query(models.User).filter(models.User.is_active == True).all()

# ═══════════════════════════════════════════════════════
# PROJECT ROUTES
# ═══════════════════════════════════════════════════════

def _build_project_out(project: models.Project) -> schemas.ProjectOut:
    data = schemas.ProjectOut.model_validate(project)
    data.task_count = len(project.tasks)
    return data

@app.post("/api/projects", response_model=schemas.ProjectOut)
def create_project(
    data: schemas.ProjectCreate,
    db: Session = Depends(get_db),
    current_user=Depends(auth.get_current_user),
):
    project = models.Project(
        name=data.name,
        description=data.description,
        owner_id=current_user.id,
    )
    db.add(project)
    db.flush()
    # Auto-add creator as admin member
    member = models.ProjectMember(
        project_id=project.id,
        user_id=current_user.id,
        role=models.UserRole.admin,
    )
    db.add(member)
    db.commit()
    db.refresh(project)
    return _build_project_out(project)

@app.get("/api/projects", response_model=List[schemas.ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    current_user=Depends(auth.get_current_user),
):
    if current_user.role == models.UserRole.admin:
        projects = db.query(models.Project).all()
    else:
        member_project_ids = [
            m.project_id for m in db.query(models.ProjectMember)
            .filter(models.ProjectMember.user_id == current_user.id).all()
        ]
        projects = db.query(models.Project).filter(
            models.Project.id.in_(member_project_ids)
        ).all()
    return [_build_project_out(p) for p in projects]

@app.get("/api/projects/{project_id}", response_model=schemas.ProjectOut)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(auth.get_current_user),
):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    _check_project_access(project_id, current_user, db)
    return _build_project_out(project)

@app.put("/api/projects/{project_id}", response_model=schemas.ProjectOut)
def update_project(
    project_id: int,
    data: schemas.ProjectUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(auth.get_current_user),
):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    _check_project_admin(project_id, current_user, db)
    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    db.commit()
    db.refresh(project)
    return _build_project_out(project)

@app.delete("/api/projects/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(auth.get_current_user),
):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    _check_project_admin(project_id, current_user, db)
    db.delete(project)
    db.commit()
    return {"message": "Project deleted"}

# ─── Project Members ────────────────────────────────────

@app.post("/api/projects/{project_id}/members")
def add_member(
    project_id: int,
    data: schemas.AddMemberRequest,
    db: Session = Depends(get_db),
    current_user=Depends(auth.get_current_user),
):
    _check_project_admin(project_id, current_user, db)
    existing = db.query(models.ProjectMember).filter(
        models.ProjectMember.project_id == project_id,
        models.ProjectMember.user_id == data.user_id
    ).first()
    if existing:
        raise HTTPException(400, "User already a member")
    user = db.query(models.User).filter(models.User.id == data.user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    member = models.ProjectMember(
        project_id=project_id,
        user_id=data.user_id,
        role=data.role,
    )
    db.add(member)
    db.commit()
    return {"message": "Member added"}

@app.delete("/api/projects/{project_id}/members/{user_id}")
def remove_member(
    project_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(auth.get_current_user),
):
    _check_project_admin(project_id, current_user, db)
    member = db.query(models.ProjectMember).filter(
        models.ProjectMember.project_id == project_id,
        models.ProjectMember.user_id == user_id
    ).first()
    if not member:
        raise HTTPException(404, "Member not found")
    db.delete(member)
    db.commit()
    return {"message": "Member removed"}

# ═══════════════════════════════════════════════════════
# TASK ROUTES
# ═══════════════════════════════════════════════════════

@app.post("/api/projects/{project_id}/tasks", response_model=schemas.TaskOut)
def create_task(
    project_id: int,
    data: schemas.TaskCreate,
    db: Session = Depends(get_db),
    current_user=Depends(auth.get_current_user),
):
    _check_project_access(project_id, current_user, db)
    task = models.Task(
        title=data.title,
        description=data.description,
        priority=data.priority,
        due_date=data.due_date,
        assignee_id=data.assignee_id,
        project_id=project_id,
        creator_id=current_user.id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

@app.get("/api/projects/{project_id}/tasks", response_model=List[schemas.TaskOut])
def list_tasks(
    project_id: int,
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(auth.get_current_user),
):
    _check_project_access(project_id, current_user, db)
    q = db.query(models.Task).filter(models.Task.project_id == project_id)
    if status:
        q = q.filter(models.Task.status == status)
    return q.order_by(models.Task.created_at.desc()).all()

@app.put("/api/projects/{project_id}/tasks/{task_id}", response_model=schemas.TaskOut)
def update_task(
    project_id: int,
    task_id: int,
    data: schemas.TaskUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(auth.get_current_user),
):
    _check_project_access(project_id, current_user, db)
    task = db.query(models.Task).filter(
        models.Task.id == task_id,
        models.Task.project_id == project_id
    ).first()
    if not task:
        raise HTTPException(404, "Task not found")
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(task, field, val)
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task

@app.delete("/api/projects/{project_id}/tasks/{task_id}")
def delete_task(
    project_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(auth.get_current_user),
):
    _check_project_access(project_id, current_user, db)
    task = db.query(models.Task).filter(
        models.Task.id == task_id,
        models.Task.project_id == project_id
    ).first()
    if not task:
        raise HTTPException(404, "Task not found")
    db.delete(task)
    db.commit()
    return {"message": "Task deleted"}

# ═══════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════

@app.get("/api/dashboard", response_model=schemas.DashboardStats)
def dashboard(
    db: Session = Depends(get_db),
    current_user=Depends(auth.get_current_user),
):
    now = datetime.utcnow()
    if current_user.role == models.UserRole.admin:
        project_ids = [p.id for p in db.query(models.Project).all()]
    else:
        project_ids = [
            m.project_id for m in db.query(models.ProjectMember)
            .filter(models.ProjectMember.user_id == current_user.id).all()
        ]

    all_tasks = db.query(models.Task).filter(
        models.Task.project_id.in_(project_ids)
    ).all() if project_ids else []

    my_tasks = [t for t in all_tasks if t.assignee_id == current_user.id]
    overdue = [
        t for t in all_tasks
        if t.due_date and t.due_date < now and t.status != models.TaskStatus.done
    ]

    return schemas.DashboardStats(
        total_projects=len(project_ids),
        total_tasks=len(all_tasks),
        todo_count=sum(1 for t in all_tasks if t.status == models.TaskStatus.todo),
        in_progress_count=sum(1 for t in all_tasks if t.status == models.TaskStatus.in_progress),
        done_count=sum(1 for t in all_tasks if t.status == models.TaskStatus.done),
        overdue_count=len(overdue),
        my_tasks=my_tasks[:10],
    )

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "ProjectFlow API"}

# ═══════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════

def _check_project_access(project_id: int, user: models.User, db: Session):
    if user.role == models.UserRole.admin:
        return
    member = db.query(models.ProjectMember).filter(
        models.ProjectMember.project_id == project_id,
        models.ProjectMember.user_id == user.id
    ).first()
    if not member:
        raise HTTPException(403, "Not a project member")

def _check_project_admin(project_id: int, user: models.User, db: Session):
    if user.role == models.UserRole.admin:
        return
    member = db.query(models.ProjectMember).filter(
        models.ProjectMember.project_id == project_id,
        models.ProjectMember.user_id == user.id
    ).first()
    if not member or member.role != models.UserRole.admin:
        raise HTTPException(403, "Project admin access required")
