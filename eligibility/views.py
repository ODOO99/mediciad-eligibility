"""Eligibility response views."""
from django.shortcuts import get_object_or_404, render
from django.utils.html import escape
from django.core.paginator import Paginator
from django.db.models import Q
from .models import EligibilityResponse, EligibilityRequest


def history(request):
    """List all eligibility checks across batches and single lookups."""
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()

    qs = EligibilityResponse.objects.select_related(
        'eligibility_request', 'patient'
    ).order_by('-created_at')

    if q:
        qs = qs.filter(
            Q(eligibility_request__cin__icontains=q) |
            Q(patient__first_name__icontains=q) |
            Q(patient__last_name__icontains=q)
        )
    if status:
        qs = qs.filter(response_status=status)

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get('page'))

    status_choices = EligibilityResponse.RESPONSE_STATUSES
    return render(request, 'eligibility/history.html', {
        'page_obj': page,
        'q': q,
        'selected_status': status,
        'status_choices': status_choices,
    })


def response_detail(request, response_id):
    response = get_object_or_404(EligibilityResponse.objects.select_related(
        'eligibility_request', 'patient',
    ).prefetch_related(
        'indicators', 'financial_details', 'benefits', 'rejections',
    ), pk=response_id)
    req = response.eligibility_request
    context = {
        'response': response,
        'request_obj': req,
        'indicators': response.indicators.all(),
        'financials': response.financial_details.all(),
        'benefits': response.benefits.all(),
        'rejections': response.rejections.all(),
        'raw_270_escaped': escape(req.raw_270) if req else '',
        'raw_271_escaped': escape(response.raw_271),
        # Keep old key for back-compat
        'raw_escaped': escape(response.raw_271),
    }
    return render(request, 'eligibility/response_detail.html', context)


def raw_response(request, response_id):
    response = get_object_or_404(EligibilityResponse.objects.select_related(
        'eligibility_request'
    ), pk=response_id)
    req = response.eligibility_request
    context = {
        'response': response,
        'request_obj': req,
        'raw_270_escaped': escape(req.raw_270) if req else '',
        'raw_271_escaped': escape(response.raw_271),
        'raw_escaped': escape(response.raw_271),
    }
    return render(request, 'eligibility/raw_response.html', context)
