"""
Smart Auto-Detector Module
Auto-detect: selectors, pagination, infinite scroll
Không cần user config thủ công
"""

import re
from bs4 import BeautifulSoup, Tag
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse


class SmartDetector:
    """
    Tự động phát hiện:
    - Data containers (sản phẩm, bài viết, items)
    - Pagination patterns (next button, page numbers)
    - Infinite scroll indicators
    - Content structure (title, price, image, link)
    """

    def __init__(self):
        # Ngưỡng tối thiểu để detect pattern
        self.min_repeats = 3
        
        # Inline tags không được coi là container
        self.inline_tags = {
            "a", "span", "b", "strong", "em", "i", "small", "label", 
            "mark", "code", "time", "button", "input", "select", 
            "option", "textarea", "svg", "path", "br", "hr"
        }
        
        # Container tags thường chứa data items
        self.container_tags = {
            "div", "article", "section", "li", "tr", "figure", 
            "card", "item", "product", "post"
        }
        
        # Pagination keywords
        self.pagination_keywords = [
            "next", "tiếp", "sau", "→", "›", "»", 
            "page", "trang", "pag", "pagination",
            "load more", "xem thêm", "see more"
        ]
        
        # Infinite scroll indicators
        self.infinite_scroll_keywords = [
            "infinite", "scroll", "lazy", "load-more", 
            "auto-load", "endless", "continuous"
        ]

    # ===================================================================
    # MAIN: Auto-detect tất cả patterns từ HTML
    # ===================================================================
    def analyze_page(self, html: str, url: str) -> Dict:
        """
        Phân tích trang web và trả về tất cả patterns detected
        
        Returns:
        {
            "data_containers": [{"selector": "...", "count": N, "sample": {...}}],
            "pagination": {"type": "button|links|infinite", "selector": "...", "next_url": "..."},
            "infinite_scroll": {"detected": bool, "trigger": "..."},
            "content_structure": {"title": "...", "price": "...", "image": "...", "link": "..."}
        }
        """
        soup = BeautifulSoup(html, "lxml")
        
        result = {
            "data_containers": [],
            "pagination": None,
            "infinite_scroll": None,
            "content_structure": {}
        }
        
        # 1. Detect data containers
        containers = self._detect_data_containers(soup)
        result["data_containers"] = containers
        
        # 2. Detect pagination
        pagination = self._detect_pagination(soup, url)
        result["pagination"] = pagination
        
        # 3. Detect infinite scroll
        infinite_scroll = self._detect_infinite_scroll(soup, html)
        result["infinite_scroll"] = infinite_scroll
        
        # 4. Analyze content structure from best container
        if containers:
            best_container = containers[0]  # Container với nhiều items nhất
            sample_elements = soup.select(best_container["selector"])[:5]
            structure = self._analyze_content_structure(sample_elements)
            result["content_structure"] = structure
        
        return result

    # ===================================================================
    # DETECT DATA CONTAINERS
    # ===================================================================
    def _detect_data_containers(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Tìm các container patterns lặp lại (sản phẩm, bài viết, items)
        Sử dụng DOM clustering + structure similarity
        """
        # Cluster elements theo structure signature
        clusters = self._cluster_by_structure(soup)
        
        # Filter các cluster có đủ repeats
        valid_clusters = []
        
        for signature, elements in clusters.items():
            if len(elements) < self.min_repeats:
                continue
            
            # Skip inline/leaf elements
            sample = elements[0]
            if not isinstance(sample, Tag):
                continue
            if sample.name in self.inline_tags:
                continue
            if self._is_leaf(sample):
                continue
            
            # Generate selector cho cluster này
            selector = self._generate_selector(sample)
            
            # Extract sample data
            sample_data = self._extract_item_data(sample)
            
            # Score cluster (ưu tiên container có nhiều content fields)
            score = self._score_container(sample_data, len(elements))
            
            valid_clusters.append({
                "selector": selector,
                "count": len(elements),
                "sample": sample_data,
                "score": score,
                "signature": signature
            })
        
        # Sort theo score (cao nhất trước)
        valid_clusters.sort(key=lambda x: x["score"], reverse=True)
        
        return valid_clusters

    def _cluster_by_structure(self, soup: BeautifulSoup) -> Dict[str, List[Tag]]:
        """
        Cluster elements theo DOM structure signature
        """
        clusters = {}
        
        for el in soup.find_all(True):
            if not isinstance(el, Tag):
                continue
            
            sig = self._structure_signature(el)
            clusters.setdefault(sig, []).append(el)
        
        return clusters

    def _structure_signature(self, el: Tag) -> str:
        """
        Tạo signature cho element dựa trên structure
        Format: tag.class|child1:count1-child2:count2
        """
        tag = el.name
        classes = ".".join(sorted(el.get("class", []))) or "_"
        
        # Count direct children
        children = [c.name for c in el.find_all(recursive=False) if isinstance(c, Tag)]
        
        if not children:
            return f"{tag}.{classes}|leaf"
        
        # Count unique child tags
        child_counts = {}
        for child in children:
            child_counts[child] = child_counts.get(child, 0) + 1
        
        child_parts = "-".join([f"{k}:{v}" for k, v in sorted(child_counts.items())])
        
        return f"{tag}.{classes}|{child_parts}"

    def _generate_selector(self, el: Tag) -> str:
        """
        Generate CSS selector cho element
        Ưu tiên: tag + class (đơn giản, stable)
        """
        tag = el.name
        classes = el.get("class", [])
        
        if classes:
            # Lọc bỏ các class động (có số, random string)
            stable_classes = [c for c in classes if not re.search(r'\d{4,}|[a-f0-9]{8}', c)]
            if stable_classes:
                return f"{tag}." + ".".join(stable_classes[:2])  # Max 2 classes
        
        # Fallback: parent > child
        parent = el.parent
        if isinstance(parent, Tag):
            parent_classes = parent.get("class", [])
            if parent_classes:
                return f"{parent.name}.{parent_classes[0]} > {tag}"
        
        return tag

    def _is_leaf(self, el: Tag) -> bool:
        """Check if element is leaf (no child tags)"""
        return not any(isinstance(c, Tag) for c in el.children)

    def _extract_item_data(self, el: Tag) -> Dict:
        """
        Extract data fields từ một item container
        """
        data = {}
        
        # Title
        title = self._extract_title(el)
        if title:
            data["title"] = title
        
        # Link
        link = self._extract_link(el)
        if link:
            data["link"] = link
        
        # Image
        image = self._extract_image(el)
        if image:
            data["image"] = image
        
        # Price
        price = self._extract_price(el)
        if price:
            data["price"] = price
        
        # Description
        desc = self._extract_description(el)
        if desc:
            data["description"] = desc
        
        return data

    def _extract_title(self, el: Tag) -> Optional[str]:
        """Extract title/heading"""
        # Try headings
        for heading in el.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            text = heading.get_text(strip=True)
            if text and len(text) > 5:
                return text
        
        # Try elements with title-related classes/ids
        for elem in el.find_all(True):
            attrs = " ".join([*elem.get("class", []), elem.get("id", "")]).lower()
            if any(kw in attrs for kw in ["title", "name", "heading"]):
                text = elem.get_text(strip=True)
                if text and len(text) > 5:
                    return text
        
        # Try title attribute
        if el.get("title"):
            return el.get("title").strip()
        
        return None

    def _extract_link(self, el: Tag) -> Optional[str]:
        """Extract main link"""
        # Try first <a> tag
        a = el.find("a", href=True)
        if a:
            return a.get("href")
        
        # Try data attributes
        for attr in ["data-url", "data-href", "data-link"]:
            if el.get(attr):
                return el.get(attr)
        
        return None

    def _extract_image(self, el: Tag) -> Optional[str]:
        """Extract image URL"""
        # Try <img> tag
        img = el.find("img")
        if img:
            # Try various attributes
            for attr in ["src", "data-src", "data-lazy", "data-original"]:
                if img.get(attr):
                    return img.get(attr)
        
        # Try background-image in style
        for elem in el.find_all(True):
            style = elem.get("style", "")
            match = re.search(r'url\([\'"]?([^\'"]+)[\'"]?\)', style)
            if match:
                return match.group(1)
        
        return None

    def _extract_price(self, el: Tag) -> Optional[str]:
        """Extract price"""
        price_pattern = re.compile(
            r'(\$|€|£|₫|¥|₹)\s?[\d.,]+|[\d.,]+\s?(usd|eur|gbp|vnd|đ|₫|yuan)',
            re.IGNORECASE
        )
        
        # Try elements with price-related classes
        for elem in el.find_all(True):
            attrs = " ".join([*elem.get("class", []), elem.get("id", "")]).lower()
            if any(kw in attrs for kw in ["price", "cost", "amount", "gia"]):
                text = elem.get_text(strip=True)
                if price_pattern.search(text):
                    return text
        
        # Try all text
        text = el.get_text()
        match = price_pattern.search(text)
        if match:
            return match.group(0)
        
        return None

    def _extract_description(self, el: Tag) -> Optional[str]:
        """Extract description/summary"""
        # Try elements with desc-related classes
        for elem in el.find_all(True):
            attrs = " ".join([*elem.get("class", []), elem.get("id", "")]).lower()
            if any(kw in attrs for kw in ["desc", "summary", "excerpt", "content", "text"]):
                text = elem.get_text(strip=True)
                if text and 20 < len(text) < 500:
                    return text
        
        # Try <p> tags
        for p in el.find_all("p"):
            text = p.get_text(strip=True)
            if text and 20 < len(text) < 500:
                return text
        
        return None

    def _score_container(self, sample_data: Dict, count: int) -> float:
        """
        Score container quality
        Cao hơn = tốt hơn
        """
        score = 0
        
        # Bonus cho số lượng items
        score += min(count, 20) * 10  # Cap at 20 items
        
        # Bonus cho các fields quan trọng
        if sample_data.get("title"):
            score += 100
        if sample_data.get("link"):
            score += 50
        if sample_data.get("price"):
            score += 30
        if sample_data.get("image"):
            score += 20
        if sample_data.get("description"):
            score += 10
        
        return score

    # ===================================================================
    # DETECT PAGINATION
    # ===================================================================
    def _detect_pagination(self, soup: BeautifulSoup, base_url: str) -> Optional[Dict]:
        """
        Detect pagination pattern:
        - Next button
        - Page numbers
        - Load more button
        """
        # 1. Try next button/link
        next_link = self._find_next_button(soup, base_url)
        if next_link:
            return {
                "type": "button",
                "next_url": next_link["url"],
                "selector": next_link["selector"]
            }
        
        # 2. Try page number links
        page_links = self._find_page_numbers(soup, base_url)
        if page_links:
            return {
                "type": "links",
                "pattern": page_links["pattern"],
                "current": page_links["current"],
                "pages": page_links["pages"]
            }
        
        # 3. Try load more button
        load_more = self._find_load_more(soup)
        if load_more:
            return {
                "type": "load_more",
                "selector": load_more["selector"],
                "trigger": "click"
            }
        
        return None

    def _find_next_button(self, soup: BeautifulSoup, base_url: str) -> Optional[Dict]:
        """Tìm nút Next/Tiếp"""
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True).lower()
            attrs = " ".join([*a.get("class", []), a.get("id", ""), a.get("rel", "")]).lower()
            
            # Check text hoặc attributes có pagination keywords
            combined = text + " " + attrs
            if any(kw in combined for kw in self.pagination_keywords):
                href = a.get("href")
                full_url = urljoin(base_url, href)
                
                selector = self._generate_selector(a)
                
                return {
                    "url": full_url,
                    "selector": selector,
                    "text": text
                }
        
        return None

    def _find_page_numbers(self, soup: BeautifulSoup, base_url: str) -> Optional[Dict]:
        """Tìm pattern page numbers (1, 2, 3, ...)"""
        # Tìm các link có text là số
        number_links = []
        
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            if text.isdigit():
                page_num = int(text)
                href = a.get("href")
                full_url = urljoin(base_url, href)
                number_links.append({
                    "page": page_num,
                    "url": full_url,
                    "href": href
                })
        
        if len(number_links) < 2:
            return None
        
        # Sort theo page number
        number_links.sort(key=lambda x: x["page"])
        
        # Detect URL pattern
        hrefs = [link["href"] for link in number_links]
        pattern = self._detect_url_pattern(hrefs)
        
        return {
            "pattern": pattern,
            "current": number_links[0]["page"],
            "pages": [link["page"] for link in number_links]
        }

    def _detect_url_pattern(self, urls: List[str]) -> str:
        """
        Detect pattern trong URLs
        VD: /page/1, /page/2 -> /page/{page}
        """
        if len(urls) < 2:
            return ""
        
        # Compare first two URLs to find difference
        url1, url2 = urls[0], urls[1]
        
        # Find differing parts (likely page numbers)
        pattern = ""
        i = 0
        while i < min(len(url1), len(url2)):
            if url1[i] == url2[i]:
                pattern += url1[i]
            else:
                # Found difference, replace with placeholder
                pattern += "{page}"
                # Skip to end or next common part
                break
            i += 1
        
        return pattern

    def _find_load_more(self, soup: BeautifulSoup) -> Optional[Dict]:
        """Tìm nút Load More"""
        for elem in soup.find_all(["button", "a", "div"]):
            text = elem.get_text(strip=True).lower()
            attrs = " ".join([*elem.get("class", []), elem.get("id", "")]).lower()
            
            combined = text + " " + attrs
            if any(kw in combined for kw in ["load more", "xem thêm", "see more", "load-more"]):
                selector = self._generate_selector(elem)
                return {
                    "selector": selector,
                    "text": text
                }
        
        return None

    # ===================================================================
    # DETECT INFINITE SCROLL
    # ===================================================================
    def _detect_infinite_scroll(self, soup: BeautifulSoup, html: str) -> Optional[Dict]:
        """
        Detect infinite scroll indicators:
        - Script tags có infinite scroll libraries
        - Elements với infinite scroll classes
        - API endpoints trong HTML
        """
        detected = False
        indicators = []
        
        # 1. Check scripts
        for script in soup.find_all("script"):
            script_text = script.get_text().lower()
            if any(kw in script_text for kw in self.infinite_scroll_keywords):
                detected = True
                indicators.append("script")
        
        # 2. Check elements with infinite scroll classes
        for elem in soup.find_all(True):
            attrs = " ".join([*elem.get("class", []), elem.get("id", "")]).lower()
            if any(kw in attrs for kw in self.infinite_scroll_keywords):
                detected = True
                indicators.append(f"element:{elem.name}")
        
        # 3. Check for API endpoints in HTML
        api_pattern = re.compile(r'(/api/.*?load|/ajax/.*?load)', re.IGNORECASE)
        matches = api_pattern.findall(html)
        if matches:
            detected = True
            indicators.extend(matches[:3])  # First 3 matches
        
        if detected:
            return {
                "detected": True,
                "indicators": indicators,
                "trigger": "scroll"
            }
        
        return None

    # ===================================================================
    # ANALYZE CONTENT STRUCTURE
    # ===================================================================
    def _analyze_content_structure(self, elements: List[Tag]) -> Dict:
        """
        Phân tích structure của content từ sample elements
        Trả về selectors cho từng field
        """
        structure = {}
        
        # Aggregate selectors from multiple samples
        title_selectors = []
        link_selectors = []
        image_selectors = []
        price_selectors = []
        
        for el in elements:
            # Title
            title_elem = self._find_title_element(el)
            if title_elem:
                title_selectors.append(self._generate_relative_selector(el, title_elem))
            
            # Link
            link_elem = el.find("a", href=True)
            if link_elem:
                link_selectors.append(self._generate_relative_selector(el, link_elem))
            
            # Image
            img_elem = el.find("img")
            if img_elem:
                image_selectors.append(self._generate_relative_selector(el, img_elem))
            
            # Price
            price_elem = self._find_price_element(el)
            if price_elem:
                price_selectors.append(self._generate_relative_selector(el, price_elem))
        
        # Pick most common selectors
        if title_selectors:
            structure["title"] = self._most_common(title_selectors)
        if link_selectors:
            structure["link"] = self._most_common(link_selectors)
        if image_selectors:
            structure["image"] = self._most_common(image_selectors)
        if price_selectors:
            structure["price"] = self._most_common(price_selectors)
        
        return structure

    def _find_title_element(self, el: Tag) -> Optional[Tag]:
        """Find title element trong container"""
        # Try headings
        for heading in el.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            return heading
        
        # Try elements with title classes
        for elem in el.find_all(True):
            classes = " ".join(elem.get("class", [])).lower()
            if "title" in classes or "name" in classes:
                return elem
        
        return None

    def _find_price_element(self, el: Tag) -> Optional[Tag]:
        """Find price element trong container"""
        price_pattern = re.compile(r'(\$|€|£|₫)\s?[\d.,]+', re.IGNORECASE)
        
        for elem in el.find_all(True):
            # Skip big containers; focus on leaf-ish nodes
            if any(isinstance(c, Tag) for c in elem.find_all(recursive=False)):
                continue

            classes = " ".join(elem.get("class", [])).lower()
            if "price" in classes or "cost" in classes:
                return elem
            
            # Check text content
            text = elem.get_text(strip=True)
            if price_pattern.search(text):
                return elem
        
        return None

    def _generate_relative_selector(self, parent: Tag, child: Tag) -> str:
        """Generate relative selector từ parent đến child"""
        child_classes = child.get("class", [])
        if child_classes:
            return f"{child.name}.{child_classes[0]}"
        return child.name

    def _most_common(self, items: List[str]) -> str:
        """Return most common item in list"""
        if not items:
            return ""
        return max(set(items), key=items.count)


# ===================================================================
# USAGE EXAMPLE
# ===================================================================
if __name__ == "__main__":
    detector = SmartDetector()
    
    # Test HTML
    test_html = """
    <div class="products">
        <div class="product-card">
            <img src="image1.jpg" />
            <h3>Product 1</h3>
            <span class="price">$19.99</span>
            <a href="/product/1">View</a>
        </div>
        <div class="product-card">
            <img src="image2.jpg" />
            <h3>Product 2</h3>
            <span class="price">$29.99</span>
            <a href="/product/2">View</a>
        </div>
        <div class="product-card">
            <img src="image3.jpg" />
            <h3>Product 3</h3>
            <span class="price">$39.99</span>
            <a href="/product/3">View</a>
        </div>
    </div>
    <a href="/page/2" class="next">Next</a>
    """
    
    result = detector.analyze_page(test_html, "https://example.com/page/1")
    
    print("=== DETECTED PATTERNS ===")
    print(f"Containers: {len(result['data_containers'])}")
    if result['data_containers']:
        best = result['data_containers'][0]
        print(f"  Best: {best['selector']} ({best['count']} items)")
        print(f"  Sample: {best['sample']}")
    
    print(f"\nPagination: {result['pagination']}")
    print(f"Infinite Scroll: {result['infinite_scroll']}")
    print(f"Content Structure: {result['content_structure']}")
