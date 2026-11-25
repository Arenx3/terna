"""Working on a candidate together: comments, mentions, assignments, notifications."""

from django.db import transaction

from accounts.models import Membership, User
from candidates.access import people_who_can_see
from candidates.models import Application, Comment, InterviewerAssignment, Notification
from events.models import EventType, OutboxEvent
from events.outbox import emit


class NotAnInterviewerError(ValueError):
    """Only people with the interviewer role are assigned to candidates."""


def add_comment(application: Application, author: User, body: str, mentions: list) -> Comment:
    """Save an internal comment. Mentions are kept only for people who can open the
    candidate, so a notification never leads someone to a page they can't see."""
    allowed = {person.id for person in people_who_can_see(application)}
    mentioned = [user_id for user_id in dict.fromkeys(mentions) if user_id in allowed]
    with transaction.atomic():
        comment = Comment.objects.create(
            application=application,
            author=author,
            author_name=author.full_name,
            body=body,
            mentions=mentioned,
        )
        emit(
            EventType.COMMENT_CREATED,
            entity_type="application",
            entity_id=application.id,
            label=application.candidate.full_name,
            payload={"comment_id": comment.id, "mentions": [str(m) for m in mentioned]},
        )
    return comment


def assign_interviewers(application: Application, user_ids: list) -> list[User]:
    """Replace who interviews this candidate. Newly assigned people are notified."""
    interviewers = {
        membership.user_id: membership.user
        for membership in Membership.objects.select_related("user").filter(
            user_id__in=user_ids, role=Membership.Role.INTERVIEWER
        )
    }
    if len(interviewers) != len(set(user_ids)):
        raise NotAnInterviewerError
    with transaction.atomic():
        current = set(application.assignments.values_list("user_id", flat=True))
        wanted = set(interviewers)
        application.assignments.exclude(user_id__in=wanted).delete()
        InterviewerAssignment.objects.bulk_create(
            [
                InterviewerAssignment(
                    company_id=application.company_id, application=application, user_id=uid
                )
                for uid in wanted - current
            ]
        )
        if wanted != current:
            emit(
                EventType.APPLICATION_ASSIGNED,
                entity_type="application",
                entity_id=application.id,
                label=application.candidate.full_name,
                payload={
                    "added": [str(uid) for uid in wanted - current],
                    "interviewers": sorted(user.full_name for user in interviewers.values()),
                },
            )
    return sorted(interviewers.values(), key=lambda person: person.full_name)


def notify(event: OutboxEvent) -> None:
    """Outbox consumer: mentions and assignments become notifications, once each."""
    if event.type == EventType.COMMENT_CREATED:
        kind, recipients = Notification.Kind.MENTION, event.payload.get("mentions", [])
        comment_id = event.payload.get("comment_id")
    elif event.type == EventType.APPLICATION_ASSIGNED:
        kind, recipients = Notification.Kind.ASSIGNED, event.payload.get("added", [])
        comment_id = None
    else:
        return
    recipients = [uid for uid in recipients if uid != str(event.actor_id)]
    if not recipients:
        return
    Notification.objects.bulk_create(
        [
            Notification(
                company_id=event.company_id,
                recipient_id=uid,
                kind=kind,
                application_id=int(event.entity_id),
                comment_id=comment_id,
                actor_name=event.actor_name,
                source_event_id=event.id,
            )
            for uid in recipients
        ],
        ignore_conflicts=True,
    )
