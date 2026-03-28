"""
FastAPI dependency providers.
Used in tests to override services with mocks.
"""
from fastapi import Request


def get_sheets_service(request: Request):
    return getattr(request.app.state, "sheets", None)


def get_outreach_graph(request: Request):
    return request.app.state.outreach_graph


def get_telegram_graph(request: Request):
    return request.app.state.telegram_graph


def get_review_queue(request: Request):
    return request.app.state.review_queue


def get_audit_service(request: Request):
    return getattr(request.app.state, "audit_service", None)
