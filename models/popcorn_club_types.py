FOCUS_CLUB_TYPES = frozenset({
    'focus_club',
    'focus_club_90',
    'focus_club_120',
})


def is_focus_club_type(club_type):
    return club_type in FOCUS_CLUB_TYPES


def get_plan_points_for_club_type(plan, club_type):
    """Return the configured points cost for a club type."""
    field_by_type = {
        'regular_offline': 'points_per_offline',
        'regular_online': 'points_per_online',
        'spclub': 'points_per_sp',
        'focus_club': 'points_per_focus',
        'focus_club_90': 'points_per_focus_90',
        'focus_club_120': 'points_per_focus_120',
        'social_experience': 'points_per_social_experience',
    }
    field_name = field_by_type.get(club_type)
    return getattr(plan, field_name, 0) if field_name else 0
