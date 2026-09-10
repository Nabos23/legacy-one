import base64
import hashlib
import hmac
import json
import re
import urllib.parse
from datetime import datetime, timezone

import httpx

from ai.connectors.base import BaseConnector


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the AWS credentials lack permission "
                f"for this action (HTTP {e.response.status_code}). "
                "Ask the user to reconnect their AWS S3 connector with valid credentials."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


def _sign_v4(method: str, url: str, headers: dict, payload: str, access_key: str, secret_key: str, region: str, service: str = "s3") -> dict:
    """AWS Signature Version 4."""
    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc
    path = parsed.path or "/"
    query = parsed.query

    signed_headers_keys = sorted(["host", "x-amz-date"] + [k.lower() for k in headers if k.lower() not in ("host", "x-amz-date")])
    all_headers = {k.lower(): v for k, v in headers.items()}
    all_headers["host"] = host
    all_headers["x-amz-date"] = amz_date
    canonical_headers = "".join(f"{k}:{all_headers[k]}\n" for k in signed_headers_keys)
    signed_headers_str = ";".join(signed_headers_keys)

    payload_hash = hashlib.sha256(payload.encode()).hexdigest()
    canonical_request = "\n".join([method, path, query, canonical_headers, signed_headers_str, payload_hash])

    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, credential_scope, hashlib.sha256(canonical_request.encode()).hexdigest()])

    def _sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode(), hashlib.sha256).digest()

    signing_key = _sign(_sign(_sign(_sign(f"AWS4{secret_key}".encode(), date_stamp), region), service), "aws4_request")
    signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()

    auth = f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, SignedHeaders={signed_headers_str}, Signature={signature}"
    result = dict(all_headers)
    result["Authorization"] = auth
    result["x-amz-content-sha256"] = payload_hash
    return result


def _sign_v4_bytes(method: str, url: str, headers: dict, payload_bytes: bytes, access_key: str, secret_key: str, region: str, service: str = "s3") -> dict:
    """AWS Signature Version 4 for binary payloads."""
    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc
    path = parsed.path or "/"
    query = parsed.query

    signed_headers_keys = sorted(["host", "x-amz-date"] + [k.lower() for k in headers if k.lower() not in ("host", "x-amz-date")])
    all_headers = {k.lower(): v for k, v in headers.items()}
    all_headers["host"] = host
    all_headers["x-amz-date"] = amz_date
    canonical_headers = "".join(f"{k}:{all_headers[k]}\n" for k in signed_headers_keys)
    signed_headers_str = ";".join(signed_headers_keys)

    payload_hash = hashlib.sha256(payload_bytes).hexdigest()
    canonical_request = "\n".join([method, path, query, canonical_headers, signed_headers_str, payload_hash])

    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, credential_scope, hashlib.sha256(canonical_request.encode()).hexdigest()])

    def _sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode(), hashlib.sha256).digest()

    signing_key = _sign(_sign(_sign(_sign(f"AWS4{secret_key}".encode(), date_stamp), region), service), "aws4_request")
    signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()

    auth = f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, SignedHeaders={signed_headers_str}, Signature={signature}"
    result = dict(all_headers)
    result["Authorization"] = auth
    result["x-amz-content-sha256"] = payload_hash
    return result


def _presigned_url_v4(method: str, url: str, access_key: str, secret_key: str, region: str, expires_in: int, service: str = "s3") -> str:
    """Generate a presigned URL using AWS Signature Version 4 query-string signing."""
    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc
    path = parsed.path or "/"

    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    credential = f"{access_key}/{credential_scope}"

    query_params = {
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": credential,
        "X-Amz-Date": amz_date,
        "X-Amz-Expires": str(expires_in),
        "X-Amz-SignedHeaders": "host",
    }
    canonical_querystring = "&".join(
        f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}"
        for k, v in sorted(query_params.items())
    )

    canonical_headers = f"host:{host}\n"
    signed_headers = "host"
    payload_hash = "UNSIGNED-PAYLOAD"

    canonical_request = "\n".join([method, path, canonical_querystring, canonical_headers, signed_headers, payload_hash])

    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256",
        amz_date,
        credential_scope,
        hashlib.sha256(canonical_request.encode()).hexdigest(),
    ])

    def _sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode(), hashlib.sha256).digest()

    signing_key = _sign(_sign(_sign(_sign(f"AWS4{secret_key}".encode(), date_stamp), region), service), "aws4_request")
    signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()

    return f"{url}?{canonical_querystring}&X-Amz-Signature={signature}"


