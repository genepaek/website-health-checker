#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime
from collections import defaultdict

WEBSITES = [
        'https://www.bil-jac.com',
        'https://homeschoolacademy.com'
]

# Extra pages to crawl beyond the homepage (keyed by base URL)
EXTRA_PAGES = {
        'https://www.bil-jac.com': [
                    '/products/30-20-performance-dog-food/',
                    '/products/adult-select-dry-dog-food/',
                    '/products/',
                    '/why-bil-jac/',
        ]
}

# CDN domains to detect and health-check separately
CDN_PATTERNS = {
        'smushcdn.com': 'Smush Image CDN (WPMU Dev)',
        'cloudfront.net': 'Amazon CloudFront',
        'fastly.net': 'Fastly CDN',
        'imgix.net': 'Imgix CDN',
        'cloudflare.com': 'Cloudflare CDN',
}

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; SiteHealthChecker/2.0)'}


def check_url(url, timeout=10):
        """Check if a URL is accessible, return HTTP status code or error string."""
        try:
                    response = requests.head(url, timeout=timeout, allow_redirects=True, headers=HEADERS)
                    return response.status_code
except requests.exceptions.Timeout:
        return 'TIMEOUT'
except requests.exceptions.ConnectionError:
        return 'CONNECTION_ERROR'
except Exception as e:
        return str(type(e).__name__)


def detect_cdn(url):
        """Return (cdn_name, cdn_hostname) if the URL is served from a known CDN."""
        hostname = urlparse(url).hostname or ''
        for pattern, name in CDN_PATTERNS.items():
                    if pattern in hostname:
                                    return name, hostname
                            return None, None


def check_cdn_availability(cdn_hostname, timeout=8):
        """Ping a CDN domain to see if it is reachable at all."""
        try:
                    response = requests.head(
                                    f'https://{cdn_hostname}/', timeout=timeout,
                                    allow_redirects=True, headers=HEADERS
                    )
                    return response.status_code
except requests.exceptions.ConnectionError:
        return 'CONNECTION_ERROR'
except requests.exceptions.Timeout:
        return 'TIMEOUT'
except Exception as e:
        return str(type(e).__name__)


def crawl_page(url):
        """Return (links, images) sets found on a single page."""
        try:
                    response = requests.get(url, timeout=15, headers=HEADERS)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.content, 'html.parser')

            links = set()
        images = set()

        for a_tag in soup.find_all('a', href=True):
                        href = urljoin(url, a_tag['href'])
                        if href.startswith('http'):
                                            links.add(href)

                    for img_tag in soup.find_all('img', src=True):
                                    src = urljoin(url, img_tag['src'])
                                    if src.startswith('http'):
                                                        images.add(src)

                                return links, images
except Exception as e:
        return set(), set()


def generate_report():
        report = []
    report.append('# Website Health Check Report\n\n')
    report.append(f'**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")}\n')

    total_broken_links = 0
    total_broken_images = 0
    total_cdn_issues = 0

    for website in WEBSITES:
                report.append(f'\n## {website}\n')

        # Build list of pages to crawl
                pages_to_crawl = [website]
                for extra_path in EXTRA_PAGES.get(website, []):
                                pages_to_crawl.append(urljoin(website, extra_path))

                all_links = set()
                all_images = set()

        for page_url in pages_to_crawl:
                        page_links, page_images = crawl_page(page_url)
                        all_links.update(page_links)
                        all_images.update(page_images)

        # --- CDN Health Check ---
        cdn_domains = defaultdict(list)
        for img_url in all_images:
                        cdn_name, cdn_hostname = detect_cdn(img_url)
                        if cdn_name:
                                            cdn_domains[cdn_hostname].append((cdn_name, img_url))

                    if cdn_domains:
                                    report.append('\n### CDN Health\n')
                                    for cdn_hostname, cdn_entries in cdn_domains.items():
                                                        cdn_name = cdn_entries[0][0]
                                                        image_count = len(cdn_entries)
                                                        status = check_cdn_availability(cdn_hostname)
                                                        # 403 on the root is normal for many CDNs — still reachable
                                                        if isinstance(status, int) and status < 500:
                                                                                report.append(
                                                                                                            f'✅ **{cdn_name}** (`{cdn_hostname}`) — reachable '
                                                                                                            f'(HTTP {status}), routing {image_count} image(s)\n'
                                                                                    )
                    else:
                    report.append(
                                                f'🚨 **{cdn_name}** (`{cdn_hostname}`) — **UNREACHABLE** '
                                                f'({status}), affecting {image_count} image(s)\n'
                    )
                                            total_cdn_issues += image_count
else:
            report.append('\n### CDN Health\n')
            report.append('ℹ️ No CDN-hosted images detected\n')

        # --- Link Check (internal links only, up to 30) ---
        base_domain = urlparse(website).netloc
        internal_links = sorted(
                        l for l in all_links if base_domain in (urlparse(l).netloc or '')
        )[:30]

        broken_links = []
        report.append(f'\n### Links ({len(internal_links)} internal links checked)\n')
        for link in internal_links:
                        status = check_url(link)
                        if status not in [200, 301, 302, 303, 307, 308]:
                                            broken_links.append((link, status))
                                            total_broken_links += 1

                    if broken_links:
                                    report.append('❌ **Broken Links:**\n')
                                    for link, status in broken_links:
                                                        report.append(f'- {link} (Status: {status})\n')
                    else:
                                    report.append('✅ All internal links OK\n')

        # --- Image Check (origin-hosted only, skip CDN images) ---
        cdn_image_urls = {url for entries in cdn_domains.values() for _, url in entries}
        origin_images = sorted(img for img in all_images if img not in cdn_image_urls)[:25]

        broken_images = []
        report.append(
                        f'\n### Images ({len(all_images)} total found, '
                        f'{len(origin_images)} origin-hosted checked)\n'
        )
        for image in origin_images:
                        status = check_url(image)
                        if status not in [200, 301, 302, 303, 307, 308]:
                                            broken_images.append((image, status))
                                            total_broken_images += 1

                    if broken_images:
                                    report.append('❌ **Broken Origin Images:**\n')
                                    for image, status in broken_images:
                                                        report.append(f'- {image} (Status: {status})\n')
                    else:
                                    report.append('✅ All origin-hosted images OK\n')

    # --- Summary ---
    report.append('\n## Summary\n')
    report.append(f'- **Broken Links:** {total_broken_links}\n')
    report.append(f'- **Broken Origin Images:** {total_broken_images}\n')
    report.append(f'- **CDN-affected Images:** {total_cdn_issues}\n')

    if total_cdn_issues > 0:
                report.append(
                                f'\n> ⚠️ **CDN ALERT:** {total_cdn_issues} images are routed through an '
                                f'unreachable CDN. Disable the CDN plugin (e.g. Smush CDN in WordPress) '
                                f'to restore images immediately, then contact your CDN provider.\n'
                )

    return ''.join(report)


if __name__ == '__main__':
        report = generate_report()
    print(report)
    with open('health_check_output.txt', 'w') as f:
                f.write(report)
