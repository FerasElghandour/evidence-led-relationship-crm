# Operating scope and release procedure

**Feras Elghandour**

## Public demonstration

The hosted report is a static site served over GitHub Pages HTTPS. It contains no backend credentials, upload endpoint, tracking, contact form, third-party JavaScript, or private database. Browser interactions operate locally on published aggregate evidence or synthetic records. The demo is suitable for public browsing; it does not expose the application backend.

To preview, run `python -m http.server 8080 --bind 127.0.0.1 --directory docs` and open `http://localhost:8080`. A local report is not an operational deployment of the underlying model or application.

## Release and rollback

1. Run the repository's quality checks and rebuild the demonstration from its documented input.
2. Review changes to data, claims and configuration; keep secrets and operational records outside version control.
3. Commit to the main branch. The Pages workflow publishes `docs/`; the quality workflow remains separate.
4. Check the live page, controls and downloaded evidence after publication.
5. Roll back by reverting the release commit and waiting for the deployment to succeed. No user-submitted records are stored by this site.

## Backend / operational adoption

The Streamlit application supports a local single-user workflow. Start with `python run.py`; the listener binds to 127.0.0.1. Private data belongs in a separately protected database. Streamlit usage reporting is disabled in the included project configuration.

Before any shared network deployment, implement organization-managed authentication and authorization, TLS termination, least-privilege database access, schema migration review, encrypted backups with a tested restore, retention/deletion controls, and an operator-owned incident process. The public edition does not claim those controls already exist. Do not expose the local app directly on the public internet.
