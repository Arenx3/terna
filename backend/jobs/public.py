"""Public careers pages: a company's open jobs, readable by anyone.

Visitors have no company, so the slug in the URL is resolved first and the
request then runs as that company, under row-level security like any other.
Only open jobs are visible, and only what a candidate should read: never the
hiring manager, the pipeline or anything internal.
"""

from django.conf import settings
from django.utils.html import escape
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_field
from rest_framework import exceptions, serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.throttles import IPRateThrottle
from jobs.models import Job, Requirement
from tenancy.context import tenant_context
from tenancy.services import company_by_slug

# schema.org/JobPosting employment types.
EMPLOYMENT_TYPES = {
    Job.Employment.FULL_TIME: "FULL_TIME",
    Job.Employment.PART_TIME: "PART_TIME",
    Job.Employment.CONTRACT: "CONTRACTOR",
    Job.Employment.INTERNSHIP: "INTERN",
}
SALARY_UNITS = {Job.SalaryPeriod.MONTH: "MONTH", Job.SalaryPeriod.YEAR: "YEAR"}
# Headings inside the structured description, in the posting's own language.
REQUIREMENT_HEADINGS = {
    "es": {"must": "Requisitos", "nice": "Deseable"},
    "en": {"must": "Requirements", "nice": "Nice to have"},
}


def job_url(slug: str, job: Job) -> str:
    return f"{settings.PUBLIC_APP_URL.rstrip('/')}/careers/{slug}/jobs/{job.id}"


def posting_schema(job: Job, company_name: str, slug: str) -> dict:
    """The job as schema.org/JobPosting, for search engines (JSON-LD)."""
    requirements = list(job.requirements.all())
    headings = REQUIREMENT_HEADINGS.get(job.language, REQUIREMENT_HEADINGS["en"])
    parts = [f"<p>{escape(par)}</p>" for par in job.description.split("\n\n") if par.strip()]
    for kind in (Requirement.Kind.MUST, Requirement.Kind.NICE):
        items = [f"<li>{escape(r.text)}</li>" for r in requirements if r.kind == kind]
        if items:
            parts.append(f"<p>{headings[kind]}</p><ul>{''.join(items)}</ul>")

    schema: dict = {
        "@context": "https://schema.org/",
        "@type": "JobPosting",
        "title": job.title,
        "description": "".join(parts).replace("\n", "<br>") or escape(job.title),
        "datePosted": (job.published_at or job.created_at).date().isoformat(),
        "employmentType": EMPLOYMENT_TYPES[job.employment],
        "hiringOrganization": {"@type": "Organization", "name": company_name},
        "identifier": {"@type": "PropertyValue", "name": company_name, "value": str(job.id)},
        "url": job_url(slug, job),
        "inLanguage": job.language,
    }
    if job.workplace == Job.Workplace.REMOTE:
        schema["jobLocationType"] = "TELECOMMUTE"
        schema["applicantLocationRequirements"] = {"@type": "Country", "name": job.country}
    else:
        address = {"@type": "PostalAddress", "addressCountry": job.country}
        if job.location:
            address["addressLocality"] = job.location
        schema["jobLocation"] = {"@type": "Place", "address": address}
    if job.salary_min is not None and job.salary_max is not None:
        schema["baseSalary"] = {
            "@type": "MonetaryAmount",
            "currency": job.salary_currency,
            "value": {
                "@type": "QuantitativeValue",
                "minValue": job.salary_min,
                "maxValue": job.salary_max,
                "unitText": SALARY_UNITS[job.salary_period],
            },
        }
    return schema


class PublicCompanySerializer(serializers.Serializer):
    name = serializers.CharField()
    slug = serializers.CharField()


class PublicRequirementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Requirement
        fields = ("text", "kind")
        read_only_fields = fields


class PublicSalarySerializer(serializers.Serializer):
    min = serializers.IntegerField()
    max = serializers.IntegerField()
    currency = serializers.CharField()
    period = serializers.ChoiceField(choices=Job.SalaryPeriod.choices)


class PublicJobSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = (
            "id",
            "title",
            "department",
            "location",
            "country",
            "workplace",
            "employment",
            "language",
            "published_at",
        )
        read_only_fields = fields


class PublicJobSerializer(PublicJobSummarySerializer):
    salary = serializers.SerializerMethodField()
    requirements = PublicRequirementSerializer(many=True, read_only=True)
    posting = serializers.SerializerMethodField(
        help_text="schema.org/JobPosting as JSON-LD, ready to embed."
    )

    class Meta(PublicJobSummarySerializer.Meta):
        fields = (
            *PublicJobSummarySerializer.Meta.fields,
            "description",
            "salary",
            "requirements",
            "posting",
        )
        read_only_fields = fields

    @extend_schema_field(PublicSalarySerializer(allow_null=True))
    def get_salary(self, job: Job) -> dict | None:
        # Shown only as a full range, as the editor promises.
        if job.salary_min is None or job.salary_max is None:
            return None
        return {
            "min": job.salary_min,
            "max": job.salary_max,
            "currency": job.salary_currency,
            "period": job.salary_period,
        }

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_posting(self, job: Job) -> dict:
        company = self.context["company"]
        return posting_schema(job, company["name"], company["slug"])


class CareersPageSerializer(serializers.Serializer):
    company = PublicCompanySerializer()
    jobs = PublicJobSummarySerializer(many=True)


class PublicJobPageSerializer(serializers.Serializer):
    company = PublicCompanySerializer()
    job = PublicJobSerializer()


class PublicView(APIView):
    authentication_classes = ()  # anonymous by design; a session changes nothing
    permission_classes = (AllowAny,)
    throttle_classes = (IPRateThrottle,)
    throttle_scope = "careers"
    cacheable = True

    def company(self, slug: str) -> dict:
        found = company_by_slug(slug)
        if found is None:
            raise exceptions.NotFound
        company_id, name = found
        return {"id": company_id, "name": name, "slug": slug}

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if response.status_code == 200 and self.cacheable:
            # Shared caches may keep a page a minute; a closed job disappears within that.
            response["Cache-Control"] = "public, max-age=60"
        else:
            response["Cache-Control"] = "no-store"
        return response


class CareersView(PublicView):
    @extend_schema(responses={200: CareersPageSerializer}, tags=["careers"])
    def get(self, request: Request, slug: str) -> Response:
        company = self.company(slug)
        with tenant_context(company["id"]):
            jobs = list(Job.objects.filter(status=Job.Status.OPEN).order_by("-published_at"))
        return Response(CareersPageSerializer({"company": company, "jobs": jobs}).data)


class PublicJobView(PublicView):
    @extend_schema(responses={200: PublicJobPageSerializer}, tags=["careers"])
    def get(self, request: Request, slug: str, pk) -> Response:
        company = self.company(slug)
        with tenant_context(company["id"]):
            job = (
                Job.objects.filter(pk=pk, status=Job.Status.OPEN)
                .prefetch_related("requirements")
                .first()
            )
            if job is None:
                raise exceptions.NotFound
            data = PublicJobPageSerializer(
                {"company": company, "job": job}, context={"company": company}
            ).data
        return Response(data)
