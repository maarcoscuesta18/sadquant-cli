from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

import httpx

from sadquant.env import load_dotenv


class OptionalProvider:
    name: str
    env_var: str

    def available(self) -> bool:
        load_dotenv()
        return bool(os.getenv(self.env_var))


class FmpProviderError(RuntimeError):
    pass


class FmpProvider(OptionalProvider):
    name = "fmp"
    env_var = "FMP_API_KEY"
    default_base_url = "https://financialmodelingprep.com/stable"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        cache_dir: Optional[Path] = None,
    ) -> None:
        load_dotenv()
        self.api_key = api_key or os.getenv(self.env_var)
        self.base_url = (base_url or os.getenv("FMP_BASE_URL") or self.default_base_url).rstrip("/")
        self.cache_dir = cache_dir or _default_cache_dir() / "fmp"

    def available(self) -> bool:
        return bool(self.api_key)

    def get(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
        cache_ttl: Optional[int] = None,
    ) -> Any:
        if not self.api_key:
            raise FmpProviderError("FMP_API_KEY is not set.")

        params = {key: value for key, value in (params or {}).items() if value is not None}
        cache_file = self._cache_file(path, params) if cache_ttl else None
        if cache_file is not None:
            cached = self._read_cache(cache_file, cache_ttl)
            if cached is not None:
                return cached

        url = f"{self.base_url}/{path.lstrip('/')}"
        request_params = {**params, "apikey": self.api_key}
        try:
            with httpx.Client(timeout=20) as client:
                response = client.get(url, params=request_params)
        except httpx.TimeoutException as exc:
            raise FmpProviderError("FMP request timed out.") from exc
        except httpx.HTTPError as exc:
            raise FmpProviderError(f"FMP request failed: {exc}") from exc

        if response.status_code == 403:
            raise FmpProviderError("FMP API rejected the request with 403. Check FMP_API_KEY and plan access.")
        if response.status_code == 429:
            raise FmpProviderError("FMP API rate limit exceeded with 429. Slow down or reduce FMP tool usage.")
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise FmpProviderError(f"FMP request failed with HTTP {response.status_code}.") from exc

        data = response.json()
        if cache_file is not None:
            self._write_cache(cache_file, data)
        return data

    def _cache_file(self, path: str, params: dict[str, Any]) -> Path:
        payload = json.dumps(
            {"base_url": self.base_url, "path": path.lstrip("/"), "params": params},
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def _read_cache(self, cache_file: Path, ttl: int) -> Optional[Any]:
        if not cache_file.exists():
            return None
        try:
            payload = json.loads(cache_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        cached_at = float(payload.get("cached_at", 0))
        if time.time() - cached_at > ttl:
            return None
        return payload.get("data")

    def _write_cache(self, cache_file: Path, data: Any) -> None:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {"cached_at": time.time(), "data": data}
        cache_file.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")


class FundaProvider(OptionalProvider):
    name = "funda"
    env_var = "FUNDA_API_KEY"
    base_url = "https://api.funda.ai/v1"

    def get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        key = os.getenv(self.env_var)
        if not key:
            raise RuntimeError("FUNDA_API_KEY is not set.")
        with httpx.Client(timeout=20) as client:
            response = client.get(
                f"{self.base_url}/{path.lstrip('/')}",
                params=params,
                headers={"Authorization": f"Bearer {key}"},
            )
            response.raise_for_status()
            return response.json()


class AdanosProvider(OptionalProvider):
    name = "adanos"
    env_var = "ADANOS_API_KEY"
    base_url = "https://api.adanos.org"

    def sentiment_compare(self, source: str, tickers: list[str], days: int = 7) -> dict[str, Any]:
        key = os.getenv(self.env_var)
        if not key:
            raise RuntimeError("ADANOS_API_KEY is not set.")
        with httpx.Client(timeout=20) as client:
            response = client.get(
                f"{self.base_url}/{source}/stocks/v1/compare",
                params={"tickers": ",".join(tickers), "days": days},
                headers={"X-API-Key": key},
            )
            response.raise_for_status()
            return response.json()


def _default_cache_dir() -> Path:
    try:
        from platformdirs import user_cache_dir

        return Path(user_cache_dir("sadquant", "sadquant"))
    except ModuleNotFoundError:
        base = Path(os.getenv("LOCALAPPDATA", Path.home() / ".cache"))
        return base / "sadquant"
