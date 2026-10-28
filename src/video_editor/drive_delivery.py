"""Private, resumable delivery copies using the owner's existing drive.file OAuth.

The source folder and its permissions are never changed. Sharing one output file
requires a separate exact-file consent action; uploads start private.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urlencode, urlparse

from .hub_delivery import DeliveryError, private_json, request
from .story_jobs import digest, lock, write

GOOGLE = "https://www.googleapis.com"
FIELDS = "id,name,parents,size,md5Checksum,sha256Checksum,mimeType,webViewLink,trashed,permissions(id,type,role,allowFileDiscovery),appProperties"
ID = re.compile(r"^[A-Za-z0-9_-]{10,200}$")


class DriveDelivery:
    def __init__(self, service, *, transport=request, config=None):
        self.service, self.transport = service, transport
        self.config = Path(config) if config else Path.home() / ".config/asap-gta6"
        self.home = service.home / "delivery"; self.home.mkdir(mode=0o700, exist_ok=True)

    def token(self):
        with lock(self.config / "drive-work-refresh.lock"):
            target = self.config / "drive-work-token.json"; value = private_json(target)
            if value.get("scope") != "https://www.googleapis.com/auth/drive.file" or not value.get("verified_email"):
                raise DeliveryError("VERIFIED_DRIVE_FILE_CONNECTION_REQUIRED")
            if time.time() >= value.get("expires_at", 0) - 60:
                config = private_json(self.config / "google-client.json")["installed"]
                code, _, refreshed = self.transport("POST", "https://oauth2.googleapis.com/token", data=urlencode({
                    "grant_type": "refresh_token", "refresh_token": value["refresh_token"], "client_id": config["client_id"], "client_secret": config["client_secret"]}).encode(), headers={"Content-Type": "application/x-www-form-urlencoded"})
                if code != 200 or not refreshed.get("access_token"):
                    raise DeliveryError("DRIVE_REAUTHORIZE_LOCALLY_REQUIRED")
                if refreshed.get("scope", value["scope"]) != value["scope"]:
                    raise DeliveryError("DRIVE_SCOPE_CHANGED")
                value.update(refreshed); value["expires_at"] = time.time() + value.get("expires_in", 3600); write(target, value)
            return value["access_token"]

    def api(self, method, path, *, data=None, headers=None):
        if not path.startswith(("/drive/v3/", "/upload/drive/v3/")):
            raise DeliveryError("DRIVE_ENDPOINT_DENIED")
        return self.transport(method, GOOGLE + path, data=data, headers={"Authorization": "Bearer " + self.token(), **(headers or {})}, timeout=90)

    def metadata(self, file_id):
        if not isinstance(file_id, str) or not ID.fullmatch(file_id): raise DeliveryError("INVALID_DRIVE_ID")
        code, _, data = self.api("GET", "/drive/v3/files/" + file_id + "?" + urlencode({"fields": FIELDS}))
        if code == 404: return None
        if code != 200: raise DeliveryError("DRIVE_READBACK_FAILED")
        return data

    def generate_id(self):
        code, _, data = self.api("GET", "/drive/v3/files/generateIds?count=1&space=drive&type=files")
        key = (data.get("ids") or [None])[0]
        if code != 200 or not isinstance(key, str) or not ID.fullmatch(key): raise DeliveryError("DRIVE_FILE_ID_REQUIRED")
        return key

    def folder(self):
        receipt = self.home / "folder.json"
        if receipt.exists(): value = json.loads(receipt.read_text())
        else:
            # Recover a previously created app-owned folder before reserving a
            # fresh ID. Never adopt the unrelated source/ASAP folder.
            query = "trashed=false and mimeType='application/vnd.google-apps.folder' and appProperties has { key='astel_delivery' and value='video-workspace-v1' }"
            code, _, found = self.api("GET", "/drive/v3/files?" + urlencode({"q": query, "fields": "files(id),nextPageToken", "pageSize": 2}))
            if code != 200 or found.get("nextPageToken") or len(found.get("files", [])) > 1: raise DeliveryError("DRIVE_DELIVERY_FOLDER_REVIEW_REQUIRED")
            value = {"id": found["files"][0]["id"] if found.get("files") else self.generate_id()}; write(receipt, value)
        data = self.metadata(value["id"])
        if data is None:
            code, _, _ = self.api("POST", "/drive/v3/files?fields=id", data={"id": value["id"], "name": "Astel Video Delivery", "mimeType": "application/vnd.google-apps.folder", "appProperties": {"astel_delivery": "video-workspace-v1"}})
            if code not in (200, 201, 409): raise DeliveryError("DRIVE_FOLDER_CREATE_UNCONFIRMED")
            data = self.metadata(value["id"])
        if not data or data.get("trashed") or data.get("mimeType") != "application/vnd.google-apps.folder" or data.get("appProperties", {}).get("astel_delivery") != "video-workspace-v1":
            raise DeliveryError("DRIVE_DELIVERY_FOLDER_CHANGED")
        if not data.get("permissions") or any(p.get("type") != "user" or p.get("role") != "owner" for p in data["permissions"]):
            raise DeliveryError("DRIVE_DELIVERY_FOLDER_MUST_STAY_PRIVATE")
        return value["id"]

    def receipt(self, sha):
        if not re.fullmatch(r"[a-f0-9]{64}", sha): raise DeliveryError("INVALID_MEDIA_HASH")
        return self.home / (sha + ".json")

    def check(self, metadata, card, folder_id, source):
        if not metadata or metadata.get("trashed") or metadata.get("mimeType") != "video/mp4" or folder_id not in metadata.get("parents", []) or int(metadata.get("size", 0)) != card["artifact"]["bytes"]:
            raise DeliveryError("DRIVE_MEDIA_IDENTITY_MISMATCH")
        if metadata.get("sha256Checksum"):
            valid = metadata["sha256Checksum"] == card["artifact"]["sha256"]
        else:
            with source.open("rb") as stream: local_md5 = hashlib.file_digest(stream, "md5").hexdigest()
            valid = metadata.get("md5Checksum") == local_md5
        if not valid or metadata.get("appProperties", {}).get("astel_sha256") != card["artifact"]["sha256"]:
            raise DeliveryError("DRIVE_MEDIA_HASH_MISMATCH")
        if not metadata.get("permissions") or any(p.get("role") != "owner" and not (p.get("type") == "anyone" and p.get("role") == "reader" and p.get("allowFileDiscovery") is False) for p in metadata["permissions"]):
            raise DeliveryError("DRIVE_MEDIA_PERMISSION_DRIFT")

    @staticmethod
    def session_path(url):
        value = urlparse(url)
        if value.scheme != "https" or value.netloc != "www.googleapis.com" or value.path != "/upload/drive/v3/files" or value.fragment:
            raise DeliveryError("DRIVE_UPLOAD_SESSION_DENIED")
        return value.path + "?" + value.query

    def upload(self, card, cancelled=lambda: None):
        from .story_workspace import story_video
        source = Path(story_video(self.service, card["artifact_job_id"])["path"])
        sha = card["artifact"]["sha256"]; receipt = self.receipt(sha)
        with lock(self.home / "upload.lock"):
            code, _, identity = self.api("GET", "/drive/v3/about?fields=user(emailAddress)")
            if code != 200 or identity.get("user", {}).get("emailAddress", "").lower() != private_json(self.config / "drive-work-token.json")["verified_email"].lower():
                raise DeliveryError("DRIVE_ACCOUNT_CHANGED")
            cancelled(); folder_id = self.folder()
            if receipt.exists(): value = json.loads(receipt.read_text())
            else:
                value = {"file_id": self.generate_id(), "sha256": sha, "folder_id": folder_id, "state": "reserved"}; write(receipt, value)
            if value["folder_id"] != folder_id: raise DeliveryError("DRIVE_DESTINATION_CHANGED")
            metadata = self.metadata(value["file_id"])
            if metadata is None:
                session = value.get("session")
                if not session:
                    cancelled()
                    code, headers, _ = self.api("POST", "/upload/drive/v3/files?uploadType=resumable&fields=" + FIELDS, data={
                        "id": value["file_id"], "name": f"Astel_{card['id']}_v{card['revision']}_{sha[:12]}.mp4", "parents": [folder_id], "mimeType": "video/mp4", "writersCanShare": False,
                        "appProperties": {"astel_sha256": sha, "astel_story": card["id"]}}, headers={"X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(card["artifact"]["bytes"])})
                    session = headers.get("Location") or headers.get("location")
                    if code not in (200, 201) or not session: raise DeliveryError("DRIVE_UPLOAD_INIT_UNCONFIRMED")
                    self.session_path(session); value.update(session=session, state="uploading"); write(receipt, value)
                path = self.session_path(session); size = source.stat().st_size
                code, headers, _ = self.api("PUT", path, data=b"", headers={"Content-Length": "0", "Content-Range": f"bytes */{size}"})
                if code not in (200, 201, 308): raise DeliveryError("DRIVE_UPLOAD_RESUME_REVIEW_REQUIRED")
                if code == 308:
                    span = headers.get("Range") or headers.get("range")
                    if span and not re.fullmatch(r"bytes=0-\d+", span): raise DeliveryError("DRIVE_UPLOAD_RANGE_INVALID")
                    offset = int(span.rsplit("-", 1)[1]) + 1 if span else 0
                    with source.open("rb") as stream:
                        while offset < size:
                            cancelled(); stream.seek(offset); chunk = stream.read(min(8 * 1024 * 1024, size - offset)); end = offset + len(chunk)
                            code, headers, _ = self.api("PUT", path, data=chunk, headers={"Content-Type": "video/mp4", "Content-Length": str(len(chunk)), "Content-Range": f"bytes {offset}-{end-1}/{size}"})
                            if code in (200, 201): break
                            if code != 308: raise DeliveryError("DRIVE_UPLOAD_PAUSED")
                            span = headers.get("Range") or headers.get("range") or ""
                            if not re.fullmatch(r"bytes=0-\d+", span): raise DeliveryError("DRIVE_UPLOAD_RANGE_INVALID")
                            confirmed = int(span.rsplit("-", 1)[1]) + 1
                            if not offset < confirmed <= end: raise DeliveryError("DRIVE_UPLOAD_NO_PROGRESS")
                            offset = confirmed
                metadata = self.metadata(value["file_id"])
            self.check(metadata, card, folder_id, source)
            shared = any(p.get("type") == "anyone" and p.get("role") == "reader" for p in metadata.get("permissions", []))
            value.update(state="uploaded", download_url="https://drive.google.com/uc?" + urlencode({"export": "download", "id": value["file_id"]}),
                         view_url="https://drive.google.com/file/d/" + value["file_id"] + "/view", server_readable=shared)
            # The resumable URL is sensitive and no longer needed after readback.
            value.pop("session", None); write(receipt, value)
            return {k: value[k] for k in ("file_id", "sha256", "download_url", "view_url", "server_readable")}

    def allow_readonly_link(self, card, expected_file_id):
        """Explicit owner action, only for this verified app-owned final MP4.

        The caller must collect separate exact-file consent. The private parent
        folder and original/reference media are never shared by this method.
        """
        media = self.upload(card)
        if media['file_id'] != expected_file_id: raise DeliveryError('DRIVE_MEDIA_IDENTITY_MISMATCH')
        from .story_workspace import story_video
        source = Path(story_video(self.service, card['artifact_job_id'])['path'])
        receipt = self.receipt(card['artifact']['sha256'])
        with lock(self.home / 'upload.lock'):
            value = json.loads(receipt.read_text())
            metadata = self.metadata(expected_file_id)
            self.check(metadata, card, value['folder_id'], source)
            if not any(p.get('type') == 'anyone' for p in metadata['permissions']):
                code, _, _ = self.api('POST', '/drive/v3/files/' + expected_file_id + '/permissions?fields=id',
                                       data={'type': 'anyone', 'role': 'reader', 'allowFileDiscovery': False})
                if code not in (200, 201): raise DeliveryError('DRIVE_LINK_PERMISSION_UNCONFIRMED')
            metadata = self.metadata(expected_file_id)
            self.check(metadata, card, value['folder_id'], source)
            if not any(p.get('type') == 'anyone' and p.get('role') == 'reader' and p.get('allowFileDiscovery') is False for p in metadata['permissions']):
                raise DeliveryError('DRIVE_LINK_PERMISSION_UNCONFIRMED')
            value['server_readable'] = True; write(receipt, value)
            return {k: value[k] for k in ('file_id', 'sha256', 'download_url', 'view_url', 'server_readable')}
