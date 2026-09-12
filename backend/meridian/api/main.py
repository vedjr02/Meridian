"""FastAPI application entry point.

Run locally with: `.venv/bin/uvicorn meridian.api.main:app --reload`
"""

from fastapi import FastAPI

from meridian import __version__


def create_app() -> FastAPI:
    """Build and return the FastAPI application.

    Why a factory instead of only a module-level app: tests construct a fresh, isolated app per
    test, and later sessions can inject test configuration (e.g. a throwaway database) without
    import-time side effects leaking between tests.
    """
    app = FastAPI(
        title="Meridian",
        version=__version__,
        description="Process mining, diagnosis and business-case analytics over event logs.",
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        """Report that the API process is up, and which build is answering.

        Why include the version: when the frontend or a deploy check polls this endpoint, a
        stale server still running an old build is otherwise indistinguishable from a fresh one.
        """
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
