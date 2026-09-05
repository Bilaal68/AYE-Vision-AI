# AI packages for computer vision experiments.

Django should call these through `backend/services/`, not the other way around.

Nothing in this folder is a running microservice. That keeps the learning
architecture small: one API (Django), one database, optional background jobs (Celery).
