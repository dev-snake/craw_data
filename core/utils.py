import os
import json
import datetime
from urllib.parse import urljoin, urlparse


# =====================================
# Ensure output folder exists
# =====================================
def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


# =====================================
# Load settings JSON
# =====================================
def load_settings(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Config file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


# =====================================
# Save settings JSON
# =====================================
def save_settings(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# =====================================
# Normalize URL
# =====================================
def normalize_url(base, link):
    """
    Convert relative URL to absolute URL.
    Example:
        base = https://example.com/page
        link = /about
        -> https://example.com/about
    """
    if not link:
        return None

    try:
        return urljoin(base, link)
    except Exception:
        return None


# =====================================
# Check if URL is allowed extension
# =====================================
def is_allowed_extension(url, banned_extensions):
    """
    Skip non-HTML resources such as images, pdf, zip...
    """
    url = url.lower()

    for ext in banned_extensions:
        if url.endswith(ext.lower()):
            return False

    return True


# =====================================
# Extract domain from URL
# =====================================
def get_domain(url):
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


# =====================================
# Check if URL is same domain
# =====================================
def same_domain(url1, url2):
    return get_domain(url1) == get_domain(url2)


# =====================================
# Timestamp prefix log
# =====================================
def log_time(text):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    return f"[{timestamp}] {text}"
