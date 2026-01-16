"""
Indeed provider.

Note: Indeed does not have a public API. This provider attempts to scrape
public job listings. Use with caution and respect rate limits and robots.txt.
"""

from __future__ import annotations

import urllib.parse
from typing import List, TYPE_CHECKING

from bs4 import BeautifulSoup

from jobscout.models import (
    NormalizedJob,
    Criteria,
    RemoteType,
    EmploymentType,
    normalize_text,
    canonicalize_url,
    parse_date,
    now_utc,
)
from jobscout.extract.html import strip_html
from jobscout.providers.base import Provider

if TYPE_CHECKING:
    from jobscout.fetchers.http import HttpFetcher


class IndeedProvider(Provider):
    """Provider for Indeed job listings (scraping-based)."""

    name = "indeed"

    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        """Collect jobs from Indeed."""
        self.reset_stats()

        # Build search URL
        query = urllib.parse.quote(criteria.primary_query)
        location = urllib.parse.quote(criteria.location or "Remote")
        url = f"https://www.indeed.com/jobs?q={query}&l={location}&start=0"

        result = await fetcher.fetch(url)
        if not result.ok:
            self.log_error(f"Request failed: {result.error or result.status}")
            return []

        jobs: List[NormalizedJob] = []

        try:
            soup = BeautifulSoup(result.text, "html.parser")
            # Indeed uses job cards with data-jk attribute
            job_cards = soup.find_all("div", {"data-jk": True})
        except Exception as e:
            self.log_error(f"HTML parsing failed: {e}")
            return []

        for card in job_cards[:criteria.max_results_per_source]:
            try:
                job_id = card.get("data-jk", "")
                if not job_id:
                    continue

                # Title
                title_elem = card.find("h2", class_="jobTitle")
                if not title_elem:
                    continue
                title_link = title_elem.find("a")
                title = normalize_text(title_link.get_text() if title_link else title_elem.get_text())
                if not title:
                    continue

                # Company
                company_elem = card.find("span", {"data-testid": "company-name"})
                if not company_elem:
                    company_elem = card.find("span", class_="companyName")
                company = normalize_text(company_elem.get_text() if company_elem else "")
                if not company:
                    company = "Unknown"

                # Location
                location_elem = card.find("div", {"data-testid": "text-location"})
                if not location_elem:
                    location_elem = card.find("div", class_="companyLocation")
                location_raw = normalize_text(location_elem.get_text() if location_elem else "Remote")

                # Job URL
                if title_link and title_link.get("href"):
                    job_path = title_link.get("href")
                    if job_path.startswith("/"):
                        job_url = f"https://www.indeed.com{job_path}"
                    else:
                        job_url = canonicalize_url(job_path)
                else:
                    job_url = f"https://www.indeed.com/viewjob?jk={job_id}"

                # Description snippet
                desc_elem = card.find("div", {"id": f"job-snippet-{job_id}"})
                if not desc_elem:
                    desc_elem = card.find("div", class_="job-snippet")
                description = strip_html(desc_elem.get_text() if desc_elem else "")

                # Salary
                salary_elem = card.find("span", {"data-testid": "attribute_snippet_testid"})
                if not salary_elem:
                    salary_elem = card.find("span", class_="salary-snippet")
                salary_text = normalize_text(salary_elem.get_text() if salary_elem else "")
                salary_min = None
                salary_max = None
                if salary_text:
                    import re
                    matches = re.findall(r"\$?([\d,]+)", salary_text)
                    if matches:
                        try:
                            salary_min = float(matches[0].replace(",", ""))
                            if len(matches) > 1:
                                salary_max = float(matches[1].replace(",", ""))
                        except ValueError:
                            pass

                # Posted date
                date_elem = card.find("span", {"data-testid": "myJobsStateDate"})
                if not date_elem:
                    date_elem = card.find("span", class_="date")
                date_text = normalize_text(date_elem.get_text() if date_elem else "")
                posted_at = parse_date(date_text)

                # Employment type
                employment_types = [EmploymentType.UNKNOWN]
                job_type_elem = card.find("div", class_="metadata")
                if job_type_elem:
                    job_type_text = normalize_text(job_type_elem.get_text())
                    et = EmploymentType.from_text(job_type_text)
                    if et != EmploymentType.UNKNOWN:
                        employment_types = [et]

                # Remote type
                remote_type = RemoteType.from_text(location_raw)

                job = NormalizedJob(
                    provider_id=job_id,
                    scraped_at=now_utc(),
                    posted_at=posted_at,
                    source=self.name,
                    source_url=url,
                    title=title,
                    company=company,
                    location_raw=location_raw,
                    remote_type=remote_type,
                    employment_types=employment_types,
                    salary_min=salary_min,
                    salary_max=salary_max,
                    job_url=canonicalize_url(job_url),
                    apply_url=canonicalize_url(job_url),
                    description_text=description,
                    tags=[],
                )
                jobs.append(job)

            except Exception as e:
                self.log_error(f"Error parsing job card: {e}")
                continue

        self.stats.collected = len(jobs)
        return jobs
