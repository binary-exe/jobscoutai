---
name: Add Multiple Job Scraping Sources
overview: ""
todos: []
---

# Add Multiple Job Scraping Sources

## Overview

Add 6 new API-based job scraping providers to expand job coverage. Each provider follows the existing pattern: inherits from `Provider` base class, implements `collect()` method, and normalizes data into `NormalizedJob` objects.

## Current Architecture

```mermaid
graph TD
A[Orchestrator] --> B[Provider Base Class]
B --> C[RemotiveProvider]
B --> D[RemoteOKProvider]
B --> E[ArbeitnowProvider]