def calculate_total_and_percentage(application):
    subject_values = application.applicationfieldvalue_set.all()

    total = 0
    max_total = 0

    for val in subject_values:
        if ":" in val.value:
            try:
                subject, mark = val.value.split(":")
                mark = float(mark)

                total += mark

                # Optional: if max stored somewhere, else assume 100
                max_total += 100  

            except:
                continue

    percentage = (total / max_total * 100) if max_total else 0

    return total, round(percentage, 2)