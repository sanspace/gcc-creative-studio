# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import List, Optional

from google.cloud import firestore
from google.cloud.firestore_v1.base_aggregation import AggregationResult
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.query_results import QueryResultsList

from src.common.base_repository import BaseRepository
from src.common.dto.pagination_response_dto import PaginationResponseDto
from src.source_assets.dto.source_asset_search_dto import SourceAssetSearchDto
from src.source_assets.schema.source_asset_model import (
    AssetScopeEnum,
    AssetTypeEnum,
    SourceAssetModel,
)


class SourceAssetRepository(BaseRepository[SourceAssetModel]):
    """Handles database operations for UserAsset objects in Firestore."""

    def __init__(self):
        super().__init__(
            collection_name="source_assets", model=SourceAssetModel
        )

    def find_by_hash(
        self, user_id: str, file_hash: str
    ) -> Optional[SourceAssetModel]:
        """Finds a user asset by its file hash to prevent duplicates."""
        query = (
            self.collection_ref.where(
                filter=FieldFilter("user_id", "==", user_id)
            )
            .where(filter=FieldFilter("file_hash", "==", file_hash))
            .limit(1)
        )
        docs = list(query.stream())
        if not docs:
            return None
        return self.model.model_validate(docs[0].to_dict())

    def query(
        self,
        search_dto: SourceAssetSearchDto,
        target_user_id: Optional[str] = None,
    ) -> PaginationResponseDto[SourceAssetModel]:
        """
        Performs a paginated query for assets. If target_user_id is provided,
        it scopes the search to that specific user.
        """
        base_query = self.collection_ref

        # Apply filters from the DTO
        if search_dto.mime_type:
            if search_dto.mime_type.endswith("image/*"):
                # TODO: Handle wildcard prefix search (e.g., "image/*")
                # by creating a range query that finds all strings starting with the prefix.
                base_query = base_query.where(
                    filter=FieldFilter("mime_type", "!=", "video/mp4")
                )
            else:
                # Standard exact match
                base_query = base_query.where(
                    filter=FieldFilter("mime_type", "==", search_dto.mime_type)
                )
        if target_user_id:
            base_query = base_query.where(
                filter=FieldFilter("user_id", "==", target_user_id)
            )
        if search_dto.scope:
            base_query = base_query.where(
                filter=FieldFilter("scope", "==", search_dto.scope)
            )
        if search_dto.asset_type:
            base_query = base_query.where(
                filter=FieldFilter("asset_type", "==", search_dto.asset_type)
            )
        if search_dto.original_filename:
            # This enables prefix searching (e.g., 'file' matches 'file.txt')
            base_query = base_query.where(
                filter=FieldFilter(
                    "original_filename", ">=", search_dto.original_filename
                )
            ).where(
                filter=FieldFilter(
                    "original_filename",
                    "<=",
                    search_dto.original_filename + "\uf8ff",
                )
            )

        count_query = base_query.count(alias="total")
        aggregation_result = count_query.get()

        total_count = 0
        if (
            isinstance(aggregation_result, QueryResultsList)
            and aggregation_result
            and isinstance(aggregation_result[0][0], AggregationResult)  # type: ignore
        ):
            total_count = int(aggregation_result[0][0].value)  # type: ignore

        data_query = base_query.order_by(
            "created_at", direction=firestore.Query.DESCENDING
        )

        if search_dto.start_after:
            last_doc_snapshot = self.collection_ref.document(
                search_dto.start_after
            ).get()
            if last_doc_snapshot.exists:
                data_query = data_query.start_after(last_doc_snapshot)

        data_query = data_query.limit(search_dto.limit)

        # Stream results and validate with the Pydantic model
        documents = list(data_query.stream())
        media_item_data = [doc.to_dict() for doc in documents]

        next_page_cursor = None
        if len(documents) == search_dto.limit:
            # The cursor is the ID of the last document fetched.
            next_page_cursor = documents[-1].id

        return PaginationResponseDto[SourceAssetModel](
            count=total_count,
            next_page_cursor=next_page_cursor,
            data=media_item_data,  # type: ignore
        )

    def find_by_scope_and_types(
        self, scope: AssetScopeEnum, asset_types: List[AssetTypeEnum]
    ) -> List[SourceAssetModel]:
        """
        Finds all assets matching a specific scope and a list of asset types.
        """
        if not asset_types:
            return []

        result = await self.db.execute(
            select(self.model)
            .where(self.model.scope == scope.value)
            .where(self.model.asset_type.in_([t.value for t in asset_types]))
        )
        assets = result.scalars().all()
        return [self.schema.model_validate(asset) for asset in assets]

    async def find_private_by_user_and_types(
        self, user_id: int, asset_types: List[AssetTypeEnum]
    ) -> List[SourceAssetModel]:
        """
        Finds all private assets for a specific user that match a list of asset types.
        """
        if not asset_types:
            return []

        result = await self.db.execute(
            select(self.model)
            .where(self.model.user_id == user_id)
            .where(self.model.scope == AssetScopeEnum.PRIVATE.value)
            .where(self.model.asset_type.in_([t.value for t in asset_types]))
        )
        assets = result.scalars().all()
        return [self.schema.model_validate(asset) for asset in assets]

    async def get_by_gcs_uri(self, gcs_uri: str) -> Optional[SourceAssetModel]:
        """Finds an asset by its GCS URI."""
        result = await self.db.execute(
            select(self.model).where(self.model.gcs_uri == gcs_uri).limit(1)
        )
        asset = result.scalar_one_or_none()
        if not asset:
            return None
        return self.schema.model_validate(asset)

    async def find_system_and_private_assets_by_types(
        self, user_id: int, asset_types: List[AssetTypeEnum]
    ) -> List[SourceAssetModel]:
        """
        Finds all system assets AND private assets for a specific user that match a list of asset types.
        This combines two queries into one using OR logic.
        """
        if not asset_types:
            return []

        result = await self.db.execute(
            select(self.model)
            .where(
                or_(
                    self.model.scope == AssetScopeEnum.SYSTEM.value,
                    and_(
                        self.model.user_id == user_id,
                        self.model.scope == AssetScopeEnum.PRIVATE.value,
                    ),
                )
            )
            .where(self.model.asset_type.in_([t.value for t in asset_types]))
        )
        assets = result.scalars().all()
        return [self.schema.model_validate(asset) for asset in assets]
