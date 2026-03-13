import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy import select

from src.images.repository.media_item_repository import MediaRepository
from src.galleries.dto.gallery_search_dto import GallerySearchDto
from src.common.base_dto import MimeTypeEnum, GenerationModelEnum
from src.common.schema.media_item_model import MediaItem, JobStatusEnum

@pytest.mark.anyio
async def test_media_repository_query_success():
    mock_db = AsyncMock()
    
    mock_count_result = MagicMock()
    mock_count_result.scalar_one.return_value = 1
    
    from datetime import datetime
    mock_item = MediaItem(
        id=1, workspace_id=1, user_email="test@example.com",
        mime_type="image/png", model="imagen-3.0-generate-001",
        aspect_ratio="1:1", status="completed",
        created_at=datetime.now(), updated_at=datetime.now(),
        gcs_uris=[], thumbnail_uris=[]
    )

    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [mock_item]
    
    mock_db.execute.side_effect = [mock_count_result, mock_result]

    repo = MediaRepository(db=mock_db)

    search_dto = GallerySearchDto(
        limit=10, offset=0,
        user_email="test@example.com",
        mime_type=MimeTypeEnum.IMAGE_PNG,
        model=GenerationModelEnum.IMAGEN_3_001,
        status=JobStatusEnum.COMPLETED
    )

    response = await repo.query(search_dto=search_dto, workspace_id=1)

    assert response.count == 1
    assert len(response.data) == 1
    assert response.data[0].id == 1
    assert mock_db.execute.call_count == 2

@pytest.mark.anyio
async def test_media_repository_query_wildcard():
    mock_db = AsyncMock()
    mock_count = MagicMock()
    mock_count.scalar_one.return_value = 0
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = []
    mock_db.execute.side_effect = [mock_count, mock_result]

    repo = MediaRepository(db=mock_db)

    search_dto = GallerySearchDto(
        limit=10, offset=0
    )
    search_dto.mime_type = MagicMock()
    search_dto.mime_type.value = "image/*"


    response = await repo.query(search_dto=search_dto)

    assert response.count == 0
