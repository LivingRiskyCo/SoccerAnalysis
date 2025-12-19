"""
Cloud Storage Module
Upload videos and project files to cloud storage
"""

import os
import json
from typing import Optional, Dict, Any, List
from pathlib import Path
import hashlib

# Try to import cloud storage libraries
try:
    import boto3
    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False

try:
    from google.cloud import storage
    GCP_AVAILABLE = True
except ImportError:
    GCP_AVAILABLE = False

try:
    from azure.storage.blob import BlobServiceClient
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

# Try to import logger
try:
    from ...utils.logger_config import get_logger
except ImportError:
    try:
        from soccer_analysis.utils.logger_config import get_logger
    except ImportError:
        try:
            from utils.logger_config import get_logger
        except ImportError:
            import logging
            get_logger = lambda name: logging.getLogger(name)

logger = get_logger("cloud_storage")


class CloudStorage:
    """
    Cloud storage interface for uploading videos and project files
    Supports AWS S3, Google Cloud Storage, and Azure Blob Storage
    """
    
    def __init__(self,
                 provider: str = "s3",
                 bucket_name: Optional[str] = None,
                 credentials: Optional[Dict[str, str]] = None):
        """
        Initialize cloud storage
        
        Args:
            provider: Cloud provider ("s3", "gcp", "azure")
            bucket_name: Bucket/container name
            credentials: Credentials dictionary (varies by provider)
        """
        self.provider = provider
        self.bucket_name = bucket_name
        self.credentials = credentials or {}
        self.client = None
        
        if provider == "s3" and AWS_AVAILABLE:
            self._init_s3()
        elif provider == "gcp" and GCP_AVAILABLE:
            self._init_gcp()
        elif provider == "azure" and AZURE_AVAILABLE:
            self._init_azure()
        else:
            logger.warning(f"Cloud provider '{provider}' not available or not configured")
    
    def _init_s3(self):
        """Initialize AWS S3 client"""
        try:
            access_key = self.credentials.get('access_key_id')
            secret_key = self.credentials.get('secret_access_key')
            region = self.credentials.get('region', 'us-east-1')
            
            if access_key and secret_key:
                self.client = boto3.client(
                    's3',
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    region_name=region
                )
            else:
                # Use default credentials (from environment or IAM role)
                self.client = boto3.client('s3')
            
            logger.info("AWS S3 client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize S3: {e}")
            self.client = None
    
    def _init_gcp(self):
        """Initialize Google Cloud Storage client"""
        try:
            credentials_path = self.credentials.get('credentials_path')
            if credentials_path:
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
            
            self.client = storage.Client()
            logger.info("Google Cloud Storage client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize GCP: {e}")
            self.client = None
    
    def _init_azure(self):
        """Initialize Azure Blob Storage client"""
        try:
            connection_string = self.credentials.get('connection_string')
            if connection_string:
                self.client = BlobServiceClient.from_connection_string(connection_string)
            else:
                account_name = self.credentials.get('account_name')
                account_key = self.credentials.get('account_key')
                if account_name and account_key:
                    self.client = BlobServiceClient(
                        account_url=f"https://{account_name}.blob.core.windows.net",
                        credential=account_key
                    )
            
            logger.info("Azure Blob Storage client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Azure: {e}")
            self.client = None
    
    def upload_file(self,
                   local_path: str,
                   remote_path: str,
                   progress_callback: Optional[callable] = None) -> bool:
        """
        Upload a file to cloud storage
        
        Args:
            local_path: Local file path
            remote_path: Remote path in cloud
            progress_callback: Optional callback for upload progress
            
        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            logger.error("Cloud storage client not initialized")
            return False
        
        if not os.path.exists(local_path):
            logger.error(f"File not found: {local_path}")
            return False
        
        try:
            if self.provider == "s3":
                return self._upload_s3(local_path, remote_path, progress_callback)
            elif self.provider == "gcp":
                return self._upload_gcp(local_path, remote_path, progress_callback)
            elif self.provider == "azure":
                return self._upload_azure(local_path, remote_path, progress_callback)
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return False
    
    def _upload_s3(self, local_path: str, remote_path: str, progress_callback: Optional[callable]) -> bool:
        """Upload to S3"""
        try:
            self.client.upload_file(
                local_path,
                self.bucket_name,
                remote_path,
                Callback=progress_callback
            )
            logger.info(f"Uploaded {local_path} to s3://{self.bucket_name}/{remote_path}")
            return True
        except Exception as e:
            logger.error(f"S3 upload failed: {e}")
            return False
    
    def _upload_gcp(self, local_path: str, remote_path: str, progress_callback: Optional[callable]) -> bool:
        """Upload to GCP"""
        try:
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(remote_path)
            blob.upload_from_filename(local_path)
            logger.info(f"Uploaded {local_path} to gs://{self.bucket_name}/{remote_path}")
            return True
        except Exception as e:
            logger.error(f"GCP upload failed: {e}")
            return False
    
    def _upload_azure(self, local_path: str, remote_path: str, progress_callback: Optional[callable]) -> bool:
        """Upload to Azure"""
        try:
            container_client = self.client.get_container_client(self.bucket_name)
            with open(local_path, 'rb') as data:
                container_client.upload_blob(name=remote_path, data=data, overwrite=True)
            logger.info(f"Uploaded {local_path} to Azure blob {self.bucket_name}/{remote_path}")
            return True
        except Exception as e:
            logger.error(f"Azure upload failed: {e}")
            return False
    
    def download_file(self,
                     remote_path: str,
                     local_path: str,
                     progress_callback: Optional[callable] = None) -> bool:
        """
        Download a file from cloud storage
        
        Args:
            remote_path: Remote path in cloud
            local_path: Local file path to save to
            progress_callback: Optional callback for download progress
            
        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            return False
        
        try:
            if self.provider == "s3":
                self.client.download_file(self.bucket_name, remote_path, local_path, Callback=progress_callback)
            elif self.provider == "gcp":
                bucket = self.client.bucket(self.bucket_name)
                blob = bucket.blob(remote_path)
                blob.download_to_filename(local_path)
            elif self.provider == "azure":
                container_client = self.client.get_container_client(self.bucket_name)
                with open(local_path, 'wb') as download_file:
                    download_file.write(container_client.download_blob(remote_path).readall())
            
            logger.info(f"Downloaded {remote_path} to {local_path}")
            return True
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False
    
    def list_files(self, prefix: str = "") -> List[str]:
        """
        List files in cloud storage
        
        Args:
            prefix: Path prefix to filter files
            
        Returns:
            List of file paths
        """
        if not self.client:
            return []
        
        files = []
        try:
            if self.provider == "s3":
                response = self.client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
                files = [obj['Key'] for obj in response.get('Contents', [])]
            elif self.provider == "gcp":
                bucket = self.client.bucket(self.bucket_name)
                blobs = bucket.list_blobs(prefix=prefix)
                files = [blob.name for blob in blobs]
            elif self.provider == "azure":
                container_client = self.client.get_container_client(self.bucket_name)
                blobs = container_client.list_blobs(name_starts_with=prefix)
                files = [blob.name for blob in blobs]
        except Exception as e:
            logger.error(f"List files failed: {e}")
        
        return files
    
    def upload_project(self,
                      project_path: str,
                      project_name: str,
                      include_video: bool = True) -> Optional[str]:
        """
        Upload entire project to cloud
        
        Args:
            project_path: Local project directory path
            project_name: Project name
            include_video: Whether to include video files
            
        Returns:
            Cloud project path or None
        """
        if not os.path.exists(project_path):
            logger.error(f"Project path not found: {project_path}")
            return None
        
        project_id = hashlib.md5(project_name.encode()).hexdigest()[:8]
        cloud_project_path = f"projects/{project_id}"
        
        # Upload project files
        uploaded_files = []
        for root, dirs, files in os.walk(project_path):
            for file in files:
                # Skip video files if not included
                if not include_video and file.endswith(('.mp4', '.avi', '.mov', '.mkv')):
                    continue
                
                local_file = os.path.join(root, file)
                relative_path = os.path.relpath(local_file, project_path)
                remote_path = f"{cloud_project_path}/{relative_path}".replace('\\', '/')
                
                if self.upload_file(local_file, remote_path):
                    uploaded_files.append(remote_path)
        
        # Create project manifest
        manifest = {
            'project_name': project_name,
            'project_id': project_id,
            'uploaded_files': uploaded_files,
            'include_video': include_video
        }
        
        manifest_path = f"{cloud_project_path}/manifest.json"
        manifest_local = os.path.join(project_path, 'cloud_manifest.json')
        with open(manifest_local, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        if self.upload_file(manifest_local, manifest_path):
            os.remove(manifest_local)
            logger.info(f"Project uploaded: {cloud_project_path}")
            return cloud_project_path
        
        return None

