"""
Package Service for S11.
Manages telecom service packages in the local knowledge database.
"""

from pymongo.collection import Collection
from pymongo import ASCENDING
from .common.BaseCRUDService import BaseCRUDService
from ..utils.pageable import Pageable
from typing import Any


class PackageService(BaseCRUDService):
    """Service for managing telecom packages."""
    
    def __init__(self, collection: Collection):
        super().__init__(collection=collection, enable_timing=False)

    def get_collection(self, pageable: Pageable, filters: dict[str, Any] | None = None):
        """
        Get all packages sorted by 'Mã dịch vụ' ascending.
        """
        filters = filters or {}
        
        return [
            *self.collection.find(
                filters,
                sort=[('Mã dịch vụ', ASCENDING)],
                **pageable.get_kwargs(),
            )
        ]

    def get_all_packages(self) -> list:
        """
        Get all packages without pagination (for snapshot).
        """
        return list(self.collection.find(sort=[('Mã dịch vụ', ASCENDING)]))
