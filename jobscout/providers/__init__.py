"""
Job source providers for JobScout.

Each provider implements a consistent interface for collecting jobs
from different sources (APIs, RSS feeds, ATS systems, etc.)
"""

from jobscout.providers.base import Provider
from jobscout.providers.remotive import RemotiveProvider
from jobscout.providers.remoteok import RemoteOKProvider
from jobscout.providers.arbeitnow import ArbeitnowProvider
from jobscout.providers.weworkremotely import WWRRssProvider
from jobscout.providers.greenhouse import GreenhouseProvider
from jobscout.providers.lever import LeverProvider
from jobscout.providers.ashby import AshbyProvider
from jobscout.providers.recruitee import RecruiteeProvider
from jobscout.providers.schemaorg import SchemaOrgProvider
from jobscout.providers.workingnomads import WorkingNomadsProvider
from jobscout.providers.remoteco import RemoteCoProvider
from jobscout.providers.justremote import JustRemoteProvider
from jobscout.providers.wellfound import WellfoundProvider
from jobscout.providers.stackoverflow import StackOverflowProvider
from jobscout.providers.indeed import IndeedProvider
from jobscout.providers.flexjobs import FlexJobsProvider
from jobscout.providers.discovery import (
    expand_queries,
    ddg_search,
    discover_ats_tokens,
)

__all__ = [
    "Provider",
    "RemotiveProvider",
    "RemoteOKProvider",
    "ArbeitnowProvider",
    "WWRRssProvider",
    "GreenhouseProvider",
    "LeverProvider",
    "AshbyProvider",
    "RecruiteeProvider",
    "SchemaOrgProvider",
    "WorkingNomadsProvider",
    "RemoteCoProvider",
    "JustRemoteProvider",
    "WellfoundProvider",
    "StackOverflowProvider",
    "IndeedProvider",
    "FlexJobsProvider",
    "expand_queries",
    "ddg_search",
    "discover_ats_tokens",
]

