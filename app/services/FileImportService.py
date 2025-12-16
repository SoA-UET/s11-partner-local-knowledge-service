"""
File Import Service for S11.
Manages file import records and orchestrates the import process.
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, Any
from bson import ObjectId
from pymongo.collection import Collection
from pymongo import DESCENDING
from flask_restx import abort

from .common.BaseCRUDService import BaseCRUDService
from .SeaweedFSService import get_seaweedfs_service
from .MessageQueueService import MessageQueueService
from ..utils.pageable import Pageable
from ..utils.db import str_to_objectid

logger = logging.getLogger(__name__)


# File import status constants
class FileImportStatus:
    PENDING = "PENDING"
    EXTRACTED = "EXTRACTED"
    FAILED = "FAILED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class FileImportService(BaseCRUDService):
    """Service for managing file imports."""
    
    def __init__(self, collection: Collection, packages_collection: Collection):
        super().__init__(collection=collection, enable_timing=False)
        self.packages_collection = packages_collection
        self._mq_service: Optional[MessageQueueService] = None
        
        # Queue names from environment
        self.request_queue = os.getenv("FILE_IMPORT_REQUEST_QUEUE", "file_import_requests")
        self.response_queue = os.getenv("FILE_IMPORT_RESPONSE_QUEUE", "file_import_responses")

    def set_mq_service(self, mq_service: MessageQueueService):
        """Set the MessageQueueService for RabbitMQ communication."""
        self._mq_service = mq_service

    def get_collection(self, pageable: Pageable, filters: dict[str, Any] | None = None):
        """
        Get all file imports sorted by 'created_at' descending.
        """
        filters = filters or {}
        
        return [
            *self.collection.find(
                filters,
                sort=[('created_at', DESCENDING)],
                **pageable.get_kwargs(),
            )
        ]

    def create_file_import(self, file_content: bytes, file_name: str) -> dict:
        """
        Create a new file import record and initiate processing.
        
        1. Upload file to SeaweedFS
        2. Create file_imports record with PENDING status
        3. Send import_file request to S15 via RabbitMQ
        4. Return the file import record
        """
        # Step 1: Upload to SeaweedFS
        seaweed_service = get_seaweedfs_service()
        seaweed_file_id = seaweed_service.upload_file(file_content, file_name)
        
        # Step 2: Create file_imports record
        file_import_doc = {
            "file_name": file_name,
            "seaweed_file_id": seaweed_file_id,
            "packages": [],
            "status": FileImportStatus.PENDING,
            "created_at": datetime.utcnow(),
        }
        
        result = self.collection.insert_one(file_import_doc)
        file_import_id = str(result.inserted_id)
        
        # Step 3: Send import_file request to S15
        if self._mq_service:
            request_message = {
                "method": "import_file",
                "params": {
                    "seaweed_file_id": seaweed_file_id,
                },
                "id": file_import_id  # Use file import ID as RPC request ID
            }
            
            try:
                self._mq_service.declare_queue(self.request_queue)
                self._mq_service.publish_message(self.request_queue, request_message)
                logger.info(f"Sent import_file request for file import {file_import_id}")
            except Exception as e:
                logger.error(f"Failed to send import_file request: {e}")
                # Update status to FAILED
                self.collection.update_one(
                    {"_id": result.inserted_id},
                    {"$set": {"status": FileImportStatus.FAILED, "error_message": str(e)}}
                )
                raise
        
        return {
            "_id": result.inserted_id,
            **file_import_doc
        }

    def handle_import_response(self, response: dict):
        """
        Handle response from S15 File Importing AI Agent.
        Updates the file_imports record based on the response.
        """
        request_id = response.get("id")
        if not request_id:
            logger.error("Received import response without id")
            return
        
        result = response.get("result", {})
        status = result.get("status")
        content = result.get("content", {})
        
        object_id = str_to_objectid(request_id)
        if not object_id:
            logger.error(f"Invalid file import id: {request_id}")
            return
        
        if status == "success":
            # Extract packages from response
            packages = content.get("packages", [])
            update_doc = {
                "status": FileImportStatus.EXTRACTED,
                "packages": packages,
            }
            logger.info(f"File import {request_id} extracted {len(packages)} packages")
        else:
            # Handle error
            error_message = content if isinstance(content, str) else str(content)
            update_doc = {
                "status": FileImportStatus.FAILED,
                "error_message": error_message,
            }
            logger.error(f"File import {request_id} failed: {error_message}")
        
        self.collection.update_one(
            {"_id": object_id},
            {"$set": update_doc}
        )

    def approve_file_import(self, file_import_id: str) -> dict:
        """
        Approve a file import, inserting extracted packages into main database.
        Can only be done if status is EXTRACTED.
        """
        object_id = str_to_objectid(file_import_id)
        if not object_id:
            abort(404, "Invalid file import ID")
        
        file_import = self.collection.find_one({"_id": object_id})
        if not file_import:
            abort(404, "File import not found")
        
        if file_import.get("status") != FileImportStatus.EXTRACTED:
            abort(400, f"Cannot approve file import with status: {file_import.get('status')}")
        
        # Insert packages into main packages collection
        packages = file_import.get("packages", [])
        if packages:
            # Remove any _id fields from packages before insertion
            clean_packages = [{k: v for k, v in pkg.items() if k != "_id"} for pkg in packages]
            self.packages_collection.insert_many(clean_packages)
            logger.info(f"Inserted {len(packages)} packages from file import {file_import_id}")
        
        # Update status to APPROVED
        self.collection.update_one(
            {"_id": object_id},
            {"$set": {"status": FileImportStatus.APPROVED}}
        )
        
        return {"_id": object_id, "status": FileImportStatus.APPROVED}

    def reject_file_import(self, file_import_id: str) -> dict:
        """
        Reject a file import.
        Can only be done if status is EXTRACTED.
        """
        object_id = str_to_objectid(file_import_id)
        if not object_id:
            abort(404, "Invalid file import ID")
        
        file_import = self.collection.find_one({"_id": object_id})
        if not file_import:
            abort(404, "File import not found")
        
        if file_import.get("status") != FileImportStatus.EXTRACTED:
            abort(400, f"Cannot reject file import with status: {file_import.get('status')}")
        
        # Update status to REJECTED
        self.collection.update_one(
            {"_id": object_id},
            {"$set": {"status": FileImportStatus.REJECTED}}
        )
        
        return {"_id": object_id, "status": FileImportStatus.REJECTED}

    def update_extracted_packages(self, file_import_id: str, packages: list) -> dict:
        """
        Update the extracted packages of a file import.
        Frontend sends the full list of packages after editing.
        """
        object_id = str_to_objectid(file_import_id)
        if not object_id:
            abort(404, "Invalid file import ID")
        
        file_import = self.collection.find_one({"_id": object_id})
        if not file_import:
            abort(404, "File import not found")
        
        if file_import.get("status") != FileImportStatus.EXTRACTED:
            abort(400, f"Cannot update packages for file import with status: {file_import.get('status')}")
        
        # Update packages
        self.collection.update_one(
            {"_id": object_id},
            {"$set": {"packages": packages}}
        )
        
        return {"_id": object_id, "message": "Extracted packages updated successfully"}
