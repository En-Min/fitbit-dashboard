"""
LibreLinkUp integration service for syncing CGM glucose data.

LibreLinkUp is Abbott's cloud service for FreeStyle Libre CGM systems that allows
caregivers/followers to monitor glucose readings in real-time.

API Reference:
- Base URLs: https://api-us.libreview.io (US), https://api-eu.libreview.io (EU)
- Login: POST /llu/auth/login
- Connections: GET /llu/connections
- Graph data: GET /llu/connections/{patientId}/graph
"""

import httpx
from datetime import datetime
from typing import List, Dict, Optional


# Default to US region, can be configured
LIBRE_API_US = "https://api-us.libreview.io"
LIBRE_API_EU = "https://api-eu.libreview.io"

# LibreView API requires specific headers
DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Product": "llu.android",
    "Version": "4.7.0",
}


class LibreLinkUpError(Exception):
    """Exception raised for LibreLinkUp API errors."""
    pass


class LibreLinkUpClient:
    """
    Client for interacting with the LibreLinkUp API.

    Usage:
        client = LibreLinkUpClient("email@example.com", "password")
        await client.login()
        connections = await client.get_connections()
        readings = await client.get_readings(connections[0]["patientId"])
    """

    def __init__(self, email: str, password: str, region: str = "us"):
        """
        Initialize the LibreLinkUp client.

        Args:
            email: LibreView account email
            password: LibreView account password
            region: API region - "us" or "eu"
        """
        self.email = email
        self.password = password
        self.token: Optional[str] = None
        self.patient_id: Optional[str] = None

        # Select API base URL based on region
        if region.lower() == "eu":
            self.api_base = LIBRE_API_EU
        else:
            self.api_base = LIBRE_API_US

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers, including auth token if available."""
        headers = DEFAULT_HEADERS.copy()
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def login(self) -> bool:
        """
        Authenticate with LibreView API.

        Returns:
            True if login successful, False otherwise

        Raises:
            LibreLinkUpError: If there's an API error other than auth failure
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self.api_base}/llu/auth/login",
                    json={"email": self.email, "password": self.password},
                    headers=DEFAULT_HEADERS
                )

                if response.status_code == 200:
                    data = response.json()

                    # Check for redirect to different region
                    if data.get("status") == 2:
                        # Region redirect - extract new region from response
                        redirect_data = data.get("data", {})
                        new_region = redirect_data.get("region")
                        if new_region == "EU":
                            self.api_base = LIBRE_API_EU
                            return await self.login()  # Retry with EU

                    # Extract auth token
                    auth_ticket = data.get("data", {}).get("authTicket", {})
                    self.token = auth_ticket.get("token")

                    if self.token:
                        return True

                elif response.status_code == 401:
                    return False
                else:
                    raise LibreLinkUpError(
                        f"Unexpected response status: {response.status_code}"
                    )

            except httpx.RequestError as e:
                raise LibreLinkUpError(f"Network error during login: {str(e)}")

        return False

    async def get_connections(self) -> List[Dict]:
        """
        Get list of connected patients/users.

        Returns:
            List of connection dictionaries with patientId, firstName, lastName, etc.

        Raises:
            LibreLinkUpError: If not authenticated or API error
        """
        if not self.token:
            if not await self.login():
                raise LibreLinkUpError("Failed to authenticate")

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.api_base}/llu/connections",
                    headers=self._get_headers()
                )

                if response.status_code == 200:
                    data = response.json()
                    connections = data.get("data", [])
                    return connections
                elif response.status_code == 401:
                    # Token expired, try to re-authenticate
                    self.token = None
                    if await self.login():
                        return await self.get_connections()
                    raise LibreLinkUpError("Authentication expired")
                else:
                    raise LibreLinkUpError(
                        f"Failed to get connections: {response.status_code}"
                    )

            except httpx.RequestError as e:
                raise LibreLinkUpError(f"Network error: {str(e)}")

        return []

    async def get_readings(self, patient_id: str) -> List[Dict]:
        """
        Fetch glucose readings for a specific patient.

        Args:
            patient_id: The patient ID from get_connections()

        Returns:
            List of glucose reading dictionaries with timestamp, value, and source

        Raises:
            LibreLinkUpError: If not authenticated or API error
        """
        if not self.token:
            if not await self.login():
                raise LibreLinkUpError("Failed to authenticate")

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.api_base}/llu/connections/{patient_id}/graph",
                    headers=self._get_headers()
                )

                if response.status_code == 200:
                    data = response.json()
                    graph_data = data.get("data", {}).get("graphData", [])

                    readings = []
                    for r in graph_data:
                        try:
                            # Parse timestamp - LibreView uses ISO format with Z suffix
                            timestamp_str = r.get("Timestamp", r.get("timestamp", ""))
                            if timestamp_str:
                                # Handle various timestamp formats
                                if timestamp_str.endswith("Z"):
                                    timestamp = datetime.fromisoformat(
                                        timestamp_str.replace("Z", "+00:00")
                                    )
                                else:
                                    timestamp = datetime.fromisoformat(timestamp_str)

                                # Convert to naive datetime (local time)
                                if timestamp.tzinfo:
                                    timestamp = timestamp.replace(tzinfo=None)

                                value = r.get("Value", r.get("value"))
                                if value is not None:
                                    readings.append({
                                        "timestamp": timestamp,
                                        "value": int(value),
                                        "source": "librelinkup"
                                    })
                        except (ValueError, KeyError) as e:
                            # Skip malformed readings
                            continue

                    return readings

                elif response.status_code == 401:
                    self.token = None
                    if await self.login():
                        return await self.get_readings(patient_id)
                    raise LibreLinkUpError("Authentication expired")
                else:
                    raise LibreLinkUpError(
                        f"Failed to get readings: {response.status_code}"
                    )

            except httpx.RequestError as e:
                raise LibreLinkUpError(f"Network error: {str(e)}")

        return []

    async def get_current_reading(self, patient_id: str) -> Optional[Dict]:
        """
        Get the most recent glucose reading for a patient.

        Args:
            patient_id: The patient ID from get_connections()

        Returns:
            Most recent reading dict or None if no readings available
        """
        if not self.token:
            if not await self.login():
                raise LibreLinkUpError("Failed to authenticate")

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.api_base}/llu/connections/{patient_id}/graph",
                    headers=self._get_headers()
                )

                if response.status_code == 200:
                    data = response.json()
                    connection_data = data.get("data", {}).get("connection", {})
                    glucose_item = connection_data.get("glucoseItem", {})

                    if glucose_item:
                        timestamp_str = glucose_item.get("Timestamp", "")
                        value = glucose_item.get("Value")

                        if timestamp_str and value is not None:
                            if timestamp_str.endswith("Z"):
                                timestamp = datetime.fromisoformat(
                                    timestamp_str.replace("Z", "+00:00")
                                )
                            else:
                                timestamp = datetime.fromisoformat(timestamp_str)

                            if timestamp.tzinfo:
                                timestamp = timestamp.replace(tzinfo=None)

                            return {
                                "timestamp": timestamp,
                                "value": int(value),
                                "source": "librelinkup",
                                "trend_arrow": glucose_item.get("TrendArrow"),
                            }

            except (httpx.RequestError, ValueError, KeyError):
                pass

        return None
