def placement_context(request):
    """Expose the most recent placement id for sidebar navigation."""
    first_placement_id = None
    try:
        from apps.placements.models import Placement

        first_placement = Placement.objects.order_by('-start_date').first()
        if first_placement is not None:
            first_placement_id = first_placement.pk
    except Exception:
        first_placement_id = None
    return {'first_placement_id': first_placement_id}


def student_context(request):
    """Expose whether the current user has a student profile."""
    is_student = False
    if request.user.is_authenticated:
        email = getattr(request.user, 'email', '') or ''
        if email:
            from apps.students.models import Student

            is_student = Student.objects.filter(email__iexact=email).exists()
    return {'is_student': is_student}
