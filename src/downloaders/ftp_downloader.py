"""
Example plugin: FTP Downloader

This is an example of how to add a new downloader type.
To use this:
1. Ensure the file is in the downloaders directory
2. Register it in downloader_factory.py or use DownloaderFactory.discover_plugins()

Note: This is a template - uncomment and modify for actual FTP support.
"""

# Uncomment for actual FTP support:
# from .base_downloader import BaseDownloader, DownloadResult
# import ftplib
# from pathlib import Path
# 
# 
# class FtpDownloader(BaseDownloader):
#     """FTP downloader for standard FTP protocol."""
# 
#     def __init__(self, source_config, logger, timeout=30):
#         super().__init__(source_config, logger)
#         self.timeout = timeout
#         self.ftp: ftplib.FTP = None
# 
#     def connect(self):
#         """Establish FTP connection."""
#         try:
#             self.ftp = ftplib.FTP()
#             self.ftp.connect(
#                 self.source_config.host,
#                 self.source_config.port,
#                 timeout=self.timeout
#             )
#             self.ftp.login(
#                 self.source_config.auth_credentials.username,
#                 self.source_config.auth_credentials.password
#             )
#             return True
#         except Exception as e:
#             self.logger.error(f"[FTP CONNECT FAILED] {e}")
#             return False
# 
#     def test_connection(self):
#         if self.connect():
#             try:
#                 self.ftp.quit()
#             except:
#                 pass
#             return True
#         return False
# 
#     def build_url(self, filename):
#         path = self.source_config.path
#         if not path.endswith('/'):
#             path += '/'
#         return path + filename
# 
#     def download(self, url, local_path, filename, retry_count=0):
#         import time
#         start_time = time.time()
#         result = DownloadResult(
#             success=False,
#             source_name=self.name,
#             url=f"ftp://{self.source_config.host}/{url}",
#             filename=filename,
#             retry_count=retry_count
#         )
# 
#         try:
#             if not self.ftp:
#                 if not self.connect():
#                     result.error = "Connection failed"
#                     return result
# 
#             local_path.mkdir(parents=True, exist_ok=True)
#             file_path = local_path / filename
# 
#             with open(file_path, 'wb') as f:
#                 self.ftp.retrbinary(f'RETR {url}', f.write)
# 
#             result.file_size = file_path.stat().st_size
#             result.local_path = str(file_path)
#             result.success = True
#             result.duration = time.time() - start_time
#             result.content_hash = self.calculate_hash(file_path)
# 
#         except Exception as e:
#             result.error = str(e)
# 
#         return result
# 
#     def close(self):
#         if self.ftp:
#             try:
#                 self.ftp.quit()
#             except:
#                 pass
