import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.core.security import create_access_token, get_password_hash
from app.database import Base, get_db
from app.main import app
from app.models.project import Project
from app.models.user import User

engine = create_engine(settings.database_url, future=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def user1(db_session):
    user = User(
        email="user1@example.com",
        hashed_password=get_password_hash("password123"),
        full_name="User One",
    )
    db_session.add(user)
    db_session.flush()
    db_session.refresh(user)
    return user


@pytest.fixture
def user2(db_session):
    user = User(
        email="user2@example.com",
        hashed_password=get_password_hash("password123"),
        full_name="User Two",
    )
    db_session.add(user)
    db_session.flush()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers_user1(user1):
    token = create_access_token(user1.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_user2(user2):
    token = create_access_token(user2.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_project(db_session, user1):
    project = Project(
        user_id=user1.id,
        name="Customer Support Evaluation",
        description="Eval suite for support bot",
    )
    db_session.add(project)
    db_session.flush()
    db_session.refresh(project)
    return project
