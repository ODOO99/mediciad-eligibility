"""Filtering logic for eligibility results."""
from django.db import models as django_models
from django.db.models import Q
from imports.models import ImportRow


def apply_import_row_filters(queryset, params):
    """Apply all result filters to an ImportRow queryset."""
    # Text searches
    if cin := params.get('cin', '').strip():
        queryset = queryset.filter(cin__icontains=cin)

    if name := params.get('name', '').strip():
        queryset = queryset.filter(
            Q(patient__first_name__icontains=name) |
            Q(patient__last_name__icontains=name)
        )

    # Date of service
    if dos := params.get('date_of_service', '').strip():
        queryset = queryset.filter(
            eligibility_request__date_of_service=dos
        )

    # Status filters
    if status := params.get('status', '').strip():
        queryset = queryset.filter(status=status)

    if patient_action := params.get('patient_action', '').strip():
        queryset = queryset.filter(patient_action=patient_action)

    if eligibility_status := params.get('eligibility_status', '').strip():
        queryset = queryset.filter(
            eligibility_request__response__response_status=eligibility_status
        )

    # Recertification date range
    if recert_from := params.get('recert_from', '').strip():
        queryset = queryset.filter(
            patient__eligibility_snapshots__recertification_date__gte=recert_from
        ).distinct()
    if recert_to := params.get('recert_to', '').strip():
        queryset = queryset.filter(
            patient__eligibility_snapshots__recertification_date__lte=recert_to
        ).distinct()

    # Indicator filters (Code 60, S1)
    indicators = params.getlist('indicator') if hasattr(params, 'getlist') else []
    match_mode = params.get('match_mode', 'any')  # 'any' or 'all'

    indicator_map = {
        'recertification': 'patient__eligibility_snapshots__has_recertification',
        'code_60': 'patient__eligibility_snapshots__has_code_60',
        's1': 'patient__eligibility_snapshots__has_s1',
    }

    if indicators:
        if match_mode == 'all':
            for ind in indicators:
                if field := indicator_map.get(ind):
                    queryset = queryset.filter(**{field: True})
        else:  # 'any' — logical OR
            q = Q()
            for ind in indicators:
                if field := indicator_map.get(ind):
                    q |= Q(**{field: True})
            if q:
                queryset = queryset.filter(q)
        queryset = queryset.distinct()

    return queryset


def apply_sorting(queryset, sort_by):
    """Apply sorting to queryset."""
    sort_map = {
        'cin': 'cin',
        '-cin': '-cin',
        'name': 'patient__last_name',
        '-name': '-patient__last_name',
        'recert_date': 'patient__eligibility_snapshots__recertification_date',
        '-recert_date': '-patient__eligibility_snapshots__recertification_date',
        'row': 'row_number',
        '-row': '-row_number',
    }
    if sort_field := sort_map.get(sort_by):
        return queryset.order_by(sort_field)
    return queryset.order_by('row_number')
