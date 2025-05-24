"""
Author:     Sai Vignesh Golla
LinkedIn:   https://www.linkedin.com/in/saivigneshgolla/

Copyright (C) 2024 Sai Vignesh Golla

License:    GNU Affero General Public License
            https://www.gnu.org/licenses/agpl-3.0.en.html
            
GitHub:     https://github.com/GodsScion/Auto_job_applier_linkedIn

version:    24.12.29.12.30
"""


##> Common Response Formats
array_of_strings = {"type": "array", "items": {"type": "string"}}
"""
Response schema to represent array of strings `["string1", "string2"]`
"""
#<


##> Extract Skills

# Structure of messages = `[{"role": "user", "content": extract_skills_prompt}]`

extract_skills_prompt ="""You are a specialized job requirements extractor for technical roles. Your task is to thoroughly extract ALL skills and requirements mentioned in the job description below.

IMPORTANT INSTRUCTIONS:
1. Analyze both EXPLICIT statements (directly mentioned skills) and IMPLICIT requirements (skills needed but not directly stated).
2. Be comprehensive - include ALL technologies, methodologies, techniques, and qualifications.
3. Pay special attention to distinguishing between REQUIRED vs PREFERRED qualifications.

Extract and categorize ALL skills into these specific buckets:
- "data_tech_stack": ALL programming languages, software, tools, platforms (Python, R, SQL, AWS, etc.)
- "analytical_methods": ALL statistical and analytical techniques (regression, ML algorithms, etc.)
- "domain_knowledge": ALL industry/field-specific knowledge (healthcare, finance, bioinformatics, etc.)
- "professional_skills": ALL soft skills and business capabilities (communication, project management, etc.)
- "required_qualifications": ALL explicitly MANDATORY skills, education, or experience
- "preferred_qualifications": ALL "nice-to-have" or "preferred" but NOT mandatory skills

RESPONSE FORMAT:
Return ONLY a valid JSON object with the exact structure below. Each category MUST contain an array of strings:

{
  "data_tech_stack": [],
  "analytical_methods": [],
  "domain_knowledge": [],
  "professional_skills": [],
  "required_qualifications": [],
  "preferred_qualifications": []
}

JOB DESCRIPTION:
{}
"""
"""
Use `extract_skills_prompt.format(job_description)` to insert `job_description`.
"""

# DeepSeek-specific optimized prompt, emphasis on returning only JSON without using json_schema
deepseek_extract_skills_prompt = """
You are a specialized job requirements extractor for data science, analytics, and bioinformatics roles. Your task is to extract all skills mentioned in a job description and classify them into categories aligned with data science careers:

1. "data_tech_stack": All programming languages, packages, tools, platforms and infrastructure used in data work including Python, R, SQL, SAS, SPSS, Tableau, Power BI, Excel, Jupyter, AWS/Azure/GCP data services, TensorFlow, PyTorch, scikit-learn, Hadoop, Spark, MongoDB, etc.

2. "analytical_methods": Statistical and analytical approaches including regression analysis, hypothesis testing, A/B testing, experimental design, machine learning algorithms, deep learning, NLP, computer vision, clustering, time series analysis, predictive modeling, data mining, etc.

3. "domain_knowledge": Field-specific requirements like bioinformatics, genomics, biological data, healthcare analytics, financial modeling, clinical data, NGS, educational assessment, market research, customer analysis, etc.

4. "professional_skills": Non-technical abilities including communication, leadership, project management, stakeholder management, team collaboration, data storytelling, documentation, etc.

5. "required_qualifications": All explicitly stated mandatory skills, education, or experience (both technical and non-technical).

6. "preferred_qualifications": Any skills listed as desirable or "nice-to-have" but not mandatory.

IMPORTANT: You must ONLY return valid JSON object in the exact format shown below - no additional text, explanations, or commentary.
Each category should contain an array of strings, even if empty.
{{
    "data_tech_stack": ["Example Skill 1", "Example Skill 2"],
    "analytical_methods": ["Example Skill 1", "Example Skill 2"],
    "domain_knowledge": ["Example Skill 1", "Example Skill 2"],
    "professional_skills": ["Example Skill 1", "Example Skill 2"],
    "required_qualifications": ["Example Skill 1", "Example Skill 2"],
    "preferred_qualifications": ["Example Skill 1", "Example Skill 2"]
}}

JOB DESCRIPTION:
{}
"""
"""
DeepSeek optimized version, use `deepseek_extract_skills_prompt.format(job_description)` to insert `job_description`.
"""


extract_skills_response_format = {
    "type": "json_schema",
    "json_schema": {
        "name": "Skills_Extraction_Response",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "tech_stack": array_of_strings,
                "technical_skills": array_of_strings,
                "other_skills": array_of_strings,
                "required_skills": array_of_strings,
                "nice_to_have": array_of_strings,
            },
            "required": [
                "tech_stack",
                "technical_skills",
                "other_skills",
                "required_skills",
                "nice_to_have",
            ],
            "additionalProperties": False
        },
    },
}
"""
Response schema for `extract_skills` function
"""
#<

##> ------ Dheeraj Deshwal : dheeraj9811 Email:dheeraj20194@iiitd.ac.in/dheerajdeshwal9811@gmail.com - Feature ------
##> Answer Questions
# Structure of messages = `[{"role": "user", "content": answer_questions_prompt}]`

ai_answer_prompt ="""You are an experienced job applicant completing an application form. Answer the following question in a NATURAL, HUMAN-LIKE manner.

RESPONSE GUIDELINES:
1. For experience questions (years, duration): Respond with ONLY a number (e.g., "5")
2. For Yes/No questions: Respond with ONLY "Yes" or "No"
3. For short questions: Provide a SINGLE concise sentence
4. For detailed questions: Write a well-structured response (maximum 350 characters)
5. NEVER repeat the question in your answer
6. Sound conversational and natural, NOT like an AI

APPLICANT BACKGROUND:
{}

QUESTION TO ANSWER:
{}

YOUR RESPONSE:
"""
#<