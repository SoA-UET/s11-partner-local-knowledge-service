"""
SeaweedFS Service for S11.
Handles file upload and download to/from SeaweedFS.
"""

import os
import logging
import requests
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class SeaweedFSService:
    """
    Service to handle file operations with SeaweedFS.
    """

    def __init__(self):
        self.master_url = os.getenv("SEAWEED_MASTER_URL", "http://localhost:9333")
        self.public_url = os.getenv("SEAWEED_PUBLIC_URL", "http://localhost:8080")

    def _get_upload_url(self) -> Tuple[str, str]:
        """
        Get an upload URL from SeaweedFS master.
        Returns (fid, upload_url).
        """
        try:
            response = requests.get(f"{self.master_url}/dir/assign", timeout=10)
            response.raise_for_status()
            data = response.json()
            fid = data["fid"]
            url = data["url"]
            return fid, f"http://{url}/{fid}"
        except Exception as e:
            logger.error(f"Failed to get upload URL from SeaweedFS: {e}")
            raise RuntimeError(f"Failed to get upload URL: {e}")

    def upload_file(self, file_content: bytes, filename: str) -> str:
        """
        Upload a file to SeaweedFS.
        Returns the file ID (fid).
        """
        try:
            fid, upload_url = self._get_upload_url()
            
            files = {
                'file': (filename, file_content)
            }
            
            response = requests.post(upload_url, files=files, timeout=60)
            response.raise_for_status()
            
            logger.info(f"Successfully uploaded file {filename} with fid: {fid}")
            return fid
        except Exception as e:
            logger.error(f"Failed to upload file to SeaweedFS: {e}")
            raise RuntimeError(f"Failed to upload file: {e}")

    def download_file(self, fid: str) -> bytes:
        """
        Download a file from SeaweedFS by file ID.
        Returns the file content as bytes.
        """
        try:
            # First, lookup the volume to get the URL
            volume_id = fid.split(",")[0]
            lookup_url = f"{self.master_url}/dir/lookup?volumeId={volume_id}"
            
            lookup_response = requests.get(lookup_url, timeout=10)
            lookup_response.raise_for_status()
            lookup_data = lookup_response.json()
            
            if "locations" not in lookup_data or len(lookup_data["locations"]) == 0:
                raise RuntimeError(f"No locations found for volume {volume_id}")
            
            location = lookup_data["locations"][0]
            file_url = f"http://{location['url']}/{fid}"
            
            response = requests.get(file_url, timeout=60)
            response.raise_for_status()
            
            logger.info(f"Successfully downloaded file with fid: {fid}")
            return response.content
        except Exception as e:
            logger.error(f"Failed to download file from SeaweedFS: {e}")
            raise RuntimeError(f"Failed to download file: {e}")

    def delete_file(self, fid: str) -> bool:
        """
        Delete a file from SeaweedFS by file ID.
        Returns True if successful.
        """
        try:
            volume_id = fid.split(",")[0]
            lookup_url = f"{self.master_url}/dir/lookup?volumeId={volume_id}"
            
            lookup_response = requests.get(lookup_url, timeout=10)
            lookup_response.raise_for_status()
            lookup_data = lookup_response.json()
            
            if "locations" not in lookup_data or len(lookup_data["locations"]) == 0:
                logger.warning(f"No locations found for volume {volume_id}, file may not exist")
                return False
            
            location = lookup_data["locations"][0]
            file_url = f"http://{location['url']}/{fid}"
            
            response = requests.delete(file_url, timeout=30)
            response.raise_for_status()
            
            logger.info(f"Successfully deleted file with fid: {fid}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete file from SeaweedFS: {e}")
            return False

    def get_public_url(self, fid: str) -> str:
        """
        Get the public URL for a file.
        """
        return f"{self.public_url}/{fid}"


# Global instance
_seaweedfs_service: Optional[SeaweedFSService] = None


def get_seaweedfs_service() -> SeaweedFSService:
    """Get or create the global SeaweedFSService instance."""
    global _seaweedfs_service
    if _seaweedfs_service is None:
        _seaweedfs_service = SeaweedFSService()
    return _seaweedfs_service
