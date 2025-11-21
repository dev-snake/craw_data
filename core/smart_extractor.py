"""
Smart Auto-Extractor Module
Tự động trích xuất dữ liệu thông minh từ bất kỳ trang web nào
Không cần config thủ công
"""

from typing import Dict, List, Optional
from bs4 import BeautifulSoup, Tag
import re
from urllib.parse import urljoin

from .smart_detector import SmartDetector


class SmartExtractor:
    """
    Smart data extractor:
    - Tự động phát hiện data structure
    - Extract data theo patterns detected
    - Handle edge cases
    - Clean và normalize data
    """

    def __init__(self, detector: Optional[SmartDetector] = None):
        self.detector = detector or SmartDetector()
        
        # Cache detected patterns để không phải re-detect mỗi page
        self.pattern_cache = {}

    # ===================================================================
    # MAIN: Extract data từ HTML (auto mode)
    # ===================================================================
    def extract_auto(self, html: str, url: str, use_cache: bool = True) -> List[Dict]:
        """
        Auto extract data từ HTML
        
        Args:
            html: HTML content
            url: Base URL (để resolve relative links)
            use_cache: Sử dụng cached patterns (nhanh hơn)
        
        Returns:
            List of extracted items
        """
        # 1. Get hoặc detect patterns
        domain = self._get_domain(url)
        
        if use_cache and domain in self.pattern_cache:
            patterns = self.pattern_cache[domain]
        else:
            # Auto-detect patterns
            patterns = self.detector.analyze_page(html, url)
            self.pattern_cache[domain] = patterns
        
        # 2. Extract data dựa trên patterns
        items = self._extract_with_patterns(html, url, patterns)
        
        # 3. Clean và normalize data
        items = self._clean_items(items)
        
        return items

    # ===================================================================
    # Extract với patterns đã detect
    # ===================================================================
    def _extract_with_patterns(self, html: str, url: str, patterns: Dict) -> List[Dict]:
        """
        Extract data dựa trên detected patterns
        """
        soup = BeautifulSoup(html, "lxml")
        items = []

        # Get best container pattern
        containers = patterns.get("data_containers", [])
        if not containers:
            return []

        best_container = containers[0]  # Highest score
        selector = best_container["selector"]

        # Find all elements matching container selector
        elements = soup.select(selector)

        # Extract data from each element
        for el in elements:
            item = self._extract_item(
                el,
                url,
                patterns.get("content_structure", {}),
                container_selector=selector,
                container_signature=best_container.get("signature"),
            )
            if item and self._is_valid_item(item):
                items.append(item)

        return items

    def _extract_item(
        self,
        el: Tag,
        base_url: str,
        structure: Dict,
        container_selector: str = "",
        container_signature: str = "",
    ) -> Dict:
        """
        Extract single item từ container element
        """
        item = {}

        # Extract fields theo structure (nếu có)
        if structure:
            # Title
            if structure.get("title"):
                title_elem = el.select_one(structure["title"])
                if title_elem:
                    item["title"] = title_elem.get_text(strip=True)
            
            # Link
            if structure.get("link"):
                link_elem = el.select_one(structure["link"])
                if link_elem:
                    href = link_elem.get("href")
                    if href:
                        item["link"] = urljoin(base_url, href)
            
            # Image
            if structure.get("image"):
                img_elem = el.select_one(structure["image"])
                if img_elem:
                    src = img_elem.get("src") or img_elem.get("data-src")
                    if src:
                        item["image"] = urljoin(base_url, src)
            
            # Price
            if structure.get("price"):
                price_elem = el.select_one(structure["price"])
                if price_elem:
                    item["price"] = price_elem.get_text(strip=True)

        # Fallback: Extract bằng heuristics nếu structure không có
        if not item.get("title"):
            item["title"] = self._extract_title_heuristic(el)
        
        if not item.get("link"):
            item["link"] = self._extract_link_heuristic(el, base_url)
        
        if not item.get("image"):
            item["image"] = self._extract_image_heuristic(el, base_url)
        
        if not item.get("price"):
            item["price"] = self._extract_price_heuristic(el)

        # Extract description if available
        item["description"] = self._extract_description_heuristic(el)

        # Dynamic field inference (generate keys from DOM hints)
        dynamic_fields = self._extract_dynamic_fields(el, base_url)
        for k, v in dynamic_fields.items():
            if k not in item:
                item[k] = v

        # Attach metadata (selector + signature) without fixing user-visible keys
        meta = {}
        if container_selector:
            meta["selector"] = container_selector
        if container_signature:
            meta["signature"] = container_signature
        if meta:
            item["_meta"] = meta

        return item

    # ===================================================================
    # Heuristic extractors (fallback methods)
    # ===================================================================
    def _extract_title_heuristic(self, el: Tag) -> Optional[str]:
        """Extract title using heuristics"""
        # Try headings
        for heading in el.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            text = heading.get_text(strip=True)
            if text and len(text) > 3:
                return text
        
        # Try elements with title-related classes/ids
        for elem in el.find_all(True):
            attrs = " ".join([*elem.get("class", []), elem.get("id", "")]).lower()
            if any(kw in attrs for kw in ["title", "name", "heading", "product-name", "item-name"]):
                text = elem.get_text(strip=True)
                if text and len(text) > 3:
                    return text
        
        # Try title attribute
        if el.get("title"):
            return el.get("title").strip()
        
        # Try alt attribute of first image
        img = el.find("img")
        if img and img.get("alt"):
            return img.get("alt").strip()
        
        return None

    def _extract_link_heuristic(self, el: Tag, base_url: str) -> Optional[str]:
        """Extract link using heuristics"""
        # Try first <a> tag with href
        a = el.find("a", href=True)
        if a:
            return urljoin(base_url, a.get("href"))
        
        # Try data attributes
        for attr in ["data-url", "data-href", "data-link"]:
            if el.get(attr):
                return urljoin(base_url, el.get(attr))
        
        # Try onclick attribute
        onclick = el.get("onclick", "")
        if "location.href" in onclick or "window.open" in onclick:
            match = re.search(r'["\']([^"\']+)["\']', onclick)
            if match:
                return urljoin(base_url, match.group(1))
        
        return None

    def _extract_image_heuristic(self, el: Tag, base_url: str) -> Optional[str]:
        """Extract image using heuristics"""
        # Try <img> tag
        img = el.find("img")
        if img:
            # Try various attributes (lazy loading, etc)
            for attr in ["src", "data-src", "data-lazy", "data-original", "data-srcset"]:
                src = img.get(attr)
                if src:
                    # Handle srcset (take first URL)
                    if " " in src:
                        src = src.split()[0]
                    return urljoin(base_url, src)
        
        # Try background-image in style
        for elem in el.find_all(True):
            style = elem.get("style", "")
            match = re.search(r'url\([\'"]?([^\'"]+)[\'"]?\)', style)
            if match:
                return urljoin(base_url, match.group(1))
        
        # Try picture > source
        source = el.find("source")
        if source and source.get("srcset"):
            srcset = source.get("srcset")
            if " " in srcset:
                srcset = srcset.split()[0]
            return urljoin(base_url, srcset)
        
        return None

    def _extract_price_heuristic(self, el: Tag) -> Optional[str]:
        """Extract price using heuristics"""
        # Price pattern (multi-currency support)
        price_pattern = re.compile(
            r'(\$|€|£|₫|¥|₹|元|원|฿|₱|Rp|RM|৳)\s?[\d.,]+\s?[KMB]?|'
            r'[\d.,]+\s?(usd|eur|gbp|vnd|đ|₫|yuan|won|baht|peso|rupiah|ringgit|taka|dollar|euro|pound)',
            re.IGNORECASE
        )
        
        # Try elements with price-related classes/ids
        for elem in el.find_all(True):
            attrs = " ".join([*elem.get("class", []), elem.get("id", "")]).lower()
            if any(kw in attrs for kw in ["price", "cost", "amount", "gia", "valor", "precio"]):
                text = elem.get_text(strip=True)
                if price_pattern.search(text):
                    return text
        
        # Try data-price attribute
        if el.get("data-price"):
            return el.get("data-price").strip()
        
        # Try all text content
        text = el.get_text()
        match = price_pattern.search(text)
        if match:
            return match.group(0).strip()
        
        return None

    def _extract_description_heuristic(self, el: Tag) -> Optional[str]:
        """Extract description using heuristics"""
        # Try elements with desc-related classes/ids
        for elem in el.find_all(True):
            attrs = " ".join([*elem.get("class", []), elem.get("id", "")]).lower()
            if any(kw in attrs for kw in ["desc", "description", "summary", "excerpt", "content", "text", "detail"]):
                text = elem.get_text(strip=True)
                if text and 20 < len(text) < 500:
                    return text
        
        # Try <p> tags
        for p in el.find_all("p"):
            text = p.get_text(strip=True)
            if text and 20 < len(text) < 500:
                return text
        
        # Try meta description in child
        meta = el.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            return meta.get("content").strip()

        return None

    def _extract_dynamic_fields(self, el: Tag, base_url: str) -> Dict:
        """
        Infer additional fields dynamically from DOM hints (class/id/aria/data-*).
        Keys are generated from semantic hints instead of fixed names.
        """
        fields = {}
        max_depth = 2  # Limit search depth inside container

        for node in el.find_all(True):
            if self._depth_from(node, el) > max_depth:
                continue

            key = self._infer_field_key(node)
            if not key:
                continue
            if key in {"title", "link", "image", "price", "description"}:
                continue
            if key in fields:
                continue

            value = self._extract_node_value(node, base_url)
            if value:
                fields[key] = value

        return fields

    def _infer_field_key(self, node: Tag) -> Optional[str]:
        """
        Guess field name from class/id/data/aria.
        Returns a snake_case key.
        """
        def normalize(token: str) -> str:
            token = token.lower()
            token = re.sub(r"[^a-z0-9]+", "_", token)
            return token.strip("_")

        raw_tokens = []
        for attr in (
            "class",
            "id",
            "itemprop",
            "aria-label",
            "data-name",
            "data-field",
            "data-type",
            "data-category",
            "data-meta",
        ):
            val = node.get(attr)
            if not val:
                continue
            if isinstance(val, list):
                raw_tokens.extend(val)
            else:
                raw_tokens.extend(str(val).split())

        tokens = [normalize(t) for t in raw_tokens if normalize(t)]

        synonyms = {
            "author": "author",
            "byline": "author",
            "writer": "author",
            "posted_by": "author",
            "time": "time",
            "date": "date",
            "datetime": "date",
            "published": "date",
            "updated": "updated",
            "category": "category",
            "cat": "category",
            "section": "category",
            "tag": "tag",
            "tags": "tag",
            "label": "label",
            "badge": "badge",
            "subtitle": "subtitle",
            "summary": "summary",
            "excerpt": "summary",
            "rating": "rating",
            "reviews": "reviews",
            "comment": "comments",
            "comments": "comments",
            "meta": "meta",
        }

        for tok in tokens:
            if tok in synonyms:
                return synonyms[tok]
            if tok.startswith(("author_", "date_", "time_", "category_", "tag_", "label_", "badge_")):
                return tok.split("_", 1)[0]

        if tokens:
            return tokens[0]

        tag_map = {
            "time": "date",
            "label": "label",
            "small": "meta",
        }
        return tag_map.get(node.name)

    def _extract_node_value(self, node: Tag, base_url: str) -> Optional[str]:
        """Extract text or URL value from a node."""
        if node.name == "img":
            for attr in ["src", "data-src", "data-lazy", "data-original"]:
                val = node.get(attr)
                if val:
                    return urljoin(base_url, val.split()[0])

        if node.name == "a" and node.get("href"):
            href = node.get("href")
            text = node.get_text(strip=True)
            return urljoin(base_url, href) if not text or len(text) < 3 else text

        if node.name == "time":
            if node.get("datetime"):
                return node.get("datetime")

        if node.name == "meta" and node.get("content"):
            return node.get("content").strip()

        text = node.get_text(strip=True)
        return text if text else None

    def _depth_from(self, node: Tag, root: Tag) -> int:
        """Compute depth of node relative to root."""
        depth = 0
        cur = node
        while cur and cur is not root:
            cur = cur.parent
            depth += 1
        return depth

    # ===================================================================
    # Data cleaning & validation
    # ===================================================================
    def _clean_items(self, items: List[Dict]) -> List[Dict]:
        """
        Clean và normalize extracted data
        - Remove duplicates
        - Clean text
        - Normalize prices
        - Validate URLs
        """
        cleaned = []
        seen = set()
        
        for item in items:
            # Clean text fields
            for key in ["title", "description", "price"]:
                if item.get(key):
                    item[key] = self._clean_text(item[key])
            
            # Normalize price
            if item.get("price"):
                item["price_normalized"] = self._normalize_price(item["price"])
            
            # Validate URLs
            for key in ["link", "image"]:
                if item.get(key):
                    if not self._is_valid_url(item[key]):
                        item[key] = None
            
            # Deduplicate by title+link
            key = (item.get("title"), item.get("link"))
            if key in seen:
                continue
            seen.add(key)
            
            cleaned.append(item)
        
        return cleaned

    def _clean_text(self, text: str) -> str:
        """Clean text: remove extra whitespace, normalize"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        return text

    def _normalize_price(self, price: str) -> Optional[float]:
        """
        Normalize price to float number
        VD: "$1,234.56" -> 1234.56
        """
        if not price:
            return None
        
        # Remove currency symbols và text
        number_part = re.sub(r'[^\d.,]', '', price)
        
        # Handle different decimal separators
        # US: 1,234.56
        # EU: 1.234,56
        if ',' in number_part and '.' in number_part:
            # Has both, determine which is decimal
            if number_part.rindex(',') > number_part.rindex('.'):
                # EU format: 1.234,56
                number_part = number_part.replace('.', '').replace(',', '.')
            else:
                # US format: 1,234.56
                number_part = number_part.replace(',', '')
        elif ',' in number_part:
            # Only comma - could be thousands or decimal
            if number_part.count(',') > 1:
                # Multiple commas -> thousands separator
                number_part = number_part.replace(',', '')
            else:
                # Single comma - check position
                parts = number_part.split(',')
                if len(parts[-1]) == 2:
                    # Likely decimal: 12,99
                    number_part = number_part.replace(',', '.')
                else:
                    # Likely thousands: 1,234
                    number_part = number_part.replace(',', '')
        
        try:
            return float(number_part)
        except ValueError:
            return None

    def _is_valid_url(self, url: str) -> bool:
        """Validate URL"""
        if not url:
            return False
        
        # Basic URL validation
        if url.startswith(('http://', 'https://', '//')):
            return True
        
        # Relative URL (starts with /)
        if url.startswith('/'):
            return True
        
        return False

    def _is_valid_item(self, item: Dict) -> bool:
        """
        Validate extracted item
        Item must have at least title + (link OR image OR price)
        """
        if not item:
            return False
        
        has_title = bool(item.get("title"))
        has_content = any([
            item.get("link"),
            item.get("image"),
            item.get("price")
        ])
        
        return has_title and has_content

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc or parsed.path

    # ===================================================================
    # Pattern management
    # ===================================================================
    def clear_cache(self):
        """Clear pattern cache"""
        self.pattern_cache.clear()

    def get_patterns(self, domain: str) -> Optional[Dict]:
        """Get cached patterns for domain"""
        return self.pattern_cache.get(domain)

    def set_patterns(self, domain: str, patterns: Dict):
        """Set patterns for domain"""
        self.pattern_cache[domain] = patterns


# ===================================================================
# USAGE EXAMPLE
# ===================================================================
if __name__ == "__main__":
    extractor = SmartExtractor()
    
    # Test HTML
    test_html = """
    <html>
    <body>
        <div class="product-list">
            <div class="product-item">
                <img src="https://example.com/img1.jpg" alt="Product 1" />
                <h3 class="product-title">Amazing Product 1</h3>
                <div class="product-price">$19.99</div>
                <a href="/product/1">View Details</a>
                <p class="product-desc">This is a great product with excellent features.</p>
            </div>
            <div class="product-item">
                <img src="https://example.com/img2.jpg" alt="Product 2" />
                <h3 class="product-title">Awesome Product 2</h3>
                <div class="product-price">$29.99</div>
                <a href="/product/2">View Details</a>
                <p class="product-desc">Another fantastic product you will love.</p>
            </div>
            <div class="product-item">
                <img src="https://example.com/img3.jpg" alt="Product 3" />
                <h3 class="product-title">Super Product 3</h3>
                <div class="product-price">$39.99</div>
                <a href="/product/3">View Details</a>
                <p class="product-desc">The best product in our catalog.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    items = extractor.extract_auto(test_html, "https://example.com/products")
    
    print("=== EXTRACTED ITEMS ===")
    for i, item in enumerate(items, 1):
        print(f"\nItem {i}:")
        print(f"  Title: {item.get('title')}")
        print(f"  Price: {item.get('price')} (normalized: {item.get('price_normalized')})")
        print(f"  Link: {item.get('link')}")
        print(f"  Image: {item.get('image')}")
        print(f"  Description: {item.get('description')[:50]}..." if item.get('description') else "")
