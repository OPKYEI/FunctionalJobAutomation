# Updated gpt_processor.py

import json
import asyncio
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
from langchain.llms.base import LLM
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from g4f.client import Client
import pandas as pd
#from src.config import GPT_MODEL_PRIMARY, GPT_MODEL_SECONDARY
from src.utilities.proxies import ProxyRotator

# Global proxy rotator
proxy_rotator = ProxyRotator()

success_list = []

class JobCategory(str, Enum):
    DATA_ANALYST = "data analyst role"
    BUSINESS_ANALYST = "business analyst role"
    GENERAL_ANALYST = "general analyst role"
    WEB_DEVELOPER = "web development role"
    NO_MATCH = "no match"

class JobAnalysisOutput(BaseModel):
    skills_in_priority_order: List[str] = Field(description="Top technical tools and tech stack mentioned in job description")
    job_category: JobCategory = Field(description="Categorization of the job role")
    why_this_company: str = Field(description="Personalized 'Why This Company' paragraph")
    why_me: str = Field(description="Personalized 'Why Me' paragraph")
    job_position_title: str = Field(description="Formatted job position title in English")
    company_name: str = Field(description="Formatted company name in English")
    location: str = Field(description="Location of company who posted job post")
    customized_resume_bullets: List[str] = Field(description="Customized resume bullet points tailored to this job")
    ats_keywords: List[str] = Field(description="Key ATS keywords from the job description")

class EducationalLLM(LLM):
    # [Keep existing code for EducationalLLM]
    @property
    def _llm_type(self) -> str:
        return "custom"

        # ── FULL REPLACEMENT ▸ EducationalLLM._call ────────────────────────────────
    def _call(self, prompt: str, stop: Optional[List[str]] = None, run_manager=None, **kwargs) -> str:
        """
        Try each model in GPT_MODEL_CANDIDATES until one responds.
        Falls back to no-proxy if all proxy attempts fail.
        """
        from src.config import GPT_MODEL_CANDIDATES  # late import to avoid cycles

        for model_name in GPT_MODEL_CANDIDATES:
            for attempt in (1, 2):  # proxy, then rotate proxy
                try:
                    client = Client(proxies=proxy_rotator.get_proxy())
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[{"role": "user", "content": prompt}],
                        **kwargs,
                    )
                    print(f"success with {model_name} via proxy {response.provider}")
                    success_list.append([model_name, response.provider])
                    return self._process_output(response.choices[0].message.content, stop)
                except Exception as e:
                    print(f"Attempt {attempt} with {model_name} failed: {e}")
                    proxy_rotator.remove_current_proxy()

            # last-ditch: same model without proxy
            try:
                client = Client()
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    **kwargs,
                )
                print(f"success with {model_name} (no proxy)")
                success_list.append([model_name, "no-proxy"])
                return self._process_output(response.choices[0].message.content, stop)
            except Exception:
                # move to next model in palette
                continue

        raise RuntimeError("All model attempts failed – try updating GPT_MODEL_CANDIDATES.")


    def _attempt_call(self, prompt: str, stop: Optional[List[str]], **kwargs) -> str:
        client = Client(proxies=proxy_rotator.get_proxy())
        response = client.chat.completions.create(
            model=GPT_MODEL_PRIMARY,
            messages=[{"role": "user", "content": prompt}],
            **kwargs
        )
        print("success with proxy", response.model, response.provider)
        success_list.append(["success with proxy", response.model,response.provider])
        return self._process_output(response.choices[0].message.content, stop)

    def _fallback_call(self, prompt: str, stop: Optional[List[str]], **kwargs) -> str:
        print("Attempting to connect without a proxy...")
        client = Client()
        response = client.chat.completions.create(
            model=GPT_MODEL_SECONDARY,
            messages=[{"role": "user", "content": prompt}],
            **kwargs
        )
        print("success without proxy", response.model, response.provider)
        success_list.append(["success without proxy", response.model, response.provider])
        return self._process_output(response.choices[0].message.content, stop)

    def _process_output(self, output: str, stop: Optional[List[str]]) -> str:
        if stop:
            for s in stop:
                if s in output:
                    output = output[:output.index(s)]
        return output

