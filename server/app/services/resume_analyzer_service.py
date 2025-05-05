# LLM_interviewer/server/app/services/resume_analyzer.py

import logging
import re
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple, Any, Set
import asyncio

logger = logging.getLogger(__name__) # Define logger at the top

# --- NLP and Date Libraries ---
# Added to requirements.txt:
# spacy>=3.0.0,<4.0.0
# python-dateutil>=2.8.0,<3.0.0
# Download model: python -m spacy download en_core_web_lg (recommended)
try:
    import spacy
    from spacy.matcher import Matcher
    NLP_LOADED = True
    # Load the model once when the service is instantiated
    try:
        # Using a larger model generally yields better results for NER
        NLP_MODEL = spacy.load('en_core_web_lg')
        logger.info("Successfully loaded spaCy model 'en_core_web_lg'.")
    except OSError:
        logger.warning("spaCy model 'en_core_web_lg' not found. Trying 'en_core_web_sm'.")
        try:
            NLP_MODEL = spacy.load('en_core_web_sm')
            logger.info("Successfully loaded spaCy model 'en_core_web_sm'.")
        except OSError:
            logger.error("No spaCy models found (en_core_web_lg or en_core_web_sm). Download with: python -m spacy download [model_name]")
            NLP_MODEL = None
            NLP_LOADED = False
    except ImportError: # Handle case where spacy is installed but model loading fails unexpectedly
         logger.error("Could not load spaCy model due to import error within spaCy itself.")
         NLP_MODEL = None
         NLP_LOADED = False

except ImportError:
    NLP_LOADED = False
    NLP_MODEL = None
    spacy = None
    Matcher = None
    logger.warning("spaCy library not found. Install with 'pip install spacy' and download a model. Skill/Experience extraction will be limited.")

try:
    from dateutil.parser import parse as date_parse
    # Use fuzzy parsing to handle slightly malformed dates
    from dateutil.parser import ParserError as DateParserError
    from dateutil.relativedelta import relativedelta
    DATEUTIL_LOADED = True
except ImportError:
    DATEUTIL_LOADED = False
    DateParserError = Exception # Define fallback exception
    logger.warning("python-dateutil library not found. Install with 'pip install python-dateutil'. Experience calculation will be limited.")
# --- End Libraries ---

# --- Constants ---
# (Expanded Skill List Example - customize heavily based on your domain)
# Consider loading from an external file/database for easier management
SKILL_KEYWORDS = [
    "python", "java", "c++", "c#", "javascript", "typescript", "html", "css", "sql", "nosql", "pl/sql",
    "react", "react.js", "angular", "vue", "vue.js", "node.js", "express", "django", "flask", "fastapi", "spring boot", ".net core", "asp.net",
    "mongodb", "postgresql", "mysql", "redis", "oracle database", "sql server", "elasticsearch", "dynamodb", "cassandra",
    "docker", "kubernetes", "k8s", "aws", "azure", "gcp", "google cloud", "amazon web services", "cloudformation", "lambda", "ec2", "s3",
    "terraform", "ansible", "jenkins", "gitlab ci", "github actions", "ci/cd", "puppet", "chef",
    "linux", "unix", "bash", "powershell", "windows server",
    "git", "svn", "jira", "confluence", "agile", "scrum", "kanban", "waterfall",
    "machine learning", "deep learning", "nlp", "natural language processing", "computer vision", "ai", "artificial intelligence",
    "tensorflow", "pytorch", "keras", "scikit-learn", "opencv", "spacy", "nltk",
    "data analysis", "data science", "pandas", "numpy", "scipy", "matplotlib", "seaborn", "power bi", "tableau", "etl", "data warehousing",
    "api design", "restful api", "graphql", "microservices", "distributed systems", "soa", "message queues", "rabbitmq", "kafka",
    "object-oriented programming", "oop", "functional programming", "data structures", "algorithms",
    "cybersecurity", "penetration testing", "network security", "encryption", "iam", "information security",
    "unit testing", "integration testing", "pytest", "junit", "selenium",
    "communication", "teamwork", "problem-solving", "leadership", # Soft skills
]
SKILL_KEYWORDS_SET = set(s.lower() for s in SKILL_KEYWORDS)

