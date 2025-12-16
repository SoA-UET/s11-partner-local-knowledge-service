"""
Snapshot Service for S11.
Handles A33 API - Creates snapshot of packages and FAQs for S12.
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional

from .SeaweedFSService import get_seaweedfs_service
from .PackageService import PackageService
from .FAQService import FAQService
from .MessageQueueService import MessageQueueService

logger = logging.getLogger(__name__)


class SnapshotService:
    """
    Service to handle snapshot requests from S12 (A33 API).
    Creates a snapshot of packages and FAQs, stores in SeaweedFS,
    and returns the file ID.
    """

    def __init__(
        self, 
        package_service: PackageService, 
        faq_service: FAQService
    ):
        self.package_service = package_service
        self.faq_service = faq_service
        self._mq_service: Optional[MessageQueueService] = None
        
        # Queue names from environment
        self.request_queue = os.getenv("SNAPSHOT_REQUESTS_QUEUE_NAME", "snapshot_requests")
        self.response_queue = os.getenv("SNAPSHOT_RESPONSES_QUEUE_NAME", "snapshot_responses")

    def set_mq_service(self, mq_service: MessageQueueService):
        """Set the MessageQueueService for RabbitMQ communication."""
        self._mq_service = mq_service

    def create_snapshot(self) -> str:
        """
        Create a snapshot of all packages and FAQs.
        Upload to SeaweedFS and return the file ID.
        """
        # Get all packages and FAQs
        packages = self.package_service.get_all_packages()
        faqs = self.faq_service.get_all_faqs()
        
        # Serialize ObjectIds to strings
        def serialize_doc(doc):
            result = {}
            for key, value in doc.items():
                if key == '_id':
                    result['id'] = str(value)
                elif hasattr(value, '__str__') and type(value).__name__ == 'ObjectId':
                    result[key] = str(value)
                elif isinstance(value, datetime):
                    result[key] = value.isoformat()
                else:
                    result[key] = value
            return result
        
        snapshot_data = {
            "packages": [serialize_doc(p) for p in packages],
            "faqs": [serialize_doc(f) for f in faqs],
            "created_at": datetime.utcnow().isoformat(),
        }
        
        # Convert to JSON and upload to SeaweedFS
        json_content = json.dumps(snapshot_data, ensure_ascii=False, indent=2)
        filename = f"snapshot_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        
        seaweed_service = get_seaweedfs_service()
        seaweed_file_id = seaweed_service.upload_file(
            json_content.encode('utf-8'), 
            filename
        )
        
        logger.info(f"Created snapshot with {len(packages)} packages and {len(faqs)} FAQs, file ID: {seaweed_file_id}")
        
        return seaweed_file_id

    def handle_snapshot_request(self, message: dict):
        """
        Handle incoming snapshot request from S12.
        Message format:
        {
            "method": "snapshot",
            "params": {},
            "id": "request_id"
        }
        """
        request_id = message.get("id")
        method = message.get("method")
        
        if not request_id:
            logger.error("Received snapshot request without id")
            return
        
        if method != "snapshot":
            logger.error(f"Unknown method: {method}")
            self._send_error_response(request_id, f"Unknown method: {method}")
            return
        
        try:
            seaweed_file_id = self.create_snapshot()
            self._send_success_response(request_id, {"seaweed_file_id": seaweed_file_id})
        except Exception as e:
            logger.error(f"Failed to create snapshot: {e}")
            self._send_error_response(request_id, str(e))

    def _send_success_response(self, request_id: str, content: dict):
        """Send a success response to S12."""
        if not self._mq_service:
            logger.error("MQ service not set, cannot send response")
            return
        
        response = {
            "id": request_id,
            "result": {
                "status": "success",
                "content": content
            }
        }
        
        self._mq_service.declare_queue(self.response_queue)
        self._mq_service.publish_message(self.response_queue, response)
        logger.info(f"Sent snapshot success response for request {request_id}")

    def _send_error_response(self, request_id: str, error_message: str):
        """Send an error response to S12."""
        if not self._mq_service:
            logger.error("MQ service not set, cannot send response")
            return
        
        response = {
            "id": request_id,
            "result": {
                "status": "error",
                "content": error_message
            }
        }
        
        self._mq_service.declare_queue(self.response_queue)
        self._mq_service.publish_message(self.response_queue, response)
        logger.info(f"Sent snapshot error response for request {request_id}")
