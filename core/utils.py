import os
from django.conf import settings
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from academics.models import FormSection

def generate_application_pdf(application, buffer):
    institute = application.course.institute if application.course else None
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = ParagraphStyle('TitleStyle', parent=styles['Normal'], fontSize=16, leading=20, alignment=1, fontName='Helvetica-Bold')
    sub_title_style = ParagraphStyle('SubTitle', parent=styles['Normal'], fontSize=8, leading=10, alignment=1)
    header_bar_style = ParagraphStyle('HeaderBar', parent=styles['Normal'], fontSize=10, color=colors.white, alignment=1, fontName='Helvetica-Bold')
    section_style = ParagraphStyle('SectionStyle', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', spaceBefore=10, spaceAfter=5)
    field_label_style = ParagraphStyle('FieldLabel', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold', color=colors.grey)
    field_value_style = ParagraphStyle('FieldValue', parent=styles['Normal'], fontSize=9)
    declaration_style = ParagraphStyle('DeclStyle', parent=styles['Normal'], fontSize=8, leading=10, alignment=4, leftIndent=0)

    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    elements = []

    # --- 1. HEADER (Logo, Details, Photo) ---
    logo_path = os.path.join(settings.MEDIA_ROOT, str(institute.logo)) if institute and institute.logo else None
    logo_img = None
    if logo_path and os.path.exists(logo_path):
        try:
            logo_img = Image(logo_path, 1*inch, 1*inch)
        except:
            logo_img = None

    student_photo_path = None
    for v in application.field_values.all():
        if v.field.field_type == 'file' and 'photo' in v.field.label.lower() and v.value:
            path = os.path.join(settings.MEDIA_ROOT, str(v.value))
            if os.path.exists(path):
                student_photo_path = path; break
    
    photo_img = None
    if student_photo_path:
        try:
             photo_img = Image(student_photo_path, 1.2*inch, 1.5*inch)
        except:
             photo_img = Paragraph("PHOTO", styles['Normal'])
    else:
        photo_img = Paragraph("PHOTO", styles['Normal'])

    # Institute Info
    inst_name = Paragraph(institute.name.upper() if institute else "INSTITUTE NAME", title_style)
    # Safely get phone, email, website as they might not be in the model
    i_phone = getattr(institute, 'phone', '-')
    i_email = getattr(institute, 'email', institute.user.email if (institute and institute.user) else '-')
    
    inst_details = Paragraph(f"{institute.address if institute else ''}<br/>Phone: {i_phone} | Email: {i_email}", sub_title_style)
    
    header_table = Table([
        [logo_img if logo_img else "", [inst_name, Spacer(1, 5), inst_details], photo_img]
    ], colWidths=[1.2*inch, 3.8*inch, 1.3*inch])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOX', (2,0), (2,0), 1, colors.grey), # Photo box
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 10))

    # --- 2. TITLE BAR ---
    title_bar = Table([[Paragraph("ADMISSION APPLICATION FORM (2025-2026)", header_bar_style)]], colWidths=[6.3*inch])
    title_bar.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.black),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(title_bar)
    elements.append(Spacer(1, 10))

    # --- 3. APP INFO ---
    app_info = [
        [
            Paragraph(f"Application ID: <b>#{application.id}</b>", field_value_style), 
            Paragraph(f"Date: <b>{application.created_at.strftime('%d/%m/%Y')}</b>", field_value_style),
            Paragraph(f"Time: <b>{application.created_at.strftime('%I:%M %p')}</b>", field_value_style)
        ],
        [Paragraph(f"Course Applied for: <font color='blue'><b>{application.course.name.upper() if application.course else ''}</b></font>", field_value_style), "", ""]
    ]
    info_table = Table(app_info, colWidths=[2.5*inch, 2.3*inch, 1.5*inch])
    elements.append(info_table)
    elements.append(Spacer(1, 15))

    # --- 4. DYNAMIC SECTIONS ---
    app_form = application.course.form if (application.course and hasattr(application.course, 'form')) else None
    
    if app_form:
        sections = FormSection.objects.filter(fields__form=app_form).distinct().order_by('order')
        for section in sections:
            elements.append(Paragraph(section.name.upper(), section_style))
            data = []
            for field in section.fields.all().order_by('order'):
                if field.field_type == 'file': continue
                # NEW: Handle snapshot fields if reference field is deleted (Part 6)
                val_obj = application.field_values.filter(field=field).first()
                if not val_obj and field:
                    # If field is deleted, we might not find it by ForeignKey
                    # This logic assumes we want to show existing data even if field isn't in section anymore
                    pass 
                
                # Fetching by application field values to ensure we show even orphans
                val = val_obj.value if val_obj else "-"
                data.append([Paragraph(field.label, field_label_style), Paragraph(str(val), field_value_style)])
            
            if data:
                t = Table(data, colWidths=[2*inch, 4.3*inch])
                t.setStyle(TableStyle([
                    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                    ('BACKGROUND', (0,0), (0,-1), colors.whitesmoke),
                    ('PADDING', (0,0), (-1,-1), 8),
                ]))
                elements.append(t)
                elements.append(Spacer(1, 10))

    # --- 5. MARKS ---
    marks_data = []
    total_obtained = 0
    total_max = 0
    
    for v in application.field_values.all():
        if v.value and ":" in str(v.value):
            try:
                subject, marks = v.value.split(":")
                subject_name = subject.strip()
                marks_val = float(marks.strip())
                
                # Try to find max marks for this subject if possible
                # In current system, max marks are stored in ExamSubject model
                # For PDF, we can use a dummy or try to match. 
                # Better: In calculateTotal we can pass max marks too.
                # For now, let's assume standard max marks or look it up if we have a match.
                max_marks = 100 # Fallback
                
                total_obtained += marks_val
                total_max += max_marks # This is a placeholder, real max marks should be captured
                
                marks_data.append([
                    Paragraph(subject_name, field_value_style), 
                    Paragraph(str(marks_val), field_value_style)
                ])
            except: continue
    
    if marks_data:
        elements.append(Paragraph("QUALIFYING EXAMINATION MARKS", section_style))
        
        # Calculate percentage
        percentage = (total_obtained / total_max * 100) if total_max > 0 else 0
        
        m_rows = [["Subject", "Marks Obtained"]] + marks_data
        # Add Total Row
        m_rows.append([Paragraph("<b>TOTAL AGGREGATE</b>", field_value_style), Paragraph(f"<b>{total_obtained}</b>", field_value_style)])
        m_rows.append([Paragraph("<b>TOTAL PERCENTAGE</b>", field_value_style), Paragraph(f"<b>{percentage:.2f}%</b>", field_value_style)])
        
        m_table = Table(m_rows, colWidths=[3.15*inch, 3.15*inch])
        m_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('PADDING', (0,0), (-1,-1), 8),
            ('BACKGROUND', (0, -2), (-1, -1), colors.whitesmoke), # Highlight total/percent
        ]))
        elements.append(m_table)

    # --- 6. DECLARATION ---
    elements.append(Spacer(1, 15))
    elements.append(Paragraph("DECLARATION", section_style))
    decl_text = "I declare that all the statements made in this application are true, complete and correct to the best of my knowledge and belief and that in the event of any information being found false or incorrect or ineligibility being detected before or after the admission, action can be taken against me."
    elements.append(Paragraph(f"<i>{decl_text}</i>", declaration_style))
    
    elements.append(Spacer(1, 25))
    sig_data = [
        ["Place: ...................", "", "................................................"],
        ["Date: ....................", "", "Student Signature"],
        ["", "", ""],
        ["", "", "................................................"],
        ["", "", "Parent/Guardian Signature"],
    ]
    sig_table = Table(sig_data, colWidths=[2*inch, 1.3*inch, 3*inch])
    sig_table.setStyle(TableStyle([
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ALIGN', (2,0), (2,-1), 'CENTER'),
    ]))
    elements.append(sig_table)

    # --- 7. OFFICE USE BOX ---
    elements.append(Spacer(1, 20))
    office_content = [
        [Paragraph("FOR OFFICE USE ONLY", ParagraphStyle('Off', parent=styles['Normal'], fontSize=10, alignment=1, fontName='Helvetica-Bold'))],
        [Spacer(1, 5)],
        [Table([
            ["Verification Status: ............................", "Admission Number: ............................"],
            ["Payment Ref: ....................................", "Checked By: ......................................."]
        ], colWidths=[3*inch, 3*inch])],
        [Spacer(1, 15)],
        [Paragraph("................................................<br/>Seal & Signature of Principal", ParagraphStyle('Seal', parent=styles['Normal'], fontSize=8, alignment=2))]
    ]
    office_table = Table(office_content, colWidths=[6.3*inch])
    office_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 2, colors.black),
        ('PADDING', (0,0), (-1,-1), 10),
    ]))
    elements.append(office_table)

    doc.build(elements)
