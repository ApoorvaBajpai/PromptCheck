import hashlib

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_user_project
from app.database import get_db
from app.models.project import Project
from app.models.prompt import Prompt, PromptVersion
from app.models.user import User
from app.schemas.prompt import (
    PromptCreate,
    PromptOut,
    PromptUpdate,
    PromptVersionCreate,
    PromptVersionOut,
)

router = APIRouter(prefix="/api/projects/{project_id}/prompts", tags=["Prompts"])


def _calculate_content_hash(content: str) -> str:
    """Calculate SHA-256 hash of normalized prompt content (Invariant 2)."""
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


def _to_prompt_out(prompt: Prompt, db: Session) -> PromptOut:
    versions = (
        db.query(PromptVersion)
        .filter(PromptVersion.prompt_id == prompt.id)
        .order_by(PromptVersion.version_number.desc())
        .all()
    )
    latest = PromptVersionOut.model_validate(versions[0]) if versions else None
    return PromptOut(
        id=prompt.id,
        project_id=prompt.project_id,
        name=prompt.name,
        description=prompt.description,
        versions_count=len(versions),
        latest_version=latest,
        created_at=prompt.created_at,
        updated_at=prompt.updated_at,
    )


@router.post("", response_model=PromptOut, status_code=status.HTTP_201_CREATED)
def create_prompt(
    payload: PromptCreate,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db),
):
    """Create a prompt container under the project."""
    prompt = Prompt(
        project_id=project.id,
        name=payload.name,
        description=payload.description,
    )
    db.add(prompt)
    db.commit()
    db.refresh(prompt)

    # If initial content provided, create version 1
    init_content = payload.initial_content or payload.initial_version_content
    if init_content:
        content_hash = _calculate_content_hash(init_content)
        v1 = PromptVersion(
            prompt_id=prompt.id,
            version_number=1,
            content=init_content,
            content_hash=content_hash,
            commit_message=payload.commit_message or "Initial version",
        )
        db.add(v1)
        db.commit()

    return _to_prompt_out(prompt, db)


@router.get("", response_model=list[PromptOut])
def list_prompts(
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db),
):
    """List all prompts under the project."""
    prompts = (
        db.query(Prompt)
        .filter(Prompt.project_id == project.id)
        .order_by(Prompt.created_at.desc())
        .all()
    )
    return [_to_prompt_out(p, db) for p in prompts]


@router.get("/{prompt_id}", response_model=PromptOut)
def get_prompt(
    prompt_id: int,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db),
):
    """Get single prompt by ID."""
    prompt = (
        db.query(Prompt).filter(Prompt.id == prompt_id, Prompt.project_id == project.id).first()
    )
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found",
        )
    return _to_prompt_out(prompt, db)


@router.put("/{prompt_id}", response_model=PromptOut)
def update_prompt(
    prompt_id: int,
    payload: PromptUpdate,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db),
):
    """Update prompt container metadata (name/description). Note: versions are immutable."""
    prompt = (
        db.query(Prompt).filter(Prompt.id == prompt_id, Prompt.project_id == project.id).first()
    )
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found",
        )

    if payload.name is not None:
        prompt.name = payload.name
    if payload.description is not None:
        prompt.description = payload.description

    db.commit()
    db.refresh(prompt)
    return _to_prompt_out(prompt, db)


@router.delete("/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_prompt(
    prompt_id: int,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db),
):
    """Delete a prompt container and its versions."""
    prompt = (
        db.query(Prompt).filter(Prompt.id == prompt_id, Prompt.project_id == project.id).first()
    )
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found",
        )

    db.delete(prompt)
    db.commit()
    return None


# --- Prompt Versions Management (Invariants 1 & 2) ---


