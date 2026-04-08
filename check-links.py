#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime

WEBSITES = [
    'https://www.biljac.com',
    'https://homeschoolacademy.com'
]

def check_url(url, timeout=10):
    """Check if a URL is accessible"""
    try:
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        return response.status_code
    except requests.exceptions.Timeout:
        return 'TIMEOUT'
    except requests.exceptions.ConnectionError:
        return 'CONNECTION_ERROR'
    except Exception as e:
        return str(type(e).__name__)

def crawl_website(base_url):
    """Crawl website and return links and images"""
    try:
        response = requests.get(base_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        links = set()
        images = set()
        
        for a_tag in soup.find_all('a', href=True):
            url = urljoin(base_url, a_tag['href'])
            if url.startswith('http'):
                links.add(url)
        
        for img_tag in soup.find_all('img', src=True):
            url = urljoin(base_url, img_tag['src'])
            if url.startswith('http'):
                images.add(url)
        
        return links, images
    except Exception as e:
        return set(), set()

def generate_report():
    """Generate health check report"""
    report = []
    report.append(f"# Website Health Check Report\n\n")
    report.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
    
    total_broken_links = 0
    total_broken_images = 0
    
    for website in WEBSITES:
        report.append(f"\n## {website}\n")
        
        try:
            links, images = crawl_website(website)
            
            broken_links = []
            report.append(f"\n### Links ({len(links)} found)\n")
            for link in sorted(links)[:20]:
                status = check_url(link)
                if status not in [200, 301, 302, 303, 307, 308]:
                    broken_links.append((link, status))
                    total_broken_links += 1
            
            if broken_links:
                report.append("❌ **Broken Links:**\n")
                for link, status in broken_links:
                    report.append(f"- {link} (Status: {status})\n")
            else:
                report.append("✅ All links OK\n")
            
            broken_images = []
            report.append(f"\n### Images ({len(images)} found)\n")
            for image in sorted(images)[:20]:
                status = check_url(image)
                if status not in [200, 301, 302, 303, 307, 308]:
                    broken_images.append((image, status))
                    total_broken_images += 1
            
            if broken_images:
                report.append("❌ **Broken Images:**\n")
                for image, status in broken_images:
                    report.append(f"- {image} (Status: {status})\n")
            else:
                report.append("✅ All images OK\n")
        
        except Exception as e:
            report.append(f"⚠️ Error checking website: {str(e)}\n")
    
    report.append(f"\n## Summary\n")
    report.append(f"- **Total Broken Links:** {total_broken_links}\n")
    report.append(f"- **Total Broken Images:** {total_broken_images}\n")
    
    return ''.join(report)

if __name__ == '__main__':
    print(generate_report())
