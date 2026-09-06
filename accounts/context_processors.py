def active_institute_context(request):
    """
    Globally provides active_institute, accessible_institutes, and user_privileges to all templates.
    """
    if not request.user.is_authenticated:
        return {}

    active_inst = None
    accessible_insts = []
    if hasattr(request.user, 'get_active_institute'):
        active_inst = request.user.get_active_institute(request)
        accessible_insts = request.user.get_accessible_institutes()
    else:
        active_inst = getattr(request.user, 'institute', None)

    # User privileges dictionary
    privileges = {}
    priv_list = [
        'perm_admissions_overview', 'perm_student_registration', 'perm_student_list', 'perm_rank_list',
        'perm_attendance', 'perm_notices', 'perm_timetables', 'perm_academic_results', 'perm_course_inventory',
        'perm_fee_reports', 'perm_fee_receipts', 'perm_payment_details',
        'perm_activity_logs', 'perm_system_backup', 'perm_employee_privileges'
    ]
    
    for p in priv_list:
        if hasattr(request.user, 'has_privilege'):
            privileges[p] = request.user.has_privilege(p)
        else:
            privileges[p] = True

    return {
        'active_institute': active_inst,
        'accessible_institutes': accessible_insts,
        'user_privileges': privileges,
        'has_multiple_institutes': len(accessible_insts) > 1 or request.user.is_superuser
    }
