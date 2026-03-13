import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.generation_options.generation_options_controller import router

@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)

def test_get_image_generation_options_success(client):
    response = client.get("/api/options/image-generation")
    assert response.status_code == 200
    data = response.json()
    # verify some fields exist
    assert "generation_models" in data or "generationModels" in data
    assert "styles" in data