def _parse_xml_list(xml: str, tag: str) -> list[str]:
    return re.findall(rf"<{tag}>(.*?)</{tag}>", xml, re.DOTALL)


class AWSS3Connector(BaseConnector):
    """
    AWS S3 connector. access_token stores credentials as "ACCESS_KEY:SECRET_KEY:REGION".
    Falls back to us-east-1 if region not provided.
    """

    PROVIDER_ID = "aws_s3"

    def __init__(self, access_token: str, agent_id: str = None) -> None:
        super().__init__(access_token, agent_id=agent_id)
        parts = access_token.split(":", 2)
        self._access_key = parts[0] if len(parts) > 0 else ""
        self._secret_key = parts[1] if len(parts) > 1 else ""
        self._region = parts[2] if len(parts) > 2 else "us-east-1"

    @property
    def _auth_headers(self) -> dict:
        return {}

    @_auth_headers.setter
    def _auth_headers(self, value: dict) -> None:
        pass

    def _request(self, method: str, url: str, query: str = "", payload: str = "") -> httpx.Response:
        full_url = f"{url}?{query}" if query else url
        headers = _sign_v4(method, full_url, {}, payload, self._access_key, self._secret_key, self._region)
        resp = httpx.request(method, full_url, headers=headers, content=payload.encode(), timeout=15)
        return resp

    def _request_bytes(self, method: str, url: str, query: str = "", payload_bytes: bytes = b"", extra_headers: dict | None = None) -> httpx.Response:
        full_url = f"{url}?{query}" if query else url
        headers = _sign_v4_bytes(method, full_url, extra_headers or {}, payload_bytes, self._access_key, self._secret_key, self._region)
        resp = httpx.request(method, full_url, headers=headers, content=payload_bytes, timeout=30)
        return resp

    def list_buckets(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "s3_list_buckets", inp)
        if permission_error: return permission_error
        try:
            resp = self._request("GET", f"https://s3.amazonaws.com/")
            resp.raise_for_status()
            names = _parse_xml_list(resp.text, "Name")
            creation_dates = _parse_xml_list(resp.text, "CreationDate")
            buckets = [{"name": n, "creationDate": d} for n, d in zip(names, creation_dates)]
            return json.dumps({"buckets": buckets, "count": len(buckets)})
        except Exception as e:
            return _handle_error("s3_list_buckets", e)

    def list_objects(self, inp: dict) -> str:
        permission_error, bucket = self._check(self.agent_id, self.PROVIDER_ID, "s3_list_objects", inp, "bucket")
        if permission_error: return permission_error
        try:
            region = inp.get("region", self._region)
            params: list[str] = [f"list-type=2", f"max-keys={inp.get('limit', 50)}"]
            if inp.get("prefix"):
                params.append(f"prefix={urllib.parse.quote(inp['prefix'])}")
            if inp.get("delimiter", "/"):
                params.append(f"delimiter={urllib.parse.quote(inp.get('delimiter', '/'))}")
            query = "&".join(params)
            resp = self._request("GET", f"https://{bucket}.s3.{region}.amazonaws.com/", query)
            resp.raise_for_status()
            keys = _parse_xml_list(resp.text, "Key")
            sizes = _parse_xml_list(resp.text, "Size")
            last_modified = _parse_xml_list(resp.text, "LastModified")
            prefixes = _parse_xml_list(resp.text, "Prefix")
            objects = [{"key": k, "size": s, "lastModified": m} for k, s, m in zip(keys, sizes, last_modified)]
            return json.dumps({"objects": objects, "commonPrefixes": prefixes, "count": len(objects)})
        except Exception as e:
            return _handle_error("s3_list_objects", e)

    def get_object_metadata(self, inp: dict) -> str:
        permission_error, bucket, key = self._check(self.agent_id, self.PROVIDER_ID, "s3_get_object_metadata", inp, "bucket", "key")
        if permission_error: return permission_error
        try:
            region = inp.get("region", self._region)
            encoded_key = urllib.parse.quote(key, safe="/")
            resp = self._request("HEAD", f"https://{bucket}.s3.{region}.amazonaws.com/{encoded_key}")
            resp.raise_for_status()
            return json.dumps({
                "bucket": bucket,
                "key": key,
                "content_length": resp.headers.get("content-length"),
                "content_type": resp.headers.get("content-type"),
                "last_modified": resp.headers.get("last-modified"),
                "etag": resp.headers.get("etag"),
            })
        except Exception as e:
            return _handle_error("s3_get_object_metadata", e)

    def get_bucket_location(self, inp: dict) -> str:
        permission_error, bucket = self._check(self.agent_id, self.PROVIDER_ID, "s3_get_bucket_location", inp, "bucket")
        if permission_error: return permission_error
        try:
            resp = self._request("GET", f"https://{bucket}.s3.amazonaws.com/", "location=")
            resp.raise_for_status()
            locations = _parse_xml_list(resp.text, "LocationConstraint")
            region = locations[0] if locations else "us-east-1"
            return json.dumps({"bucket": bucket, "region": region or "us-east-1"})
        except Exception as e:
            return _handle_error("s3_get_bucket_location", e)

    def delete_object(self, inp: dict) -> str:
        permission_error, bucket, key = self._check(self.agent_id, self.PROVIDER_ID, "s3_delete_object", inp, "bucket", "key")
        if permission_error: return permission_error
        try:
            region = inp.get("region", self._region)
            encoded_key = urllib.parse.quote(key, safe="/")
            resp = self._request("DELETE", f"https://{bucket}.s3.{region}.amazonaws.com/{encoded_key}")
            resp.raise_for_status()
            return json.dumps({"status": "deleted", "bucket": bucket, "key": key})
        except Exception as e:
            return _handle_error("s3_delete_object", e)

    def put_object(self, inp: dict) -> str:
        permission_error, bucket, key, content = self._check(self.agent_id, self.PROVIDER_ID, "s3_put_object", inp, "bucket", "key", "content")
        if permission_error: return permission_error
        try:
            region = inp.get("region", self._region)
            content_type = inp.get("content_type", "text/plain")
            encoded_key = urllib.parse.quote(key, safe="/")
            payload_bytes = content.encode("utf-8")
            extra_headers = {"content-type": content_type}
            resp = self._request_bytes(
                "PUT",
                f"https://{bucket}.s3.{region}.amazonaws.com/{encoded_key}",
                payload_bytes=payload_bytes,
                extra_headers=extra_headers,
            )
            resp.raise_for_status()
            etag = resp.headers.get("etag", "")
            return json.dumps({"status": "uploaded", "bucket": bucket, "key": key, "etag": etag, "size": len(payload_bytes)})
        except Exception as e:
            return _handle_error("s3_put_object", e)

    def get_object(self, inp: dict) -> str:
        permission_error, bucket, key = self._check(self.agent_id, self.PROVIDER_ID, "s3_get_object", inp, "bucket", "key")
        if permission_error: return permission_error
        try:
            region = inp.get("region", self._region)
            encoded_key = urllib.parse.quote(key, safe="/")
            resp = self._request_bytes(
                "GET",
                f"https://{bucket}.s3.{region}.amazonaws.com/{encoded_key}",
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
                "key": key,
                "content": content,
                "encoding": encoding,
                "content_type": content_type,
                "size": len(resp.content),
            })
        except Exception as e:
            return _handle_error("s3_get_object", e)

    def copy_object(self, inp: dict) -> str:
        permission_error, source_bucket, source_key, dest_bucket, dest_key = self._check(self.agent_id, self.PROVIDER_ID, "s3_copy_object", inp, "source_bucket", "source_key", "dest_bucket", "dest_key")
        if permission_error: return permission_error
        try:
            region = inp.get("region", self._region)
            encoded_dest_key = urllib.parse.quote(dest_key, safe="/")
            copy_source = f"/{source_bucket}/{urllib.parse.quote(source_key, safe='/')}"
            extra_headers = {"x-amz-copy-source": copy_source}
            resp = self._request_bytes(
                "PUT",
                f"https://{dest_bucket}.s3.{region}.amazonaws.com/{encoded_dest_key}",
                extra_headers=extra_headers,
            )
            resp.raise_for_status()
            etag_list = _parse_xml_list(resp.text, "ETag")
            etag = etag_list[0] if etag_list else ""
            return json.dumps({
                "status": "copied",
                "source": f"{source_bucket}/{source_key}",
                "destination": f"{dest_bucket}/{dest_key}",
                "etag": etag,
            })
        except Exception as e:
            return _handle_error("s3_copy_object", e)

    def generate_presigned_url(self, inp: dict) -> str:
        permission_error, bucket, key = self._check(self.agent_id, self.PROVIDER_ID, "s3_generate_presigned_url", inp, "bucket", "key")
        if permission_error: return permission_error
        try:
            region = inp.get("region", self._region)
            expires_in = int(inp.get("expires_in", 3600))
            encoded_key = urllib.parse.quote(key, safe="/")
            object_url = f"https://{bucket}.s3.{region}.amazonaws.com/{encoded_key}"
            presigned = _presigned_url_v4(
                "GET",
                object_url,
                self._access_key,
                self._secret_key,
                region,
                expires_in,
            )
            return json.dumps({"presigned_url": presigned, "expires_in": expires_in, "bucket": bucket, "key": key})
        except Exception as e:
            return _handle_error("s3_generate_presigned_url", e)

    def get_bucket_policy(self, inp: dict) -> str:
        permission_error, bucket = self._check(self.agent_id, self.PROVIDER_ID, "s3_get_bucket_policy", inp, "bucket")
        if permission_error: return permission_error
        try:
            resp = self._request("GET", f"https://{bucket}.s3.amazonaws.com/", "policy=")
            if resp.status_code == 404:
                return json.dumps({"bucket": bucket, "policy": "No policy set"})
            resp.raise_for_status()
            try:
                policy = resp.json()
            except Exception:
                policy = resp.text
            return json.dumps({"bucket": bucket, "policy": policy})
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return json.dumps({"bucket": bucket, "policy": "No policy set"})
            return _handle_error("s3_get_bucket_policy", e)
        except Exception as e:
            return _handle_error("s3_get_bucket_policy", e)

    def get_object_tagging(self, inp: dict) -> str:
        permission_error, bucket, key = self._check(self.agent_id, self.PROVIDER_ID, "s3_get_object_tagging", inp, "bucket", "key")
        if permission_error: return permission_error
        try:
            region = inp.get("region", self._region)
            encoded_key = urllib.parse.quote(key, safe="/")
            resp = self._request("GET", f"https://{bucket}.s3.{region}.amazonaws.com/{encoded_key}", "tagging=")
            resp.raise_for_status()
            keys = _parse_xml_list(resp.text, "Key")
            values = _parse_xml_list(resp.text, "Value")
            tags = [{"key": k, "value": v} for k, v in zip(keys, values)]
            return json.dumps({"bucket": bucket, "key": key, "tags": tags})
        except Exception as e:
            return _handle_error("s3_get_object_tagging", e)

    def put_object_tagging(self, inp: dict) -> str:
        permission_error, bucket, key, tags = self._check(self.agent_id, self.PROVIDER_ID, "s3_put_object_tagging", inp, "bucket", "key", "tags")
        if permission_error: return permission_error
        try:
            region = inp.get("region", self._region)
            encoded_key = urllib.parse.quote(key, safe="/")
            tag_set = "".join(f"<Tag><Key>{k}</Key><Value>{v}</Value></Tag>" for k, v in tags.items())
            body = f'<?xml version="1.0" encoding="UTF-8"?><Tagging><TagSet>{tag_set}</TagSet></Tagging>'
            resp = self._request(
                "PUT",
                f"https://{bucket}.s3.{region}.amazonaws.com/{encoded_key}",
                "tagging=",
                body,
            )
            resp.raise_for_status()
            return json.dumps({"status": "tagged", "bucket": bucket, "key": key, "tags": tags})
        except Exception as e:
            return _handle_error("s3_put_object_tagging", e)

    def list_object_versions(self, inp: dict) -> str:
        permission_error, bucket = self._check(self.agent_id, self.PROVIDER_ID, "s3_list_object_versions", inp, "bucket")
        if permission_error: return permission_error
        try:
            region = inp.get("region", self._region)
            params = ["versions=", f"max-keys={inp.get('limit', 50)}"]
            if inp.get("prefix"):
                params.append(f"prefix={urllib.parse.quote(inp['prefix'])}")
            query = "&".join(params)
            resp = self._request("GET", f"https://{bucket}.s3.{region}.amazonaws.com/", query)
            resp.raise_for_status()
            keys = _parse_xml_list(resp.text, "Key")
            version_ids = _parse_xml_list(resp.text, "VersionId")
            is_latest = _parse_xml_list(resp.text, "IsLatest")
            last_modified = _parse_xml_list(resp.text, "LastModified")
            versions = [
                {"key": k, "versionId": v, "isLatest": il, "lastModified": lm}
                for k, v, il, lm in zip(keys, version_ids, is_latest, last_modified)
            ]
            return json.dumps({"bucket": bucket, "versions": versions, "count": len(versions)})
        except Exception as e:
            return _handle_error("s3_list_object_versions", e)

    def delete_objects(self, inp: dict) -> str:
        permission_error, bucket, keys = self._check(self.agent_id, self.PROVIDER_ID, "s3_delete_objects", inp, "bucket", "keys")
        if permission_error: return permission_error
        try:
            region = inp.get("region", self._region)
            objects_xml = "".join(f"<Object><Key>{k}</Key></Object>" for k in keys)
            body = f'<?xml version="1.0" encoding="UTF-8"?><Delete>{objects_xml}</Delete>'
            body_bytes = body.encode("utf-8")
            content_md5 = base64.b64encode(hashlib.md5(body_bytes).digest()).decode("ascii")
            extra_headers = {"content-md5": content_md5, "content-type": "application/xml"}
            resp = self._request_bytes(
                "POST",
                f"https://{bucket}.s3.{region}.amazonaws.com/",
                "delete=",
                body_bytes,
                extra_headers,
            )
            resp.raise_for_status()
            deleted = _parse_xml_list(resp.text, "Key")
            return json.dumps({"bucket": bucket, "deleted": deleted, "count": len(deleted)})
        except Exception as e:
            return _handle_error("s3_delete_objects", e)

    def get_bucket_versioning(self, inp: dict) -> str:
        permission_error, bucket = self._check(self.agent_id, self.PROVIDER_ID, "s3_get_bucket_versioning", inp, "bucket")
        if permission_error: return permission_error
        try:
            region = inp.get("region", self._region)
            resp = self._request("GET", f"https://{bucket}.s3.{region}.amazonaws.com/", "versioning=")
            resp.raise_for_status()
            status_list = _parse_xml_list(resp.text, "Status")
            status = status_list[0] if status_list else "Disabled"
            return json.dumps({"bucket": bucket, "versioning_status": status})
        except Exception as e:
            return _handle_error("s3_get_bucket_versioning", e)

    def get_object_acl(self, inp: dict) -> str:
        permission_error, bucket, key = self._check(self.agent_id, self.PROVIDER_ID, "s3_get_object_acl", inp, "bucket", "key")
        if permission_error: return permission_error
        try:
            region = inp.get("region", self._region)
            encoded_key = urllib.parse.quote(key, safe="/")
            resp = self._request("GET", f"https://{bucket}.s3.{region}.amazonaws.com/{encoded_key}", "acl=")
            resp.raise_for_status()
            owner_ids = _parse_xml_list(resp.text, "ID")
            display_names = _parse_xml_list(resp.text, "DisplayName")
            permissions = _parse_xml_list(resp.text, "Permission")
            return json.dumps({
                "bucket": bucket,
                "key": key,
                "owner": owner_ids[0] if owner_ids else None,
                "grantees": display_names,
                "permissions": permissions,
            })
        except Exception as e:
            return _handle_error("s3_get_object_acl", e)

    def restore_object(self, inp: dict) -> str:
        permission_error, bucket, key = self._check(self.agent_id, self.PROVIDER_ID, "s3_restore_object", inp, "bucket", "key")
        if permission_error: return permission_error
        try:
            region = inp.get("region", self._region)
            days = int(inp.get("days", 1))
            tier = inp.get("tier", "Standard")
            encoded_key = urllib.parse.quote(key, safe="/")
            body = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                f"<RestoreRequest><Days>{days}</Days>"
                f"<GlacierJobParameters><Tier>{tier}</Tier></GlacierJobParameters></RestoreRequest>"
            )
            resp = self._request(
                "POST",
                f"https://{bucket}.s3.{region}.amazonaws.com/{encoded_key}",
                "restore=",
                body,
            )
            resp.raise_for_status()
            return json.dumps({"status": "restore_initiated", "bucket": bucket, "key": key, "days": days, "tier": tier})
        except Exception as e:
            return _handle_error("s3_restore_object", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "s3_list_buckets",
                    "description": "List all S3 buckets in the AWS account.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "s3_list_objects",
                    "description": "List objects in an S3 bucket.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "bucket": {"type": "string", "description": "S3 bucket name."},
                            "prefix": {"type": "string", "description": "Filter objects by key prefix (like a folder path)."},
                            "delimiter": {"type": "string", "description": "Delimiter for virtual folders (default '/')."},
                            "limit": {"type": "integer", "description": "Max objects to return (default 50)."},
                            "region": {"type": "string", "description": "AWS region of the bucket (e.g. us-east-1). Optional if set in credentials."},
                        },
                        "required": ["bucket"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "s3_get_object_metadata",
                    "description": "Get metadata (size, content type, last modified) for an S3 object.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "bucket": {"type": "string", "description": "S3 bucket name."},
                            "key": {"type": "string", "description": "Object key (path)."},
                            "region": {"type": "string", "description": "AWS region of the bucket."},
                        },
                        "required": ["bucket", "key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "s3_get_bucket_location",
                    "description": "Get the AWS region where an S3 bucket is located.",
                    "parameters": {
                        "type": "object",
                        "properties": {"bucket": {"type": "string", "description": "S3 bucket name."}},
                        "required": ["bucket"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "s3_delete_object",
                    "description": "Delete an object from an S3 bucket.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "bucket": {"type": "string", "description": "S3 bucket name."},
                            "key": {"type": "string", "description": "Object key (path) to delete."},
                            "region": {"type": "string", "description": "AWS region of the bucket."},
                        },
                        "required": ["bucket", "key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "s3_put_object",
                    "description": "Upload text or string content to an S3 bucket.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "bucket": {"type": "string", "description": "S3 bucket name."},
                            "key": {"type": "string", "description": "Object key (path) to write, e.g. 'folder/file.txt'."},
                            "content": {"type": "string", "description": "String content to upload."},
                            "content_type": {"type": "string", "description": "MIME type of the content (default 'text/plain')."},
                            "region": {"type": "string", "description": "AWS region of the bucket."},
                        },
                        "required": ["bucket", "key", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "s3_get_object",
                    "description": "Download the content of an S3 object. Returns UTF-8 text or base64-encoded string for binary files.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "bucket": {"type": "string", "description": "S3 bucket name."},
                            "key": {"type": "string", "description": "Object key (path) to download."},
                            "region": {"type": "string", "description": "AWS region of the bucket."},
                        },
                        "required": ["bucket", "key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "s3_copy_object",
                    "description": "Copy an S3 object within the same bucket or to a different bucket.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source_bucket": {"type": "string", "description": "Source S3 bucket name."},
                            "source_key": {"type": "string", "description": "Source object key (path)."},
                            "dest_bucket": {"type": "string", "description": "Destination S3 bucket name."},
                            "dest_key": {"type": "string", "description": "Destination object key (path)."},
                            "region": {"type": "string", "description": "AWS region (used for the destination bucket endpoint)."},
                        },
                        "required": ["source_bucket", "source_key", "dest_bucket", "dest_key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "s3_generate_presigned_url",
                    "description": "Generate a presigned GET URL for an S3 object, allowing temporary public access without AWS credentials.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "bucket": {"type": "string", "description": "S3 bucket name."},
                            "key": {"type": "string", "description": "Object key (path)."},
                            "expires_in": {"type": "integer", "description": "URL expiry time in seconds (default 3600 = 1 hour)."},
                            "region": {"type": "string", "description": "AWS region of the bucket."},
                        },
                        "required": ["bucket", "key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "s3_get_bucket_policy",
                    "description": "Get the bucket policy for an S3 bucket. Returns the policy JSON or 'No policy set' if none exists.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "bucket": {"type": "string", "description": "S3 bucket name."},
                        },
                        "required": ["bucket"],
                    },
                },
            },
        ]
        callables = {
            "s3_list_buckets": self.list_buckets,
            "s3_list_objects": self.list_objects,
            "s3_get_object_metadata": self.get_object_metadata,
            "s3_get_bucket_location": self.get_bucket_location,
            "s3_delete_object": self.delete_object,
            "s3_put_object": self.put_object,
            "s3_get_object": self.get_object,
            "s3_copy_object": self.copy_object,
            "s3_generate_presigned_url": self.generate_presigned_url,
            "s3_get_bucket_policy": self.get_bucket_policy,
        }
        return tools, callables
