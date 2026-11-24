from django.urls import path

from accounts import team_views

urlpatterns = [
    path("members/", team_views.MembersView.as_view(), name="team-members"),
    path("members/<int:pk>/", team_views.MemberDetailView.as_view(), name="team-member"),
    path("invitations/", team_views.InvitationsView.as_view(), name="team-invitations"),
    path(
        "invitations/<int:pk>/",
        team_views.InvitationDetailView.as_view(),
        name="team-invitation",
    ),
]

public_urlpatterns = [
    path("<str:token>/", team_views.InvitationPreviewView.as_view(), name="invitation-preview"),
    path(
        "<str:token>/accept/",
        team_views.AcceptInvitationView.as_view(),
        name="invitation-accept",
    ),
]
