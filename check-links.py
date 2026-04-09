#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime
from collections import defaultdict

WEBSITES = [
    'https://www.bil-jac.com',
    'https://homeschoolacademy.com',
    'https://www.curriculumexpress.com',
    'https://padhps.com',
    'https://discoverk8learning.com',
    'https://elephango.com',
]

EXTRA_PAGES = {
    'https://www.bil-jac.com': [
        '/products/30-20-performance-dog-food/',
        '/products/adult-select-dry-dog-food/',
        '/products/',
        '/why-bil-jac/',
    ]
}

CDN_PATTERNS = {
    'smushcdn.com': 'Smush Image CDN (WPMU Dev)',
    'cloudfront.net': 'Amazon CloudFront',
    'fastly.net': 'Fastly CDN',
    'imgix.net': 'Imgix CDN',
    'cloudflare.com': 'Cloudflare CDN',
}

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; SiteHealthChecker/2.0)'}


def check_url(url, timeout=10):
    try:
        r = requests.head(url, timeout=timeout, allow_redirects=True, headers=HEADERS)
        return r.status_code
    except requests.exceptions.Timeout:
        return 'TIMEOUT'
    except requests.exceptions.ConnectionError:
        return 'CONNECTION_ERROR'
    except Exception as e:
        return str(type(e).__name__)


def detect_cdn(url):
    hostname = urlparse(url).hostname or ''
    for pattern, name in CDN_PATTERNS.items():
        if pattern in hostname:
            return name, hostname
    return None, None


def check_cdn_availability(cdn_hostname, timeout=8):
    try:
        r = requests.head('https://' + cdn_hostname + '/',
                         timeout=timeout, allow_redirects=True, headers=HEADERS)
        return r.status_code
    except requests.exceptions.ConnectionError:
        return 'CONNECTION_ERROR'
    except requests.exceptions.Timeout:
        return 'TIMEOUT'
    except Exception as e:
        return str(type(e).__name__)


def crawl_page(url):
    try:
        r = requests.get(url, timeout=15, headers=HEADERS)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, 'html.parser')
        links = set()
        images = set()
        for a in soup.find_all('a', href=True):
            h = urljoin(url, a['href'])
            if h.startswith('http'):
                links.add(h)
        for img in soup.find_all('img', src=True):
            s = urljoin(url, img['src'])
            if s.startswith('http'):
                images.add(s)
        return links, images
    except Exception:
        return set(), set()


def generate_report():
    report = []
    report.append('# Website Health Check Report\n\n')
    report.append('**Generated:** ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC') + '\n')
    broken_links_total = 0
    broken_images_total = 0
    cdn_issues_total = 0

    for website in WEBSITES:
        report.append('\n## ' + website + '\n')
        pages = [website] + [urljoin(website, p) for p in EXTRA_PAGES.get(website, [])]
        all_links = set()
        all_images = set()
        for page in pages:
            lnks, imgs = crawl_page(page)
            all_links.update(lnks)
            all_images.update(imgs)

        cdn_map = defaultdict(list)
        for img in all_images:
            name, host = detect_cdn(img)
            if name:
                cdn_map[host].append((name, img))

        report.append('\n### CDN Health\n')
        if cdn_map:
            for host, entries in cdn_map.items():
                count = len(entries)
                status = check_cdn_availability(host)
                if isinstance(status, int) and status < 500:
                    report.append('CDN OK: ' + entries[0][0] + ' (' + host + ') HTTP ' + str(status) + ' - ' + str(count) + ' images\n')
                else:
                    report.append('CDN ALERT: ' + entries[0][0] + ' (' + host + ') UNREACHABLE ' + str(status) + ' affects ' + str(count) + ' images\n')
                    cdn_issues_total += count
        else:
            report.append('No CDN images detected\n')

        base = urlparse(website).netloc
        int_links = sorted(l for l in all_links if base in (urlparse(l).netloc or ''))[:30]
        broken = []
        report.append('\n### Links (' + str(len(int_links)) + ' checked)\n')
        for link in int_links:
            s = check_url(link)
            if s not in [200, 301, 302, 303, 307, 308]:
                broken.append((link, s))
                broken_links_total += 1
        if broken:
            report.append('Broken Links:\n')
            for link, s in broken:
                report.append('- ' + link + ' (Status: ' + str(s) + ')\n')
        else:
            report.append('All links OK\n')

        cdn_urls = set(u for e in cdn_map.values() for _, u in e)
        orig_imgs = sorted(i for i in all_images if i not in cdn_urls)[:25]
        broken_img = []
        report.append('\n### Images (' + str(len(all_images)) + ' total, ' + str(len(orig_imgs)) + ' origin checked)\n')
        for img in orig_imgs:
            s = check_url(img)
            if s not in [200, 301, 302, 303, 307, 308]:
                broken_img.append((img, s))
                broken_images_total += 1
        if broken_img:
            report.append('Broken Origin Images:\n')
            for img, s in broken_img:
                report.append('- ' + img + ' (Status: ' + str(s) + ')\n')
        else:
            report.append('All origin images OK\n')

    report.append('\n## Summary\n')
    report.append('- Broken Links: ' + str(broken_links_total) + '\n')
    report.append('- Broken Origin Images: ' + str(broken_images_total) + '\n')
    report.append('- CDN-affected Images: ' + str(cdn_issues_total) + '\n')
    if cdn_issues_total > 0:
        report.append('\nCDN ALERT: ' + str(cdn_issues_total) + ' images through unreachable CDN. Disable CDN plugin to restore.\n')
    return ''.join(report)


if __name__ == '__main__':
    report = generate_report()
    print(report)
    with open('health_check_output.txt', 'w') as f:
        f.write(report)
