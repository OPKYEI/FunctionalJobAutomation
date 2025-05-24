"""
Configuration for resume font sizes and styles.
Adjust these settings to customize the appearance of your resume.
"""

# Font sizes in points (pt)
FONT_SIZES = {
    "name": 36,              # Your name at the top
    "contact_info": 9,      # Contact information line below name
    "section_header": 12,    # Section titles (SKILLS, WORK EXPERIENCE, etc.)
    "company_name": 11,      # Company/school names
    "job_title": 10,         # Job titles
    "content_text": 10,      # Regular content text (descriptions, bullets)
    "date": 10,              # Dates
    "skills_list": 10,       # Skills list
    "summary": 10,           # Professional summary
}

# Font styles - set to True to enable
FONT_STYLES = {
    "name_bold": True,               # Bold name at top
    "section_header_bold": True,     # Bold section headings
    "company_name_bold": True,       # Bold company names
    "job_title_italic": True,        # Italic job titles
    "technologies_italic": True,     # Italic technologies line
}

# Spacing in points (pt)
SPACING = {
    "after_name": 1,                 # Space after name
    "after_contact_info": 6,         # Space after contact info line
    "after_section_header": 4,       # Space after section titles
    "after_paragraph": 8,            # Space after paragraphs
    "between_experiences": 8,        # Space between work experiences  
}

# Margins in inches
MARGINS = {
    "top": 0.5,
    "bottom": 0.5,
    "left": 0.5,
    "right": 0.5,
}
