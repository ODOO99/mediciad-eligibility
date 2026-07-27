"""Patient views."""
from datetime import date
from django.shortcuts import get_object_or_404, render
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Patient


def patient_list(request):
    q = request.GET.get('q', '').strip()
    qs = Patient.objects.prefetch_related('eligibility_snapshots').order_by('-updated_at')
    if q:
        qs = qs.filter(
            Q(cin__icontains=q) |
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q)
        )
    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'patients/list.html', {'page_obj': page, 'q': q})


def patient_detail(request, patient_id):
    patient = get_object_or_404(Patient, pk=patient_id)
    current_eligibility = patient.current_eligibility
    history = patient.eligibility_snapshots.select_related(
        'eligibility_response__eligibility_request'
    ).order_by('-created_at')
    return render(request, 'patients/detail.html', {
        'patient': patient,
        'current_eligibility': current_eligibility,
        'history': history,
    })


def patient_detail_modal(request, patient_id):
    patient = get_object_or_404(Patient, pk=patient_id)
    return render(request, 'patients/detail.html', {
        'patient': patient,
        'current_eligibility': patient.current_eligibility,
        'history': patient.eligibility_snapshots.select_related(
            'eligibility_response__eligibility_request'
        ).order_by('-created_at'),
        'modal': True,
    })


def lookup(request):
    """Single CIN eligibility lookup — runs inline, no batch required."""
    result = None
    cin = ''
    dos = date.today().isoformat()
    error = None

    if request.method == 'POST':
        cin = request.POST.get('cin', '').strip().upper()
        dos = request.POST.get('date_of_service', '').strip()

        if not cin:
            error = 'CIN is required.'
        elif not dos:
            error = 'Date of service is required.'
        else:
            try:
                from datetime import date as dt
                date_of_service = dt.fromisoformat(dos)
            except ValueError:
                error = 'Invalid date format.'
            else:
                from .services import run_eligibility_lookup
                result = run_eligibility_lookup(cin, date_of_service)
                if result.get('error'):
                    error = result['error']

    return render(request, 'patients/lookup.html', {
        'result': result,
        'cin': cin,
        'date_of_service': dos,
        'error': error,
    })
