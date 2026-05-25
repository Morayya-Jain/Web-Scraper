"""Source collectors.

Layer A (broad aggregators):
    adzuna, jooble, careerjet

Layer B (public ATS feeds, no auth):
    greenhouse, lever, ashby, workable, recruitee, smartrecruiters, workday

Each module exposes a `fetch() -> list[dict]` that returns rows conforming
to the common schema (see schema.py / dedupe.py). One source failing must
never crash the run - main.py wraps every call in try/except.
"""