@router.post(
    "/{prompt_id}/versions",
    response_model=PromptVersionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_prompt_version(
    prompt_id: int,
    payload: PromptVersionCreate,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db),
):
    """
    Create a new immutable prompt version.
    Invariant 2: Identical prompt content must be deduplicated using SHA-256.
    """
    prompt = (
        db.query(Prompt).filter(Prompt.id == prompt_id, Prompt.project_id == project.id).first()
    )
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found",
        )

    content_hash = _calculate_content_hash(payload.content)

    # Deduplication check
    existing_version = (
        db.query(PromptVersion)
        .filter(
            PromptVersion.prompt_id == prompt.id,
            PromptVersion.content_hash == content_hash,
        )
        .first()
    )
    if existing_version:
        # Return existing version if identical content hash exists
        return PromptVersionOut.model_validate(existing_version)

    # Determine next version number
    highest_version = (
        db.query(PromptVersion.version_number)
        .filter(PromptVersion.prompt_id == prompt.id)
        .order_by(PromptVersion.version_number.desc())
        .first()
    )
    next_version = (highest_version[0] + 1) if highest_version else 1

    version = PromptVersion(
        prompt_id=prompt.id,
        version_number=next_version,
        content=payload.content,
        content_hash=content_hash,
        commit_message=payload.commit_message,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return PromptVersionOut.model_validate(version)


@router.get("/{prompt_id}/versions", response_model=list[PromptVersionOut])
def list_prompt_versions(
    prompt_id: int,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db),
):
    """List all immutable versions of a prompt."""
    prompt = (
        db.query(Prompt).filter(Prompt.id == prompt_id, Prompt.project_id == project.id).first()
    )
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found",
        )

    versions = (
        db.query(PromptVersion)
        .filter(PromptVersion.prompt_id == prompt.id)
        .order_by(PromptVersion.version_number.desc())
        .all()
    )
    return [PromptVersionOut.model_validate(v) for v in versions]


@router.get("/{prompt_id}/versions/{version_id}", response_model=PromptVersionOut)
def get_prompt_version(
    prompt_id: int,
    version_id: int,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db),
):
    """Get specific immutable version of a prompt."""
    prompt = (
        db.query(Prompt).filter(Prompt.id == prompt_id, Prompt.project_id == project.id).first()
    )
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found",
        )

    version = (
        db.query(PromptVersion)
        .filter(
            PromptVersion.id == version_id,
            PromptVersion.prompt_id == prompt.id,
        )
        .first()
    )
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt version not found",
        )

    return PromptVersionOut.model_validate(version)


# --- Standalone Prompt Routes (/api/prompts/...) ---
standalone_prompt_router = APIRouter(tags=["Prompts"])


@standalone_prompt_router.get(
    "/api/prompts/{prompt_id}/versions", response_model=list[PromptVersionOut]
)
def list_prompt_versions_standalone(
    prompt_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all immutable versions of a prompt directly by prompt ID."""
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found",
        )
    project = db.query(Project).filter(Project.id == prompt.project_id).first()
    if not project or project.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found",
        )

    versions = (
        db.query(PromptVersion)
        .filter(PromptVersion.prompt_id == prompt.id)
        .order_by(PromptVersion.version_number.desc())
        .all()
    )
    return [PromptVersionOut.model_validate(v) for v in versions]


@standalone_prompt_router.post(
    "/api/prompts/{prompt_id}/versions",
    response_model=PromptVersionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_prompt_version_standalone(
    prompt_id: int,
    payload: PromptVersionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new immutable prompt version directly by prompt ID."""
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found",
        )
    project = db.query(Project).filter(Project.id == prompt.project_id).first()
    if not project or project.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found",
        )

    content_hash = _calculate_content_hash(payload.content)

    existing_version = (
        db.query(PromptVersion)
        .filter(
            PromptVersion.prompt_id == prompt.id,
            PromptVersion.content_hash == content_hash,
        )
        .first()
    )
    if existing_version:
        return PromptVersionOut.model_validate(existing_version)

    highest_version = (
        db.query(PromptVersion.version_number)
        .filter(PromptVersion.prompt_id == prompt.id)
        .order_by(PromptVersion.version_number.desc())
        .first()
    )
    next_version = (highest_version[0] + 1) if highest_version else 1

    version = PromptVersion(
        prompt_id=prompt.id,
        version_number=next_version,
        content=payload.content,
        content_hash=content_hash,
        commit_message=payload.commit_message,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return PromptVersionOut.model_validate(version)