class JobAnalyzer:
    def __init__(self, df: pd.DataFrame, resume_text: str):
        self.llm = EducationalLLM()
        self.df = df
        self.resume_text = resume_text
        proxy_rotator.get_proxy()

    def _get_prompt(self) -> PromptTemplate:
        template = """
        Analyze the following job description and resume, then provide highly customized content for an application that will score 100% on ATS systems:

        Job Description:
        {job_description}

        Resume:
        {resume}

        Company Name: {company_name}
        Job Position Title: {job_position_title}
        Location: {location}

        Please provide the following information:

        1. List the top technical tools and tech stack mentioned in the job description, which should be highlighted in the resume. Include Python by default for data roles or JavaScript for web roles, listed in priority order based on frequency and importance in the job description.

        2. Categorize the job role: data analyst role, business analyst role, general analyst role, web development role, or no match if none apply.

        3. A personalized 'Why This Company' paragraph that demonstrates deep research into the company's mission, vision, values, products, market position, and culture. Include specific details about their services and accomplishments. Explain why you're excited about the company and how it aligns with your career aspirations.

        4. A personalized 'Why Me' paragraph that demonstrates you are the perfect match for this job. Highlight specific achievements from your resume that match the job requirements. Include metrics and specific technologies. Incorporate keywords from the job description. End with a brief mention of perfecting your homemade pizza recipe before the interview.

        5. A formatted job position title (clean, professional, directory-friendly).

        6. A formatted company name (clean, directory-friendly).

        7. Formatted location as "City, Country".

        8. Create 5-7 highly customized resume bullet points that make you appear to be a perfect match for this job. These should:
           - Be extremely tailored to this specific role's requirements
           - Include measurable achievements with specific metrics (percentages, numbers)
           - Incorporate exact keywords and phrases from the job description
           - Be written in a powerful, action-oriented style beginning with strong verbs
           - Even if these experiences are not in the original resume, create appropriate bullet points that would be ideal for this role
           - Focus on the most relevant skills and experiences for this specific position
           - Follow the format: "Action verb + what you did + result/impact with metrics"

        9. List 10-15 key ATS keywords from the job description that should be incorporated into the resume. Focus on hard skills, technologies, and qualifications emphasized in the job posting.

        Write your response as a structured JSON object with the following keys: skills_in_priority_order, job_category, why_this_company, why_me, job_position_title, company_name, location, customized_resume_bullets, ats_keywords.

        Make all content extremely specific to this job and company - avoid generic language that could apply to any position.
        """
        
        return PromptTemplate(
            input_variables=["job_description", "resume", "company_name", "job_position_title", "location"],
            template=template
        )

    def _extract_json(self, text: str) -> Dict[str, Any]:
        try:
            # Handle code block format if present
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
                
            # Find JSON object within text if not properly formatted
            start_idx = text.find('{')
            end_idx = text.rfind('}') + 1
            if start_idx >= 0 and end_idx > start_idx:
                text = text[start_idx:end_idx]
                
            return json.loads(text)
        except json.JSONDecodeError:
            print(f"Failed to parse JSON: {text}")
            return {}

    async def analyze_job(
        self,
        job_description: str,
        resume: str,
        company_name: str,
        job_position_title: str,
        job_id: str,
        location: str,
    ) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Run the LLM chain and return (job_id, parsed_json_dict).
        Never returns None – on any failure we return an empty-field dict
        so downstream code always has the expected columns.
        """
        prompt = self._get_prompt()
        chain = (
            {
                "job_description": RunnablePassthrough(),
                "resume": lambda x: x["resume"],
                "company_name": lambda x: x["company_name"],
                "job_position_title": lambda x: x["job_position_title"],
                "location": lambda x: x["location"],
            }
            | prompt
            | self.llm
            | self._extract_json
        )

        try:
            raw_json = await chain.ainvoke(
                {
                    "job_description": job_description,
                    "resume": resume,
                    "company_name": company_name,
                    "job_position_title": job_position_title,
                    "location": location,
                }
            )
        except Exception as e:
            print(f"LLM call failed → {e}")
            raw_json = {}

        # ---------- tolerant parsing --------------------------------------- #
        # Fill in every expected key so dataframe columns always exist
        safe_dict = {
            "skills_in_priority_order": raw_json.get("skills_in_priority_order", []),
            "job_category": raw_json.get("job_category", "no match"),
            "why_this_company": raw_json.get("why_this_company", ""),
            "why_me": raw_json.get("why_me", ""),
            "job_position_title": raw_json.get("job_position_title", job_position_title),
            "company_name": raw_json.get("company_name", company_name),
            "location": raw_json.get("location", location),
            "customized_resume_bullets": raw_json.get("customized_resume_bullets", []),
            "ats_keywords": raw_json.get("ats_keywords", []),
        }

        return job_id, safe_dict

        # ── FULL REPLACEMENT • src/processor/gpt_processor.py ─────────────────────────
    async def process_jobs(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Analyse every job row asynchronously and return:
        • df_new    → brand-new GPT columns (top_skills, ats_keywords, …)
        • df_update → refreshed basics (title, company, location)   – optional
        """
        tasks = []
        for _, row in self.df.iterrows():
            tasks.append(
                asyncio.create_task(
                    self.analyze_job(
                        job_description=row.get("job_description", ""),
                        resume=self.resume_text,
                        company_name=row.get("company_name", ""),
                        job_position_title=row.get("job_position_title", ""),
                        job_id=row.get("job_id", ""),
                        location=row.get("location", ""),
                    )
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        new_records:    List[Dict[str, Any]] = []
        update_records: List[Dict[str, Any]] = []

        for res in results:
            # Skip failed coroutines or explicit None returns
            if res is None or isinstance(res, Exception):
                continue
            try:
                job_id, out = res
                new_dict, upd_dict = self._preprocess_job_analysis((job_id, out))
                new_records.append(new_dict)
                update_records.append(upd_dict)
            except Exception as e:
                print(f"Pre-processing error for one job → skipped: {e}")

        df_new    = pd.DataFrame(new_records)    if new_records    else pd.DataFrame()
        df_update = pd.DataFrame(update_records) if update_records else pd.DataFrame()

        return df_new, df_update




    @staticmethod
    def _preprocess_job_analysis(
        result: Tuple[str, Dict[str, Any]]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        job_id, out = result
        new_cols = {
            "job_id": job_id,
            "top_skills": ", ".join(out["skills_in_priority_order"]),
            "job_category": out["job_category"],
            "why_this_company": out["why_this_company"],
            "why_me": out["why_me"],
            "customized_resume_bullets": "\n".join(out["customized_resume_bullets"]),
            "ats_keywords": ", ".join(out["ats_keywords"]),
        }
        update_cols = {
            "job_id": job_id,
            "job_position_title": out["job_position_title"],
            "company_name": out["company_name"],
            "location": out["location"],
        }
        return new_cols, update_cols


if __name__ == "__main__":
    # Initialize the proxy rotator
    pass