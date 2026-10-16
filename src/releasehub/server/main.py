"""Entry point for uvicorn:  uvicorn releasehub.server.main:app"""
from releasehub.server.app import create_app

app = create_app()
