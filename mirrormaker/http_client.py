import json
import logging
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, Any, Optional, Tuple, List, Union

logger = logging.getLogger(__name__)

class HttpResponse:
    """A simplified HTTP response object similar to requests.Response."""
    
    def __init__(self, status_code: int, body: bytes, headers: Dict[str, str]) -> None:
        self.status_code = status_code
        self._body = body
        self.headers = headers
        self.text = body.decode('utf-8')
        self.links: Dict[str, Dict[str, str]] = {}
        
        # Parse Link header for pagination if it exists
        if 'Link' in headers:
            for link in headers['Link'].split(','):
                parts = link.strip().split(';')
                if len(parts) >= 2:
                    url = parts[0].strip('<>').strip()
                    rel = parts[1].split('=')[1].strip('"')
                    self.links[rel] = {"url": url}
    
    def json(self) -> Any:
        """Parse response body as JSON."""
        return json.loads(self.text)
    
    def raise_for_status(self) -> None:
        """Raise an exception if status code indicates an error."""
        if self.status_code >= 400:
            raise HttpError(f"HTTP Error {self.status_code}: {self.text}", self)


class HttpError(Exception):
    """Exception raised for HTTP errors."""
    
    def __init__(self, message: str, response: Optional[HttpResponse] = None) -> None:
        self.message = message
        self.response = response
        super().__init__(self.message)


def get(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 30) -> HttpResponse:
    """Send a GET request."""
    return _request('GET', url, headers=headers, timeout=timeout)


def post(url: str, json: Optional[Dict[str, Any]] = None, 
         headers: Optional[Dict[str, str]] = None, timeout: int = 30) -> HttpResponse:
    """Send a POST request with JSON data."""
    return _request('POST', url, json=json, headers=headers, timeout=timeout)


def _request(method: str, url: str, json: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, str]] = None, timeout: int = 30) -> HttpResponse:
    """Send an HTTP request and return the response."""
    if headers is None:
        headers = {}
    
    # Prepare the request
    req = urllib.request.Request(url, method=method)
    
    # Add headers
    for name, value in headers.items():
        req.add_header(name, value)
    
    # Add JSON body if provided
    data = None
    if json is not None:
        data = bytes(json_serialize(json), encoding='utf-8')
        req.add_header('Content-Type', 'application/json')
    
    try:
        # Send the request
        with urllib.request.urlopen(req, data=data, timeout=timeout) as response:
            # Read the response
            body = response.read()
            status_code = response.status
            headers_dict = dict(response.getheaders())
            
            # Create and return the response object
            http_response = HttpResponse(status_code, body, headers_dict)
            return http_response
    
    except urllib.error.HTTPError as e:
        # Handle HTTP errors
        body = e.read()
        headers_dict = dict(e.headers)
        http_response = HttpResponse(e.code, body, headers_dict)
        raise HttpError(f"HTTP Error {e.code}: {body.decode('utf-8')}", http_response)
    
    except urllib.error.URLError as e:
        # Handle connection errors
        raise HttpError(f"Connection error: {str(e)}")
    
    except Exception as e:
        # Handle other errors
        raise HttpError(f"Request error: {str(e)}")


def json_serialize(obj: Any) -> str:
    """Serialize an object to JSON."""
    return json.dumps(obj)