# Regex for explicit YoE mentions
YOE_REGEX = re.compile(r'(\d{1,2})\s*\+?\s+(?:year|yr)s?', re.IGNORECASE)
# Improved Regex for date ranges (still needs refinement for edge cases)
# Handles YYYY, Mon YYYY, Month YYYY, MM/YYYY, MM-YYYY etc. Separators: -, –, to
# End: YYYY, Mon YYYY, Month YYYY, MM/YYYY, MM-YYYY, Present, Current, Now, Today
DATE_RANGE_REGEX = re.compile(
    # Start Date Part (Month optional, Year required)
    r'(?:'                                       # Non-capturing group for start date part
        r'(?:(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?)' # Optional Month Name (Capture Group 1)
        r'|(\d{1,2})[/-]'                         # Optional MM/ or MM- (Capture Group 2)
    r')?'                                        # End optional month part
    r'\s*(\d{4})'                                # Year (Capture Group 3)

    # Separator Part
    r'\s*[-\u2013to]+\s*'                         # Separator (hyphen, en-dash, 'to')

    # End Date Part (Month optional, Year required OR Present/Current)
    r'(?:'                                       # Non-capturing group for end date part
        r'(?:'                                   # Non-capturing group for specific date end
            r'(?:(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?)' # Optional Month Name (Capture Group 4)
            r'|(\d{1,2})[/-]'                     # Optional MM/ or MM- (Capture Group 5)
        r')?'                                    # End optional month part
        r'\s*(\d{4})'                            # Year (Capture Group 6)
        r'|(Present|Current|Today|Now)'          # OR Present/Current keyword (Capture Group 7)
    r')',
    re.IGNORECASE
)
MONTH_MAP = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}
# --- End Constants ---


