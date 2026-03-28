"""
Message templates for each student use case.

This is the ONLY place to add or edit message copy.
Templates use {variable} placeholders — filled exclusively from the student
record loaded from Google Sheets. No hallucination possible.

Required variables per template:
  homework_followup    : student_name, course_name, upcoming_task, upcoming_deadline
  missed_class         : student_name, course_name, last_class_date, teacher_note
  satisfaction_survey  : student_name, course_name
  upcoming_reminder    : student_name, upcoming_task, upcoming_deadline, course_name
"""

TEMPLATES: dict[str, str] = {
    "homework_followup": (
        "Hi {student_name}! 👋\n\n"
        "We noticed your *{upcoming_task}* for *{course_name}* is due on *{upcoming_deadline}* "
        "and hasn't been submitted yet.\n\n"
        "If you need help or more time, just reply here and your teacher will get back to you. "
        "You've got this! 💪"
    ),

    "missed_class": (
        "Hi {student_name}! 😊\n\n"
        "We missed you in *{course_name}* on {last_class_date}. "
        "Hope everything is okay!\n\n"
        "{teacher_note_line}"
        "Reply here if you have any questions or want to know what was covered. "
        "We look forward to seeing you next time! 📚"
    ),

    "satisfaction_survey": (
        "Hi {student_name}! 🌟\n\n"
        "We hope you're enjoying *{course_name}*!\n\n"
        "We'd love to hear how it's going. How would you rate your experience so far?\n"
        "Reply with a number from 1 (not great) to 5 (amazing) and any feedback you have. "
        "Your input helps us improve! 🙏"
    ),

    "upcoming_reminder": (
        "Hi {student_name}! ⏰\n\n"
        "Just a friendly reminder: *{upcoming_task}* for *{course_name}* "
        "is due on *{upcoming_deadline}*.\n\n"
        "Make sure you're all set! Reply here if you need any help. You're doing great! ⭐"
    ),
}

# Variables required for each template (used for validation before send)
REQUIRED_VARS: dict[str, list[str]] = {
    "homework_followup": ["student_name", "course_name", "upcoming_task", "upcoming_deadline"],
    "missed_class": ["student_name", "course_name", "last_class_date"],
    "satisfaction_survey": ["student_name", "course_name"],
    "upcoming_reminder": ["student_name", "upcoming_task", "upcoming_deadline", "course_name"],
}


def render(template_key: str, variables: dict) -> str:
    """
    Fill a template with variables. Raises KeyError if a required variable is missing.
    The teacher_note_line is optional — handled specially for missed_class.
    """
    template = TEMPLATES[template_key]
    # Special handling: teacher_note_line
    if "teacher_note_line" in template:
        note = variables.get("teacher_note", "")
        variables = {
            **variables,
            "teacher_note_line": f"Your teacher noted: _{note}_\n\n" if note else "",
        }
    return template.format(**variables)


def get_missing_vars(template_key: str, variables: dict) -> list[str]:
    """Return list of required variables not present in variables dict."""
    required = REQUIRED_VARS.get(template_key, [])
    return [v for v in required if not variables.get(v)]
