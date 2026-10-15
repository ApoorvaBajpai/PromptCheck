import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.core.security import create_access_token, get_password_hash
from app.database import Base, get_db
from app.engine.client import FakeGeminiClient
from app.main import app
from app.models.project import Project
from app.models.user import User

engine = create_engine(settings.database_url, future=True)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
    join_transaction_mode="create_savepoint",
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    # Clean up any leftover rows from previous test runs
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture(autouse=True)
def mock_gemini_client_for_api_keys(monkeypatch):
    """Ensure automated API key validation tests do not depend on real Gemini network calls."""
    fake_client = FakeGeminiClient()
    monkeypatch.setattr(
        "app.api.projects.get_gemini_client_for_key",
        lambda api_key: fake_client,
    )


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        nonlocal nested
        if trans.nested:
            return
        if not connection.closed and connection.in_transaction():
            nested = connection.begin_nested()

    yield session

    session.close()
    if not connection.closed and connection.in_transaction():
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