class ResumeAnalyzerService:
    """
    Service using spaCy and dateutil to extract skills and estimate experience.
    """

    def __init__(self):
        self.nlp = NLP_MODEL # Use the globally loaded model
        self.matcher = None
        if self.nlp:
            self.matcher = Matcher(self.nlp.vocab)
            # TODO: Add specific spaCy Matcher patterns here if needed
            # Example: pattern = [{"LOWER": "react"}, {"LOWER": ".", "OP": "?"}, {"LOWER": "js"}]
            # self.matcher.add("REACT_JS", [pattern])
            logger.info("ResumeAnalyzerService initialized with spaCy resources.")
        else:
             logger.warning("ResumeAnalyzerService initialized WITHOUT spaCy resources.")

    def _parse_date(self, month_str_name: Optional[str], month_str_num: Optional[str], year_str: Optional[str]) -> Optional[datetime]:
        """ Safely parse year and optional month (name or number) into a datetime object. """
        if not year_str: return None
        try:
            year = int(year_str)
            month = 1 # Default
            if month_str_name:
                month = MONTH_MAP.get(month_str_name[:3].lower(), 1)
            elif month_str_num:
                month_num = int(month_str_num)
                if 1 <= month_num <= 12:
                    month = month_num
            # Use beginning of the month, timezone aware
            return datetime(year, month, 1, tzinfo=timezone.utc)
        except (ValueError, TypeError) as e:
            logger.debug(f"Could not parse date components: MonthName='{month_str_name}', MonthNum='{month_str_num}', Year='{year_str}'. Error: {e}")
            return None

    async def extract_skills(self, resume_text: str) -> List[str]:
        """ Extracts skills using keyword matching and basic spaCy NER. """
        if not resume_text: return []
        logger.debug("Extracting skills...")
        extracted_skills: Set[str] = set() # Use a set for automatic deduplication

        # 1. Keyword Matching (on lowercase text)
        text_lower = resume_text.lower()
        for skill in SKILL_KEYWORDS_SET:
            # Use word boundaries for better accuracy
            try:
                if re.search(r'\b' + re.escape(skill) + r'\b', text_lower):
                    extracted_skills.add(skill) # Add the canonical skill name
            except re.error as re_err: # Catch potential regex errors with complex skills
                 logger.warning(f"Regex error matching skill '{skill}': {re_err}")

        # 2. spaCy Processing (if loaded)
        if self.nlp:
            try:
                doc = self.nlp(resume_text)

                # 2a. NER - Check ORG, PRODUCT, potentially others like NORP (Nationalities/Groups - sometimes tech groups)
                # Filter common non-skill orgs/products if possible
                common_non_skills = {'inc', 'llc', 'ltd', 'corp', 'corporation', 'university', 'college', 'institute', 'company'}
                for ent in doc.ents:
                    if ent.label_ in ["ORG", "PRODUCT"]: # Add other relevant labels if needed
                        ent_text_lower = ent.text.lower().strip()
                        # Check if it's a known skill or a plausible multi-word skill not in common non-skills
                        if ent_text_lower in SKILL_KEYWORDS_SET or \
                           (len(ent_text_lower) > 1 and ' ' in ent_text_lower and ent_text_lower not in common_non_skills):
                             extracted_skills.add(ent_text_lower)

                # 2b. spaCy Matcher (if patterns were added in __init__)
                # matches = self.matcher(doc)
                # for match_id, start, end in matches:
                #    span = doc[start:end]
                #    skill_name = self.nlp.vocab.strings[match_id] # Get the label used in matcher.add
                #    extracted_skills.add(skill_name) # Add the canonical name from matcher

            except Exception as e:
                logger.error(f"Error during spaCy processing for skills: {e}", exc_info=True)

        # 3. Final Cleanup & Sort
        final_skills = sorted([s for s in extracted_skills if s]) # Remove empty strings just in case
        logger.info(f"Extracted skills: {len(final_skills)} unique skills found.")
        return final_skills


    async def extract_experience_years(self, resume_text: str) -> Optional[float]:
        """ Estimates total years of experience from date ranges and explicit mentions. """
        if not resume_text or not DATEUTIL_LOADED:
            return None

        logger.debug("Extracting experience years...")
        total_months = 0
        max_explicit_yoe = 0.0
        processed_text_segments = set() # To avoid double counting from identical text matches

        # 1. Extract explicit mentions
        try:
            explicit_matches = YOE_REGEX.findall(resume_text)
            if explicit_matches:
                max_explicit_yoe = max(float(y) for y in explicit_matches)
                logger.debug(f"Found max explicit YoE mention: {max_explicit_yoe}")
        except Exception as e:
            logger.warning(f"Error parsing explicit YoE mentions: {e}")

        # 2. Extract from date ranges
        now = datetime.now(timezone.utc)
        durations_months = []

        for match in DATE_RANGE_REGEX.finditer(resume_text):
            full_match_text = match.group(0)
            if full_match_text in processed_text_segments:
                continue # Skip if we already processed this exact string match
            processed_text_segments.add(full_match_text)

            # Extract captured groups carefully based on the regex structure
            start_month_name, start_month_num, start_year, \
            end_month_name, end_month_num, end_year, present_keyword = match.groups()

            start_date = self._parse_date(start_month_name, start_month_num, start_year)
            end_date = None

            if present_keyword:
                end_date = now
            else:
                end_date = self._parse_date(end_month_name, end_month_num, end_year)

            if start_date and end_date and end_date >= start_date:
                try:
                    delta = relativedelta(end_date, start_date)
                    # Add 1 month because range "Jan 2023 - Jan 2023" should be 1 month, not 0
                    duration_months = (delta.years * 12 + delta.months) + 1
                    durations_months.append(duration_months)
                    logger.debug(f"Parsed range: '{full_match_text}' -> Start: {start_date.date()}, End: {end_date.date()}, Duration: {duration_months} months")
                except Exception as e:
                    logger.warning(f"Error calculating duration for range '{full_match_text}': {e}")
            elif start_date:
                 logger.debug(f"Parsed range '{full_match_text}' but end date was invalid or before start date.")


        # 3. Aggregate Durations (Simplified - Summing durations, doesn't handle overlaps perfectly)
        # A better approach would identify job blocks and build a non-overlapping timeline.
        if durations_months:
            total_months = sum(durations_months)
            calculated_yoe = total_months / 12.0
            logger.debug(f"Total calculated YoE from date ranges (summed, may overlap): {calculated_yoe:.2f}")
        else:
            calculated_yoe = 0.0

        # 4. Determine final YoE
        final_yoe = max(max_explicit_yoe, calculated_yoe)

        logger.info(f"Estimated experience years: {final_yoe:.2f}")
        # Return None if effectively zero, otherwise the calculated value
        return round(final_yoe, 2) if final_yoe > 0.01 else None


    async def analyze_resume(self, resume_text: str) -> Dict[str, Any]:
        """ Performs comprehensive analysis using implemented methods. """
        if not resume_text:
             return {"extracted_skills_list": [], "estimated_yoe": None} # Match expected keys

        logger.info("Performing comprehensive resume analysis...")
        # Run extractions
        # Using asyncio.gather can speed things up if functions are truly async or CPU-bound enough
        # results = await asyncio.gather(
        #     self.extract_skills(resume_text),
        #     self.extract_experience_years(resume_text)
        # )
        # skills = results[0]
        # experience_years = results[1]

        # Run sequentially for simplicity
        skills = await self.extract_skills(resume_text)
        experience_years = await self.extract_experience_years(resume_text)

        analysis_result = {
            "extracted_skills_list": skills,
            "estimated_yoe": experience_years,
            # Add other extracted fields here if implemented
        }
        logger.info("Resume analysis complete.")
        return analysis_result

# Singleton instance
resume_analyzer_service = ResumeAnalyzerService()
