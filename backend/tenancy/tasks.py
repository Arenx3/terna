"""Celery tasks that touch tenant data.

    @tenant_task
    def send_digest(company_id, digest_id): ...

    send_digest.delay(company.id, digest.id)

The first argument is always the company id; the task body runs inside
`tenant_context(company_id)`, so the company is set before any query.
Long-running work (transcription) should keep that block short: read inputs,
process outside the transaction, then open a new `tenant_context` to write.
"""

from functools import partial

from celery import Task, shared_task

from tenancy.context import tenant_context


class TenantTask(Task):
    abstract = True

    def __call__(self, company_id, *args, **kwargs):
        with tenant_context(company_id):
            return super().__call__(company_id, *args, **kwargs)


tenant_task = partial(shared_task, base=TenantTask)
