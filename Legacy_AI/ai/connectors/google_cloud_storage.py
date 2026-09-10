import base64
import json
import urllib.parse

import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://storage.googleapis.com/storage/v1"
_UPLOAD_BASE = "https://storage.googleapis.com/upload/storage/v1"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Google account lacks permission "
                f"for this action (HTTP {e.response.status_code}). "
                "Ask the user to reconnect their Google Cloud Storage connector."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class GoogleCloudStorageConnector(BaseConnector):

    PROVIDER_ID = "google-cloud-storage"

    def list_buckets(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "gcs_list_buckets", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/b", headers=self._auth_headers, params={"project": inp.get("project_id", ""), "maxResults": inp.get("limit", 50)}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            buckets = [
                {"id": b["id"], "name": b["name"], "location": b.get("location"), "storageClass": b.get("storageClass"), "timeCreated": b.get("timeCreated")}
                for b in data.get("items", [])
            ]
            return json.dumps({"buckets": buckets, "count": len(buckets)})
        except Exception as e:
            return _handle_error("gcs_list_buckets", e)

    def list_objects(self, inp: dict) -> str:
        permission_error, bucket = self._check(self.agent_id, self.PROVIDER_ID, "gcs_list_objects", inp, "bucket")
        if permission_error: return permission_error
        try:
            params = {"maxResults": inp.get("limit", 50)}
            if inp.get("prefix"):
                params["prefix"] = inp["prefix"]
            if inp.get("delimiter"):
                params["delimiter"] = inp.get("delimiter", "/")
            resp = httpx.get(f"{_BASE}/b/{bucket}/o", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            objects = [
                {"name": o["name"], "size": o.get("size"), "contentType": o.get("contentType"), "updated": o.get("updated")}
                for o in data.get("items", [])
            ]
            prefixes = data.get("prefixes", [])
            return json.dumps({"objects": objects, "prefixes": prefixes, "count": len(objects)})
        except Exception as e:
            return _handle_error("gcs_list_objects", e)

    def get_object_metadata(self, inp: dict) -> str:
        permission_error, bucket, name = self._check(self.agent_id, self.PROVIDER_ID, "gcs_get_object_metadata", inp, "bucket", "name")
        if permission_error: return permission_error
        try:
            encoded_name = name.replace("/", "%2F")
            resp = httpx.get(f"{_BASE}/b/{bucket}/o/{encoded_name}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            o = resp.json()
            return json.dumps({
                "name": o.get("name"),
                "bucket": o.get("bucket"),
                "size": o.get("size"),
                "contentType": o.get("contentType"),
                "updated": o.get("updated"),
                "mediaLink": o.get("mediaLink"),
                "selfLink": o.get("selfLink"),
            })
        except Exception as e:
            return _handle_error("gcs_get_object_metadata", e)

    def get_bucket_info(self, inp: dict) -> str:
        permission_error, bucket = self._check(self.agent_id, self.PROVIDER_ID, "gcs_get_bucket_info", inp, "bucket")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/b/{bucket}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            b = resp.json()
            return json.dumps({
                "name": b.get("name"),
                "location": b.get("location"),
                "storageClass": b.get("storageClass"),
                "timeCreated": b.get("timeCreated"),
                "versioning": b.get("versioning"),
            })
        except Exception as e:
            return _handle_error("gcs_get_bucket_info", e)

    def delete_object(self, inp: dict) -> str:
        permission_error, bucket, name = self._check(self.agent_id, self.PROVIDER_ID, "gcs_delete_object", inp, "bucket", "name")
        if permission_error: return permission_error
        try:
            encoded_name = name.replace("/", "%2F")
            resp = httpx.delete(f"{_BASE}/b/{bucket}/o/{encoded_name}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"status": "deleted", "bucket": bucket, "name": name})
        except Exception as e:
            return _handle_error("gcs_delete_object", e)

    def upload_object(self, inp: dict) -> str:
        permission_error, bucket, object_name, content = self._check(self.agent_id, self.PROVIDER_ID, "gcs_upload_object", inp, "bucket", "object_name", "content")
        if permission_error: return permission_error
        try:
            content_type = inp.get("content_type", "text/plain")
            encoded_name = urllib.parse.quote(object_name, safe="")
            upload_url = f"{_UPLOAD_BASE}/b/{bucket}/o"
            headers = {**self._auth_headers, "Content-Type": content_type}
            payload_bytes = content.encode("utf-8")
            resp = httpx.post(
                upload_url,
                headers=headers,
                params={"uploadType": "media", "name": object_name},
                content=payload_bytes,
                timeout=30,
            )
            resp.raise_for_status()
            o = resp.json()
            return json.dumps({
                "name": o.get("name"),
                "size": o.get("size"),
                "contentType": o.get("contentType"),
                "updated": o.get("updated"),
                "mediaLink": o.get("mediaLink"),
            })
        except Exception as e:
            return _handle_error("gcs_upload_object", e)

    def download_object(self, inp: dict) -> str:
        permission_error, bucket, object_name = self._check(self.agent_id, self.PROVIDER_ID, "gcs_download_object", inp, "bucket", "object_name")
        if permission_error: return permission_error
        try:
            encoded_name = urllib.parse.quote(object_name, safe="")
            resp = httpx.get(
                f"{_BASE}/b/{bucket}/o/{encoded_name}",
                headers=self._auth_headers,
                params={"alt": "media"},
                timeout=30,
            )
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            try:
                content = resp.content.decode("utf-8")
                encoding = "utf-8"
            except UnicodeDecodeError:
                content = base64.b64encode(resp.content).decode("ascii")
                encoding = "base64"
            return json.dumps({
                "bucket": bucket,
                "object_name": object_name,
                "content": content,
                "encoding": encoding,
                "content_type": content_type,
                "size": len(resp.content),
            })
        except Exception as e:
            return _handle_error("gcs_download_object", e)

    def copy_object(self, inp: dict) -> str:
        permission_error, source_bucket, source_object, dest_bucket, dest_object = self._check(self.agent_id, self.PROVIDER_ID, "gcs_copy_object", inp, "source_bucket", "source_object", "dest_bucket", "dest_object")
        if permission_error: return permission_error
        try:
            encoded_source = urllib.parse.quote(source_object, safe="")
            encoded_dest = urllib.parse.quote(dest_object, safe="")
            url = f"{_BASE}/b/{source_bucket}/o/{encoded_source}/copyTo/b/{dest_bucket}/o/{encoded_dest}"
            resp = httpx.post(url, headers=self._auth_headers, json={}, timeout=30)
            resp.raise_for_status()
            o = resp.json()
            return json.dumps({
                "status": "copied",
                "source": f"{source_bucket}/{source_object}",
                "destination": f"{dest_bucket}/{dest_object}",
                "name": o.get("name"),
                "size": o.get("size"),
                "contentType": o.get("contentType"),
            })
        except Exception as e:
            return _handle_error("gcs_copy_object", e)

    def create_bucket(self, inp: dict) -> str:
        permission_error, bucket_name, project_id = self._check(self.agent_id, self.PROVIDER_ID, "gcs_create_bucket", inp, "bucket_name", "project_id")
        if permission_error: return permission_error
        try:
            location = inp.get("location", "US")
            storage_class = inp.get("storage_class", "STANDARD")
            body = {
                "name": bucket_name,
                "location": location,
                "storageClass": storage_class,
            }
            resp = httpx.post(
                f"{_BASE}/b",
                headers=self._auth_headers,
                params={"project": project_id},
                json=body,
                timeout=30,
            )
            resp.raise_for_status()
            b = resp.json()
            return json.dumps({
                "status": "created",
                "name": b.get("name"),
                "location": b.get("location"),
                "storageClass": b.get("storageClass"),
                "timeCreated": b.get("timeCreated"),
            })
        except Exception as e:
            return _handle_error("gcs_create_bucket", e)

    def get_object_acl(self, inp: dict) -> str:
        permission_error, bucket, object_name = self._check(self.agent_id, self.PROVIDER_ID, "gcs_get_object_acl", inp, "bucket", "object_name")
        if permission_error: return permission_error
        try:
            encoded_name = urllib.parse.quote(object_name, safe="")
            resp = httpx.get(
                f"{_BASE}/b/{bucket}/o/{encoded_name}/acl",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            acl_entries = [
                {
                    "entity": entry.get("entity"),
                    "role": entry.get("role"),
                    "email": entry.get("email"),
                }
                for entry in data.get("items", [])
            ]
            return json.dumps({"bucket": bucket, "object_name": object_name, "acl": acl_entries, "count": len(acl_entries)})
        except Exception as e:
            return _handle_error("gcs_get_object_acl", e)

    def compose_objects(self, inp: dict) -> str:
        permission_error, bucket, source_objects, destination_object = self._check(self.agent_id, self.PROVIDER_ID, "gcs_compose_objects", inp, "bucket", "source_objects", "destination_object")
        if permission_error: return permission_error
        try:
            encoded_dest = urllib.parse.quote(destination_object, safe="")
            body = {
                "sourceObjects": [{"name": name} for name in source_objects],
                "destination": {"contentType": inp.get("content_type", "text/plain")},
            }
            resp = httpx.post(
                f"{_BASE}/b/{bucket}/o/{encoded_dest}/compose",
                headers=self._auth_headers,
                json=body,
                timeout=30,
            )
            resp.raise_for_status()
            o = resp.json()
            return json.dumps({
                "status": "composed",
                "bucket": bucket,
                "name": o.get("name"),
                "size": o.get("size"),
                "contentType": o.get("contentType"),
                "sourceCount": len(source_objects),
            })
        except Exception as e:
            return _handle_error("gcs_compose_objects", e)

    def rewrite_object(self, inp: dict) -> str:
        permission_error, source_bucket, source_object, dest_bucket, dest_object = self._check(self.agent_id, self.PROVIDER_ID, "gcs_rewrite_object", inp, "source_bucket", "source_object", "dest_bucket", "dest_object")
        if permission_error: return permission_error
        try:
            encoded_source = urllib.parse.quote(source_object, safe="")
            encoded_dest = urllib.parse.quote(dest_object, safe="")
            body = {}
            if inp.get("storage_class"):
                body["storageClass"] = inp["storage_class"]
            rewrite_token = inp.get("rewrite_token", "")
            params = {}
            if rewrite_token:
                params["rewriteToken"] = rewrite_token
            url = f"{_BASE}/b/{source_bucket}/o/{encoded_source}/rewriteTo/b/{dest_bucket}/o/{encoded_dest}"
            resp = httpx.post(url, headers=self._auth_headers, params=params, json=body, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            result = {
                "done": data.get("done", False),
                "objectsWritten": data.get("objectsCount"),
                "totalBytesRewritten": data.get("totalBytesRewritten"),
                "objectSize": data.get("objectSize"),
                "source": f"{source_bucket}/{source_object}",
                "destination": f"{dest_bucket}/{dest_object}",
            }
            if not data.get("done", False):
                result["rewriteToken"] = data.get("rewriteToken")
                result["note"] = "Rewrite incomplete; call gcs_rewrite_object again with this rewrite_token to continue."
            else:
                resource = data.get("resource", {})
                result["name"] = resource.get("name")
                result["contentType"] = resource.get("contentType")
            return json.dumps(result)
        except Exception as e:
            return _handle_error("gcs_rewrite_object", e)

    def list_object_versions(self, inp: dict) -> str:
        permission_error, bucket = self._check(self.agent_id, self.PROVIDER_ID, "gcs_list_object_versions", inp, "bucket")
        if permission_error: return permission_error
        try:
            params = {"versions": "true", "maxResults": inp.get("limit", 50)}
            if inp.get("prefix"):
                params["prefix"] = inp["prefix"]
            resp = httpx.get(f"{_BASE}/b/{bucket}/o", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            versions = [
                {
                    "name": o["name"],
                    "generation": o.get("generation"),
                    "size": o.get("size"),
                    "timeCreated": o.get("timeCreated"),
                    "updated": o.get("updated"),
                    "timeDeleted": o.get("timeDeleted"),
                }
                for o in data.get("items", [])
            ]
            return json.dumps({"bucket": bucket, "versions": versions, "count": len(versions)})
        except Exception as e:
            return _handle_error("gcs_list_object_versions", e)

    def restore_object_version(self, inp: dict) -> str:
        permission_error, bucket, object_name, generation = self._check(self.agent_id, self.PROVIDER_ID, "gcs_restore_object_version", inp, "bucket", "object_name", "generation")
        if permission_error: return permission_error
        try:
            encoded_name = urllib.parse.quote(object_name, safe="")
            resp = httpx.post(
                f"{_BASE}/b/{bucket}/o/{encoded_name}/restore",
                headers=self._auth_headers,
                params={"generation": generation},
                json={},
                timeout=30,
            )
            resp.raise_for_status()
            o = resp.json()
            return json.dumps({
                "status": "restored",
                "bucket": bucket,
                "name": o.get("name"),
                "generation": o.get("generation"),
                "size": o.get("size"),
                "updated": o.get("updated"),
            })
        except Exception as e:
            return _handle_error("gcs_restore_object_version", e)

    def update_object_metadata(self, inp: dict) -> str:
        permission_error, bucket, object_name = self._check(self.agent_id, self.PROVIDER_ID, "gcs_update_object_metadata", inp, "bucket", "object_name")
        if permission_error: return permission_error
        metadata = inp.get("metadata", {})
        content_type = inp.get("content_type", "")
        if not metadata and not content_type:
            return "Error: at least one of 'metadata' or 'content_type' must be provided."
        try:
            encoded_name = urllib.parse.quote(object_name, safe="")
            body = {}
            if metadata:
                body["metadata"] = metadata
            if content_type:
                body["contentType"] = content_type
            resp = httpx.patch(
                f"{_BASE}/b/{bucket}/o/{encoded_name}",
                headers=self._auth_headers,
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            o = resp.json()
            return json.dumps({
                "status": "updated",
                "bucket": bucket,
                "name": o.get("name"),
                "contentType": o.get("contentType"),
                "metadata": o.get("metadata"),
                "updated": o.get("updated"),
            })
        except Exception as e:
            return _handle_error("gcs_update_object_metadata", e)

    def set_bucket_lifecycle(self, inp: dict) -> str:
        permission_error, bucket, rules = self._check(self.agent_id, self.PROVIDER_ID, "gcs_set_bucket_lifecycle", inp, "bucket", "rules")
        if permission_error: return permission_error
        try:
            body = {"lifecycle": {"rule": rules}}
            resp = httpx.patch(
                f"{_BASE}/b/{bucket}",
                headers=self._auth_headers,
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            b = resp.json()
            return json.dumps({
                "status": "updated",
                "bucket": b.get("name"),
                "lifecycle": b.get("lifecycle"),
            })
        except Exception as e:
            return _handle_error("gcs_set_bucket_lifecycle", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "gcs_list_buckets",
                    "description": "List Google Cloud Storage buckets.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string", "description": "GCP project ID to list buckets for."},
                            "limit": {"type": "integer", "description": "Max buckets to return (default 50)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gcs_list_objects",
                    "description": "List objects in a Google Cloud Storage bucket.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "bucket": {"type": "string", "description": "Bucket name."},
                            "prefix": {"type": "string", "description": "Filter objects by prefix (like a folder path)."},
                            "delimiter": {"type": "string", "description": "Delimiter for virtual folders (default '/')."},
                            "limit": {"type": "integer", "description": "Max objects to return (default 50)."},
                        },
                        "required": ["bucket"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gcs_get_object_metadata",
                    "description": "Get metadata for a specific object in Google Cloud Storage.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "bucket": {"type": "string", "description": "Bucket name."},
                            "name": {"type": "string", "description": "Object name/path."},
                        },
                        "required": ["bucket", "name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gcs_get_bucket_info",
                    "description": "Get configuration and metadata for a GCS bucket.",
                    "parameters": {
                        "type": "object",
                        "properties": {"bucket": {"type": "string", "description": "Bucket name."}},
                        "required": ["bucket"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gcs_delete_object",
                    "description": "Delete an object from a Google Cloud Storage bucket.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "bucket": {"type": "string", "description": "Bucket name."},
                            "name": {"type": "string", "description": "Object name/path to delete."},
                        },
                        "required": ["bucket", "name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gcs_upload_object",
                    "description": "Upload text or string content to a Google Cloud Storage bucket.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "bucket": {"type": "string", "description": "Bucket name."},
                            "object_name": {"type": "string", "description": "Destination object name/path, e.g. 'folder/file.txt'."},
                            "content": {"type": "string", "description": "String content to upload."},
                            "content_type": {"type": "string", "description": "MIME type of the content (default 'text/plain')."},
                        },
                        "required": ["bucket", "object_name", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gcs_download_object",
                    "description": "Download the content of a Google Cloud Storage object. Returns UTF-8 text or base64-encoded string for binary files.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "bucket": {"type": "string", "description": "Bucket name."},
                            "object_name": {"type": "string", "description": "Object name/path to download."},
                        },
                        "required": ["bucket", "object_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gcs_copy_object",
                    "description": "Copy a Google Cloud Storage object within the same bucket or to a different bucket.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source_bucket": {"type": "string", "description": "Source bucket name."},
                            "source_object": {"type": "string", "description": "Source object name/path."},
                            "dest_bucket": {"type": "string", "description": "Destination bucket name."},
                            "dest_object": {"type": "string", "description": "Destination object name/path."},
                        },
                        "required": ["source_bucket", "source_object", "dest_bucket", "dest_object"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gcs_create_bucket",
                    "description": "Create a new Google Cloud Storage bucket.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "bucket_name": {"type": "string", "description": "Name for the new bucket."},
                            "project_id": {"type": "string", "description": "GCP project ID that will own the bucket."},
                            "location": {"type": "string", "description": "Storage location (default 'US'). Examples: 'US', 'EU', 'us-central1'."},
                            "storage_class": {"type": "string", "description": "Storage class (default 'STANDARD'). Options: STANDARD, NEARLINE, COLDLINE, ARCHIVE."},
                        },
                        "required": ["bucket_name", "project_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gcs_get_object_acl",
                    "description": "Get the access control list (ACL) for a Google Cloud Storage object.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "bucket": {"type": "string", "description": "Bucket name."},
                            "object_name": {"type": "string", "description": "Object name/path."},
                        },
                        "required": ["bucket", "object_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gcs_compose_objects",
                    "description": "Concatenate multiple existing objects in the same bucket into a single new object (server-side, no download required).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "bucket": {"type": "string", "description": "Bucket name (source and destination must match)."},
                            "source_objects": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Ordered list of source object names to concatenate (max 32).",
                            },
                            "destination_object": {"type": "string", "description": "Name/path for the resulting composed object."},
                            "content_type": {"type": "string", "description": "MIME type for the composed object (default 'text/plain')."},
                        },
                        "required": ["bucket", "source_objects", "destination_object"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gcs_rewrite_object",
                    "description": "Copy/rewrite an object across buckets, locations, or storage classes. Handles large objects that require multiple requests; pass back the returned rewrite_token to continue an incomplete rewrite.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source_bucket": {"type": "string", "description": "Source bucket name."},
                            "source_object": {"type": "string", "description": "Source object name/path."},
                            "dest_bucket": {"type": "string", "description": "Destination bucket name."},
                            "dest_object": {"type": "string", "description": "Destination object name/path."},
                            "storage_class": {"type": "string", "description": "Optional new storage class for the destination object (e.g. NEARLINE, COLDLINE, ARCHIVE)."},
                            "rewrite_token": {"type": "string", "description": "Token from a prior incomplete gcs_rewrite_object call, used to continue that rewrite."},
                        },
                        "required": ["source_bucket", "source_object", "dest_bucket", "dest_object"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gcs_list_object_versions",
                    "description": "List all generations (versions) of objects in a bucket, including soft-deleted ones, for a versioning-enabled bucket.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "bucket": {"type": "string", "description": "Bucket name."},
                            "prefix": {"type": "string", "description": "Filter objects by prefix."},
                            "limit": {"type": "integer", "description": "Max versions to return (default 50)."},
                        },
                        "required": ["bucket"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gcs_restore_object_version",
                    "description": "Restore a specific noncurrent or soft-deleted object generation, making it the live version again.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "bucket": {"type": "string", "description": "Bucket name."},
                            "object_name": {"type": "string", "description": "Object name/path to restore."},
                            "generation": {"type": "string", "description": "Generation number of the version to restore (from gcs_list_object_versions)."},
                        },
                        "required": ["bucket", "object_name", "generation"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gcs_update_object_metadata",
                    "description": "Patch an object's custom metadata and/or content type without re-uploading its content.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "bucket": {"type": "string", "description": "Bucket name."},
                            "object_name": {"type": "string", "description": "Object name/path to update."},
                            "metadata": {"type": "object", "description": "Custom key/value metadata to set on the object."},
                            "content_type": {"type": "string", "description": "New MIME content type for the object."},
                        },
                        "required": ["bucket", "object_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gcs_set_bucket_lifecycle",
                    "description": "Set object lifecycle management rules on a bucket (e.g. auto-delete or change storage class after N days).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "bucket": {"type": "string", "description": "Bucket name."},
                            "rules": {
                                "type": "array",
                                "items": {"type": "object"},
                                "description": (
                                    "List of lifecycle rule objects, each with 'action' (e.g. {\"type\": \"Delete\"} or "
                                    "{\"type\": \"SetStorageClass\", \"storageClass\": \"NEARLINE\"}) and 'condition' "
                                    "(e.g. {\"age\": 30})."
                                ),
                            },
                        },
                        "required": ["bucket", "rules"],
                    },
                },
            },
        ]
        callables = {
            "gcs_list_buckets": self.list_buckets,
            "gcs_list_objects": self.list_objects,
            "gcs_get_object_metadata": self.get_object_metadata,
            "gcs_get_bucket_info": self.get_bucket_info,
            "gcs_delete_object": self.delete_object,
            "gcs_upload_object": self.upload_object,
            "gcs_download_object": self.download_object,
            "gcs_copy_object": self.copy_object,
            "gcs_create_bucket": self.create_bucket,
            "gcs_get_object_acl": self.get_object_acl,
            "gcs_compose_objects": self.compose_objects,
            "gcs_rewrite_object": self.rewrite_object,
            "gcs_list_object_versions": self.list_object_versions,
            "gcs_restore_object_version": self.restore_object_version,
            "gcs_update_object_metadata": self.update_object_metadata,
            "gcs_set_bucket_lifecycle": self.set_bucket_lifecycle,
        }
        return tools, callables
