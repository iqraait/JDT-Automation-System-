def extract_application_data(application):
    data = application.extra_data or {}

    result = {
        "name": application.full_name or "",
        "mobile": "",
        "caste": "",
        "quota": "",
        "gender": "",
        "subjects": {},
        "total": 0,
        "max_total": 0,
        "percentage": 0,
    }

    # ✅ SAFE LOOP
    if isinstance(data, dict):
        for key, value in data.items():

            label = str(key).lower()

            if isinstance(value, str):
                if "mobile" in label or "phone" in label:
                    result["mobile"] = value

                elif "caste" in label:
                    result["caste"] = value

                elif "quota" in label:
                    result["quota"] = value

                elif "gender" in label:
                    result["gender"] = value

    # ✅ SUBJECT SAFE
    subjects = data.get("subjects", {})

    if isinstance(subjects, dict):
        total = 0
        max_total = 0

        for subject, marks in subjects.items():
            try:
                marks = int(marks)
            except:
                marks = 0

            total += marks
            max_total += 100

            result["subjects"][subject] = marks

        result["total"] = total
        result["max_total"] = max_total

        if max_total > 0:
            result["percentage"] = round((total / max_total) * 100, 2)

    return result