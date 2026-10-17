import os
from django.conf import settings
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from academics.models import FormSection

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Register Roboto Fonts
FONT_DIR = os.path.join(settings.BASE_DIR, 'fonts')
pdfmetrics.registerFont(TTFont('Roboto', os.path.join(FONT_DIR, 'Roboto-Regular.ttf')))
pdfmetrics.registerFont(TTFont('Roboto-Bold', os.path.join(FONT_DIR, 'Roboto-Bold.ttf')))

def generate_application_pdf(application, buffer):
    institute = application.course.institute if application.course else None
    styles = getSampleStyleSheet()
    
    # Custom Styles (Standardized to Roboto, No Italics)
    title_style = ParagraphStyle('TitleStyle', parent=styles['Normal'], fontSize=16, leading=20, alignment=1, fontName='Roboto-Bold')
    sub_title_style = ParagraphStyle('SubTitle', parent=styles['Normal'], fontSize=8, leading=10, alignment=1, fontName='Roboto')
    header_bar_style = ParagraphStyle('HeaderBar', parent=styles['Normal'], fontSize=10, color=colors.white, alignment=1, fontName='Roboto-Bold')
    section_style = ParagraphStyle('SectionStyle', parent=styles['Normal'], fontSize=10, fontName='Roboto-Bold', spaceBefore=10, spaceAfter=5)
    field_label_style = ParagraphStyle('FieldLabel', parent=styles['Normal'], fontSize=9, fontName='Roboto-Bold', color=colors.grey)
    field_value_style = ParagraphStyle('FieldValue', parent=styles['Normal'], fontSize=9, fontName='Roboto')
    declaration_style = ParagraphStyle('DeclStyle', parent=styles['Normal'], fontSize=8, leading=10, alignment=4, leftIndent=0, fontName='Roboto')

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
        field_type = v.field.field_type if v.field else v.field_type
        field_label = v.field.label if v.field else v.field_label
        if field_type == 'file' and field_label and 'photo' in field_label.lower() and v.value:
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
    import datetime
    current_date_str = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
    
    app_info = [
        [
            Paragraph(f"Application ID: <b>#{application.id}</b>", field_value_style), 
            Paragraph(f"Submitted Date: <b>{application.created_at.strftime('%d/%m/%Y')}</b>", field_value_style),
            Paragraph(f"Submitted Time: <b>{application.created_at.strftime('%I:%M %p')}</b>", field_value_style)
        ],
        [
            Paragraph(f"Course Applied for: <font color='blue'><b>{application.course.name.upper() if application.course else ''}</b></font>", field_value_style), 
            "", 
            Paragraph(f"<font size='8' color='grey'>Applied on: {application.created_at.strftime('%d/%m/%Y %H:%M')}</font>", field_value_style)
        ]
    ]
    info_table = Table(app_info, colWidths=[2.5*inch, 2.3*inch, 1.5*inch])
    elements.append(info_table)
    elements.append(Spacer(1, 15))

    # --- 4. DYNAMIC SECTIONS ---
    app_form = application.course.form if (application.course and hasattr(application.course, 'form')) else None
    
    if app_form:
        sections = FormSection.objects.filter(fields__form=app_form).distinct().order_by('order')
        from academics.models import FieldOption # Import for lookup
        for section in sections:
            elements.append(Paragraph(section.name.upper(), section_style))
            data = []
            for field in section.fields.all().order_by('order'):
                if field.field_type == 'file': continue
                
                val_obj = application.field_values.filter(field=field).first()
                val = val_obj.value if val_obj else "-"
                
                # NEW: Resolve Display Text
                display_val = str(val)
                label_lower = field.label.lower()
                
                # Check for Field Options regardless of field type
                opt = FieldOption.objects.filter(field=field, value=val).first()
                if opt:
                    display_val = opt.display_text
                
                # Resolve Qualifying Examination name
                if "exam" in label_lower or "qualifying" in label_lower:
                    if display_val.isdigit() or (display_val.lower().startswith('id:') and display_val[3:].strip().isdigit()):
                        clean_id = display_val[3:].strip() if display_val.lower().startswith('id:') else display_val
                        from academics.models import QualifyingExam
                        exam_obj = QualifyingExam.objects.filter(id=clean_id).first()
                        if exam_obj:
                            display_val = exam_obj.name
                
                data.append([Paragraph(field.label, field_label_style), Paragraph(display_val, field_value_style)])
            
            if data:
                t = Table(data, colWidths=[2*inch, 4.3*inch])
                t.setStyle(TableStyle([
                    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                    ('BACKGROUND', (0,0), (0,-1), colors.whitesmoke),
                    ('PADDING', (0,0), (-1,-1), 8),
                ]))
                elements.append(t)
                elements.append(Spacer(1, 10))

    # [REST OF MARKS LOGIC UNCHANGED...]
    
    # --- 5. MARKS ---
    marks_data = []
    total_obtained = 0
    total_max = 0
    
    for v in application.field_values.all().order_by('id'):
        label_lower = (v.field.label if v.field else v.field_label or "").lower()
        section_lower = (v.field.section.name if v.field and v.field.section else v.field_label or "").lower()
        is_qual_field = any(x in label_lower or x in section_lower for x in ["mark", "subject", "qualify", "exam"])
        if v.value and ":" in str(v.value) and is_qual_field:
            try:
                parts = str(v.value).split(":")
                subject_name = parts[0].strip()
                marks_val = float(parts[1].strip())
                max_marks = float(parts[2].strip()) if len(parts) >= 3 else 100
                
                total_obtained += marks_val
                total_max += max_marks
                
                marks_data.append([
                    Paragraph(subject_name, field_value_style), 
                    Paragraph(str(marks_val), field_value_style),
                    Paragraph(str(max_marks), field_value_style)
                ])
            except: continue
    
    if marks_data:
        elements.append(Paragraph("QUALIFYING EXAMINATION MARKS", section_style))
        percentage = (total_obtained / total_max * 100) if total_max > 0 else 0
        m_rows = [["Subject", "Marks Obtained", "Max Marks"]] + marks_data
        m_rows.append([Paragraph("<b>TOTAL AGGREGATE</b>", field_value_style), Paragraph(f"<b>{total_obtained}</b>", field_value_style), Paragraph(f"<b>{total_max}</b>", field_value_style)])
        m_rows.append([Paragraph("<b>TOTAL PERCENTAGE</b>", field_value_style), "", Paragraph(f"<b>{percentage:.2f}%</b>", field_value_style)])
        m_table = Table(m_rows, colWidths=[2.1*inch, 2.1*inch, 2.1*inch])
        m_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Roboto-Bold'),
            ('PADDING', (0,0), (-1,-1), 8),
            ('BACKGROUND', (0, -2), (-1, -1), colors.whitesmoke), 
            ('SPAN', (0, -1), (1, -1)), # Span first two columns for percentage
        ]))
        elements.append(m_table)

    # --- 6. DECLARATION ---
    elements.append(Spacer(1, 15))
    elements.append(Paragraph("DECLARATION", section_style))
    decl_text = f"I, {application.student.first_name.upper() if application.student.first_name else application.student.username.upper()}, declare that all the statements made in this application are true, complete and correct to the best of my knowledge and belief and that in the event of any information being found false or incorrect or ineligibility being detected before or after the admission, action can be taken against me."
    elements.append(Paragraph(f"{decl_text}", declaration_style))
    
    elements.append(Spacer(1, 15))
    
    # Signature alignment fix
    # Signature images
    student_sig_img = None
    if student_photo_path: # This was actually looking for photo path in original code, wait
        # I need to find the signature path
        for v in application.field_values.all():
            field_label = v.field.label if v.field else v.field_label
            is_signature = getattr(v.field, 'is_signature', False) if v.field else False
            if (is_signature or (field_label and "signature" in field_label.lower())) and v.value:
                path = os.path.join(settings.MEDIA_ROOT, str(v.value))
                if os.path.exists(path):
                    try:
                        student_sig_img = Image(path, 1.2*inch, 0.4*inch)
                    except: pass
                break

    sig_data = [
        ["", "", student_sig_img if student_sig_img else ""],
        ["Place: ...................", "", "................................................"],
        ["Date: ....................", "", "Student Signature"],
        ["", "", ""],
        ["", "", "................................................"],
        ["", "", "Parent/Guardian Signature"],
    ]
    sig_table = Table(sig_data, colWidths=[2.1*inch, 1.2*inch, 3*inch])
    sig_table.setStyle(TableStyle([
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ALIGN', (2,0), (2,-1), 'CENTER'),
        ('VALIGN', (2,0), (2,0), 'BOTTOM'), # Align image to bottom of its cell
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (2, 0), (2, 0), -5), # Pull signature image closer to line
    ]))
    elements.append(sig_table)

    # --- 7. OFFICE USE BOX ---
    elements.append(Spacer(1, 20))
    office_content = [
        [Paragraph("FOR OFFICE USE ONLY", ParagraphStyle('Off', parent=styles['Normal'], fontSize=10, alignment=1, fontName='Roboto-Bold'))],
        [Spacer(1, 5)],
        [Table([
            ["Admission Quota: ............................", "No: Date Of Tc: ............................"],
            ["Rank: ....................................", "Checked By: ......................................."]
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


def generate_allotment_memo_pdf(context, buffer):
    """
    Generates a printable single-page PDF allotment memo matching the official allotment memo format.
    """
    import datetime
    from reportlab.lib.colors import HexColor
    from reportlab.graphics.shapes import Drawing, Circle, String

    app = context.get('app')
    institute = context.get('institute') or (app.course.institute if app and app.course else None)
    styles = getSampleStyleSheet()

    # A4: 595.27 x 841.89 points. With 34pt margins, usable width = 527.27 pt
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=34,
        rightMargin=34,
        topMargin=24,
        bottomMargin=20
    )
    elements = []

    # Typography styles matching Times New Roman college allotment memo
    inst_name_style = ParagraphStyle(
        'MemoInstName',
        fontName='Times-Bold',
        fontSize=14,
        leading=16.5,
        alignment=1,
        textColor=HexColor('#001F3F')
    )
    inst_addr_style = ParagraphStyle(
        'MemoInstAddr',
        fontName='Times-Roman',
        fontSize=10,
        leading=13,
        alignment=1,
        textColor=HexColor('#001F3F')
    )
    inst_course_style = ParagraphStyle(
        'MemoCourse',
        fontName='Times-Roman',
        fontSize=10,
        leading=13,
        alignment=1,
        textColor=HexColor('#001F3F')
    )
    memo_title_style = ParagraphStyle(
        'MemoTitle',
        fontName='Times-Bold',
        fontSize=12,
        leading=15,
        alignment=1,
        textColor=colors.black
    )

    th_style = ParagraphStyle(
        'ThStyle',
        fontName='Times-Bold',
        fontSize=9,
        leading=11.5,
        textColor=colors.black
    )
    td_style = ParagraphStyle(
        'TdStyle',
        fontName='Times-Roman',
        fontSize=9,
        leading=11.5,
        textColor=colors.black
    )
    sec_title_style = ParagraphStyle(
        'SecTitle',
        fontName='Times-Bold',
        fontSize=9,
        leading=11.5,
        textColor=colors.black
    )
    bullet_style = ParagraphStyle(
        'DocBullet',
        fontName='Times-Roman',
        fontSize=8.5,
        leading=11,
        leftIndent=15,
        firstLineIndent=-10,
        textColor=colors.black
    )
    fee_title_style = ParagraphStyle(
        'FeeTitle',
        fontName='Times-Bold',
        fontSize=9,
        leading=11.5,
        textColor=HexColor('#0E1140')
    )
    fee_desc_style = ParagraphStyle(
        'FeeDesc',
        fontName='Times-Roman',
        fontSize=8.5,
        leading=11.5,
        firstLineIndent=20,
        alignment=4,
        textColor=colors.black
    )
    fee_details_style = ParagraphStyle(
        'FeeDetails',
        fontName='Times-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.black
    )
    bank_th_style = ParagraphStyle(
        'BankTh',
        fontName='Times-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.black
    )
    bank_td_style = ParagraphStyle(
        'BankTd',
        fontName='Times-Roman',
        fontSize=8.5,
        leading=11,
        textColor=colors.black
    )
    rep_style = ParagraphStyle(
        'RepNote',
        fontName='Times-Roman',
        fontSize=9,
        leading=12,
        textColor=colors.black
    )
    print_style = ParagraphStyle(
        'PrintOn',
        fontName='Times-Roman',
        fontSize=7.5,
        leading=9.5,
        textColor=HexColor('#666666')
    )

    # 1. HEADER (Centered Institute & Allotment Title)
    inst_name = (institute.name if institute and institute.name else "JDT ISLAM COLLEGE OF ARTS AND SCIENCE")
    if institute and institute.address:
        inst_addr = institute.address.strip().replace('\n', ', ')
    else:
        inst_addr = "CALICUT 673012, Phone No. 0495 2730366, 2730398<br/>Email: nursingadmission22@gmail.com"

    course_name_str = app.course.name if (app and app.course) else "Admission"
    acad_year_str = app.academic_year.name if (app and app.academic_year) else ""
    course_line = f"{course_name_str} Admission {acad_year_str}".strip()

    elements.append(Paragraph(inst_name, inst_name_style))
    elements.append(Spacer(1, 2))
    elements.append(Paragraph(inst_addr, inst_addr_style))
    elements.append(Spacer(1, 2))
    elements.append(Paragraph(course_line, inst_course_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("<u><b>ALLOTMENT MEMO</b></u>", memo_title_style))
    elements.append(Spacer(1, 6))

    # 2. DETAILS TABLE
    allot_date_raw = context.get('allotment_date')
    if hasattr(allot_date_raw, 'strftime'):
        allot_date_str = allot_date_raw.strftime('%Y-%m-%d')
    else:
        allot_date_str = str(allot_date_raw or datetime.date.today().strftime('%Y-%m-%d'))

    app_no = str(context.get('app_no') or (app.form_no if app else ''))
    student_name = str(context.get('student_name') or (app.display_name if app else ''))
    dob_str = str(context.get('dob') or '')
    quota_str = str(context.get('quota') or 'Merit')
    place_str = str(context.get('place') or '')
    rank_str = str(context.get('rank') or '')
    phase_str = str(context.get('phase_no') or '1st Allotment')

    table_data = [
        [Paragraph("Phase No", th_style), Paragraph(phase_str, td_style)],
        [Paragraph("Allotment Date", th_style), Paragraph(allot_date_str, td_style)],
        [Paragraph("Application No", th_style), Paragraph(app_no, td_style)],
        [Paragraph("Name", th_style), Paragraph(student_name, td_style)],
        [Paragraph("Date of Birth", th_style), Paragraph(dob_str, td_style)],
        [Paragraph("Quota", th_style), Paragraph(quota_str, td_style)],
        [Paragraph("Place", th_style), Paragraph(place_str, td_style)],
        [Paragraph("Rank", th_style), Paragraph(rank_str, td_style)],
    ]

    details_table = Table(table_data, colWidths=[184, 343])
    details_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.75, colors.black),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (0, -1), HexColor('#FAFAFA')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(details_table)
    elements.append(Spacer(1, 6))

    # 3. ORIGINAL DOCUMENTS LIST
    elements.append(Paragraph("Original documents to be produced at the time of joining:", sec_title_style))
    elements.append(Spacer(1, 2))

    doc_bullets = [
        "Allotment Memo (2 copies)",
        "Application form (2 copies)",
        "SSLC, PLUSTWO/Pass Certificate (2 copies)",
        "TC & Conduct Certificate (2 copies)",
        "2 passport size colour photograph with white background and one stamp size photo.",
        "Eligibility certificate and migration certificate (if applicable) (2 Copies)",
        "Aadhaar copy (one copy)",
    ]
    for b in doc_bullets:
        elements.append(Paragraph(f"&bull;&nbsp;&nbsp;{b}", bullet_style))
        elements.append(Spacer(1, 1))

    # 4. FEE PAYMENT INSTRUCTION & DETAILS
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("Kindly pay the fee by Online payment", fee_title_style))
    elements.append(Spacer(1, 2))
    elements.append(Paragraph(
        "After scrutiny of the documents, provisional admission will be given if found eligible. "
        "You have to remit the full fee for the first year as prescribed by admission supervisory committee.",
        fee_desc_style
    ))

    fee_details_str = str(context.get('fee_details') or '').strip()
    if fee_details_str:
        elements.append(Spacer(1, 3))
        elements.append(Paragraph(fee_details_str.replace('\n', '<br/>'), fee_details_style))

    # 5. BANK DETAILS (Optional)
    if context.get('include_bank_details'):
        elements.append(Spacer(1, 4))
        bank_rows = [
            [Paragraph("Beneficiary Name", bank_th_style), Paragraph(f": {inst_name}", bank_td_style)],
            [Paragraph("Bank Name", bank_th_style), Paragraph(f": {context.get('bank_name', 'Punjab National Bank')}", bank_td_style)],
            [Paragraph("A/c No", bank_th_style), Paragraph(f": {context.get('account_no', '4909001300014441')}", bank_td_style)],
            [Paragraph("IFSC Code", bank_th_style), Paragraph(f": {context.get('ifsc_code', 'PUNB0788500')}", bank_td_style)],
            [Paragraph("Branch Name", bank_th_style), Paragraph(f": {context.get('branch_name', 'Vellimadukunnu')}", bank_td_style)],
        ]
        bank_table = Table(bank_rows, colWidths=[110, 390])
        bank_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        indented_bank = Table([[Spacer(20, 1), bank_table]], colWidths=[20, 507])
        indented_bank.setStyle(TableStyle([
            ('PADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(indented_bank)

    # 6. REPORTING INSTRUCTIONS
    elements.append(Spacer(1, 5))
    rep_from = str(context.get('report_from') or '')
    rep_to = str(context.get('report_to') or '')
    rep_time = str(context.get('reporting_time') or '10:00 AM')

    reporting_text = (
        f"Candidates must report to {inst_name} from <b>{rep_from}</b> to <b>{rep_to}</b> with original document <b>at {rep_time}</b>.<br/>"
        "If you fail to report on time, admission will be cancelled."
    )
    elements.append(Paragraph(reporting_text, rep_style))
    elements.append(Spacer(1, 10))

    # 7. SEAL & SIGNATURE
    seal_flowable = None
    if institute and getattr(institute, 'seal_image', None):
        try:
            seal_file = os.path.join(settings.MEDIA_ROOT, str(institute.seal_image))
            if os.path.exists(seal_file):
                seal_flowable = Image(seal_file, 65, 65)
        except Exception:
            seal_flowable = None

    if not seal_flowable:
        d = Drawing(65, 65)
        d.add(Circle(32.5, 32.5, 31, strokeColor=colors.black, strokeWidth=1.5, fillColor=None))
        d.add(String(32.5, 35, 'OFFICIAL', fontName='Times-Roman', fontSize=7.5, textAnchor='middle', fillColor=HexColor('#333333')))
        d.add(String(32.5, 24, 'SEAL', fontName='Times-Roman', fontSize=7.5, textAnchor='middle', fillColor=HexColor('#333333')))
        seal_flowable = d

    sig_flowable = None
    if institute and getattr(institute, 'signature_image', None):
        try:
            sig_file = os.path.join(settings.MEDIA_ROOT, str(institute.signature_image))
            if os.path.exists(sig_file):
                sig_flowable = Image(sig_file, 100, 40)
        except Exception:
            sig_flowable = None

    if not sig_flowable:
        sig_flowable = Spacer(1, 40)

    auth_table = Table([[seal_flowable, sig_flowable]], colWidths=[263, 264])
    auth_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('PADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(auth_table)
    elements.append(Spacer(1, 6))

    # 8. FOOTER
    printed_str = datetime.datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')
    elements.append(Paragraph(f"Printed On : {printed_str}", print_style))

    doc.build(elements)


