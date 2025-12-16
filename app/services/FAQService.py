"""
FAQ Service for S11.
Manages frequently asked questions in the local knowledge database.
"""

from pymongo.collection import Collection
from pymongo import ASCENDING
from .common.BaseCRUDService import BaseCRUDService
from ..utils.pageable import Pageable
from typing import Any


class FAQService(BaseCRUDService):
    """Service for managing FAQs."""
    
    def __init__(self, collection: Collection):
        super().__init__(collection=collection, enable_timing=False)

    def get_collection(self, pageable: Pageable, filters: dict[str, Any] | None = None):
        """
        Get all FAQs sorted by 'question' ascending.
        """
        filters = filters or {}
        
        return [
            *self.collection.find(
                filters,
                sort=[('question', ASCENDING)],
                **pageable.get_kwargs(),
            )
        ]

    def get_all_faqs(self) -> list:
        """
        Get all FAQs without pagination (for snapshot).
        """
        return list(self.collection.find(sort=[('question', ASCENDING)]))
