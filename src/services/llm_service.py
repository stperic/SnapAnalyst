"""
LLM Service for Natural Language to SQL Query Generation

Supports multiple LLM providers:
- OpenAI (GPT-4)
- Anthropic (Claude)
- Ollama (Local models)

Uses Vanna.AI with ChromaDB for SQL generation with training data.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from vanna.chromadb import ChromaDB_VectorStore
from vanna.openai import OpenAI_Chat
from vanna.anthropic import Anthropic_Chat
from vanna.ollama import Ollama

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class VannaOpenAI(ChromaDB_VectorStore, OpenAI_Chat):
    """Vanna implementation with OpenAI and ChromaDB vector store"""
    def __init__(self, config=None):
        ChromaDB_VectorStore.__init__(self, config=config)
        OpenAI_Chat.__init__(self, config=config)


class VannaAnthropic(ChromaDB_VectorStore, Anthropic_Chat):
    """Vanna implementation with Anthropic Claude and ChromaDB vector store"""
    def __init__(self, config=None):
        ChromaDB_VectorStore.__init__(self, config=config)
        Anthropic_Chat.__init__(self, config=config)


class VannaOllama(ChromaDB_VectorStore, Ollama):
    """Vanna implementation with Ollama and ChromaDB vector store"""
    def __init__(self, config=None):
        ChromaDB_VectorStore.__init__(self, config=config)
        Ollama.__init__(self, config=config)


class LLMService:
    """
    Service for generating SQL queries from natural language using LLMs.
    
    Supports multiple providers (OpenAI, Anthropic, Ollama) configured via settings.
    Uses Vanna.AI with ChromaDB for training and SQL generation.
    """
    
    def __init__(self):
        """Initialize LLM service with configured provider"""
        self.provider = settings.llm_provider
        self.sql_model = settings.sql_model  # Model for SQL generation
        self.summary_model = settings.summary_model  # Model for summaries
        self.vanna = None
        self.vanna_summary = None  # Separate instance for summaries
        self._initialized = False
        
        logger.info(f"LLM Service initialized with provider: {self.provider}")
        logger.info(f"  SQL Model (input): {self.sql_model}")
        logger.info(f"  Summary Model (output): {self.summary_model}")
    
    def _initialize_vanna(self, model: str = None):
        """Initialize Vanna with the configured LLM provider and ChromaDB
        
        Args:
            model: Optional model override. If not provided, uses self.sql_model
        """
        config = {
            "model": model or self.sql_model,
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
            "path": settings.vanna_chromadb_path,  # Use configured path for ChromaDB storage
        }
        
        vanna_instance = None
        
        if self.provider == "openai":
            if not settings.openai_api_key:
                raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY in .env")
            config["api_key"] = settings.openai_api_key
            logger.info(f"Initializing Vanna with OpenAI ({config['model']}) and ChromaDB")
            vanna_instance = VannaOpenAI(config=config)
        
        elif self.provider == "anthropic":
            if not settings.anthropic_api_key:
                raise ValueError("Anthropic API key not configured. Set ANTHROPIC_API_KEY in .env")
            config["api_key"] = settings.anthropic_api_key
            logger.info(f"Initializing Vanna with Anthropic Claude ({config['model']}) and ChromaDB")
            vanna_instance = VannaAnthropic(config=config)
        
        elif self.provider == "ollama":
            config["host"] = settings.ollama_base_url
            logger.info(f"Initializing Vanna with Ollama ({config['model']} at {settings.ollama_base_url}) and ChromaDB")
            vanna_instance = VannaOllama(config=config)
        
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
        
        # Connect Vanna to PostgreSQL database
        try:
            vanna_instance.connect_to_postgres(
                host="localhost",
                dbname="snapanalyst_db",
                user="snapanalyst",
                password="snapanalyst_dev_password",
                port=5432
            )
            logger.info("Connected Vanna to PostgreSQL database")
        except Exception as e:
            logger.warning(f"Could not connect Vanna to database: {e}")
        
        return vanna_instance
    
    def _load_schema(self) -> Dict:
        """Load database schema documentation"""
        schema_path = Path(settings.vanna_schema_path)
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
        
        with open(schema_path, 'r') as f:
            schema = json.load(f)
        
        logger.info(f"Loaded schema from {schema_path}")
        return schema
    
    def _train_basic_schema(self) -> None:
        """Train Vanna on DDL with embedded business context from code lookups"""
        logger.info("Training Vanna on enhanced schema with business context...")
        
        # Load code lookups from data_mapping.json
        try:
            schema_path = Path(settings.vanna_schema_path)
            with open(schema_path, 'r') as f:
                mapping = json.load(f)
            code_lookups = mapping.get('code_lookups', {})
            logger.info(f"Loaded {len(code_lookups)} code lookup sets from data_mapping.json")
        except Exception as e:
            logger.warning(f"Could not load code lookups: {e}. Using DDL without context.")
            code_lookups = {}
        
        # Build enhanced DDL with inline comments for code lookups
        ddl_statements = [
            # ==================== HOUSEHOLDS TABLE ====================
            """
            CREATE TABLE households (
                -- Primary identifiers
                case_id VARCHAR(50) PRIMARY KEY,
                fiscal_year INTEGER,
                state_name VARCHAR(50),  -- State name for geographic queries (NOT in household_members or qc_errors)
                
                -- Income fields (household aggregated totals)
                gross_income DECIMAL(12,2),        -- Total household income before deductions
                net_income DECIMAL(12,2),          -- Income after deductions
                earned_income DECIMAL(12,2),       -- Income from wages/employment
                unearned_income DECIMAL(12,2),     -- Income from benefits/assistance (RSDI, SSI, TANF, etc.)
                
                -- Benefits
                snap_benefit DECIMAL(10,2),        -- Final calculated SNAP benefit amount
                raw_benefit DECIMAL(10,2),         -- Reported SNAP benefit (before QC corrections)
                amount_error DECIMAL(10,2),        -- Dollar amount of benefit in error
                maximum_benefit DECIMAL(10,2),     -- Max benefit for household size
                minimum_benefit DECIMAL(10,2),     -- Min benefit amount
                
                -- Household composition
                certified_household_size INTEGER,   -- Number of people in household
                num_elderly INTEGER,                -- Number of members age 60+
                num_children INTEGER,               -- Number of members under 18
                num_disabled INTEGER,               -- Number of disabled members
                
                -- Status and classification codes
                status INTEGER,
                -- STATUS CODES: 1=Amount correct, 2=Overissuance, 3=Underissuance
                -- Common query: WHERE status = 2 to find overissuance cases
                
                case_classification INTEGER,
                -- CASE CLASSIFICATION: 1=Included in error rate, 2=Excluded (SSA worker), 3=Excluded (FNS designation)
                
                categorical_eligibility INTEGER,
                -- CATEGORICAL ELIGIBILITY: 0=Not eligible, 1=Categorically eligible (exempt from income/asset tests), 2=Recoded as eligible
                
                expedited_service INTEGER,
                -- EXPEDITED SERVICE: 1=Entitled and received on time, 2=Entitled but NOT received on time, 3=Not entitled
                
                -- Other fields
                review_month INTEGER,
                review_year INTEGER
            );
            -- IMPORTANT: Use households table for state_name and household-level income queries
            -- Example queries:
            --   SELECT state_name, AVG(gross_income) FROM households GROUP BY state_name
            --   SELECT * FROM households WHERE status = 2 AND fiscal_year = 2023
            """,
            
            # ==================== HOUSEHOLD_MEMBERS TABLE ====================
            """
            CREATE TABLE household_members (
                -- Primary identifiers
                case_id VARCHAR(50),
                fiscal_year INTEGER,
                member_number INTEGER,
                
                -- Demographics
                age INTEGER,                        -- Age in years (0=under 1 year, 98=98 or older)
                sex INTEGER,
                -- SEX CODES: 1=Male, 2=Female, 3=Prefer not to answer
                
                -- Member status
                snap_affiliation_code INTEGER,
                -- SNAP AFFILIATION (eligibility status):
                --   1=Eligible and entitled to benefits
                --   2=Eligible participant in another unit
                --   4=Ineligible noncitizen (not state-funded)
                --   7=Ineligible student
                --   8=Disqualified for program violation
                --   9=Ineligible due to work requirements
                --   10=ABAWD time limit exhausted
                --   17=Foster care
                --   18=Ineligible noncitizen (state-funded)
                --   19=In home but not part of SNAP household
                --   99=Unknown
                -- Common query: WHERE snap_affiliation_code = 1 for eligible members
                
                -- Individual income sources (member-level detail)
                wages DECIMAL(10,2),                -- Wages and salaries
                self_employment_income DECIMAL(10,2),
                social_security DECIMAL(10,2),      -- RSDI benefits
                ssi DECIMAL(10,2),                  -- Supplemental Security Income
                unemployment DECIMAL(10,2),
                tanf DECIMAL(10,2),                 -- Temporary Assistance for Needy Families
                veterans_benefits DECIMAL(10,2),
                workers_compensation DECIMAL(10,2),
                child_support DECIMAL(10,2),
                other_income DECIMAL(10,2),
                total_income DECIMAL(10,2),         -- Sum of all member income
                
                PRIMARY KEY (case_id, fiscal_year, member_number)
            );
            -- IMPORTANT: This table does NOT have state_name
            -- For state-based queries, JOIN with households table on case_id
            -- Example: 
            --   SELECT h.state_name, AVG(m.wages) 
            --   FROM household_members m 
            --   JOIN households h ON m.case_id = h.case_id 
            --   GROUP BY h.state_name
            """,
            
            # ==================== QC_ERRORS TABLE ====================
            """
            CREATE TABLE qc_errors (
                -- Primary identifiers
                case_id VARCHAR(50),
                fiscal_year INTEGER,
                error_number INTEGER,               -- Sequential error number for this case
                
                -- Error classification
                element_code INTEGER,
                -- ELEMENT CODES (what area had the problem):
                --   INCOME ERRORS:
                --     311=Wages and salaries
                --     312=Self-employment
                --     331=RSDI benefits (Social Security)
                --     332=Veterans benefits
                --     333=SSI/State SSI supplement
                --     334=Unemployment compensation
                --     335=Workers compensation
                --     344=TANF/PA/GA (public assistance)
                --     346=Other unearned income
                --   ASSET ERRORS:
                --     211=Bank accounts or cash on hand
                --     212=Nonrecurring lump-sum payment
                --     221=Real property
                --     222=Vehicles
                --   DEDUCTION ERRORS:
                --     323=Dependent care deduction
                --     361=Standard deduction
                --     363=Shelter deduction
                --     365=Medical expense deductions
                --   HOUSEHOLD COMPOSITION:
                --     150=Unit composition
                --     151=Recipient disqualification
                --   ELIGIBILITY:
                --     111=Student status
                --     130=Citizenship/noncitizen status
                --     170=Social Security number
                --   COMPUTATION:
                --     520=Arithmetic computation
                -- Common queries:
                --   WHERE element_code = 311 for wage errors
                --   WHERE element_code BETWEEN 311 AND 346 for income errors
                --   WHERE element_code IN (311, 331, 333, 334) for major income errors
                
                nature_code INTEGER,
                -- NATURE CODES (what went wrong):
                --   35=Unreported source of income
                --   37=All income from source known but not included
                --   38=More income received than budgeted
                --   44=Less income received than budgeted
                --   52=Deduction that should have been included was not
                --   53=Deduction included that should not have been
                --   75=Benefit/allotment/eligibility incorrectly computed
                --   98=Transcription or computation errors
                --   99=Other
                -- Common query: WHERE nature_code IN (35, 37, 38) for income reporting issues
                
                error_amount DECIMAL(10,2),         -- Dollar amount of this specific error
                
                error_finding INTEGER,
                -- ERROR FINDING: 2=Overissuance, 3=Underissuance, 4=Ineligible
                
                agency_responsibility INTEGER,
                -- AGENCY RESPONSIBILITY:
                --   1-4, 7-8=Client responsibility (client error)
                --   10-21=Agency responsibility (agency error)
                --   Common: 1=Info not reported (client), 10=Policy incorrectly applied (agency)
                
                PRIMARY KEY (case_id, fiscal_year, error_number)
            );
            -- IMPORTANT: This table does NOT have state_name
            -- For state-based error analysis, JOIN with households table
            -- Example:
            --   SELECT h.state_name, COUNT(*) as wage_errors
            --   FROM qc_errors e
            --   JOIN households h ON e.case_id = h.case_id
            --   WHERE e.element_code = 311
            --   GROUP BY h.state_name
            """
        ]
        
        # Train on each DDL statement
        for ddl in ddl_statements:
            self.vanna.train(ddl=ddl)
        
        # Add business terminology documentation
        business_context = """
        SNAP QC Database - Business Context and Common Terms:
        
        PROGRAM TERMS:
        - SNAP = Supplemental Nutrition Assistance Program (formerly "food stamps")
        - QC = Quality Control review process to ensure benefit accuracy
        - Overissuance = Household received more benefits than entitled
        - Underissuance = Household received less benefits than entitled
        - RSDI = Retirement, Survivors, and Disability Insurance (Social Security)
        - SSI = Supplemental Security Income
        - TANF = Temporary Assistance for Needy Families (welfare/cash assistance)
        - ABAWD = Able-Bodied Adults Without Dependents (work requirement rules)
        - PA/GA = Public Assistance / General Assistance
        - Categorical Eligibility = Exempt from SNAP income/asset tests due to other program participation
        
        COMMON QUERY PATTERNS:
        1. Overissuance analysis: WHERE status = 2
        2. Income errors: WHERE element_code IN (311, 331, 333, 334)
        3. Wage errors specifically: WHERE element_code = 311
        4. Asset errors: WHERE element_code IN (211, 221, 222)
        5. Elderly households: WHERE num_elderly > 0
        6. Households with children: WHERE num_children > 0
        7. State comparisons: GROUP BY state_name (must use households table)
        8. Error amounts: SUM(error_amount) or AVG(error_amount)
        
        TABLE RELATIONSHIPS:
        - All tables join on case_id (and fiscal_year for multi-year queries)
        - state_name is ONLY in households table
        - Individual member income is in household_members table
        - Aggregated household income is in households table
        - Error details are in qc_errors table
        
        IMPORTANT NOTES:
        - Always use households table when query mentions state, state_name, or geographic analysis
        - Join household_members or qc_errors to households when needing state context
        - For income analysis: use households.gross_income for household totals, household_members.wages for individual wages
        - Status and error_finding both indicate over/under issuance but in different contexts
        """
        
        self.vanna.train(documentation=business_context)
        
        logger.info(f"Trained on {len(ddl_statements)} tables with embedded code lookups and business context")
    
    def _load_training_examples(self) -> List[Dict]:
        """Load SQL query examples for training"""
        examples_path = Path(settings.vanna_training_data_path)
        if not examples_path.exists():
            logger.warning(f"Training examples file not found: {examples_path}")
            return []
        
        with open(examples_path, 'r') as f:
            data = json.load(f)
        
        examples = data.get('example_queries', [])
        logger.info(f"Loaded {len(examples)} training examples from {examples_path}")
        return examples
    
    def _train_on_schema(self, schema: Dict) -> None:
        """Train Vanna on database schema"""
        logger.info("Training Vanna on database schema...")
        
        # Train on table structures
        for table_name, table_info in schema['tables'].items():
            ddl = self._generate_ddl_from_schema(table_name, table_info)
            self.vanna.train(ddl=ddl)
            logger.debug(f"Trained on table: {table_name}")
        
        # Train on documentation
        db_doc = (
            f"Database: {schema['database']['name']}\n"
            f"Description: {schema['database']['description']}\n"
            f"Purpose: {schema['database']['purpose']}\n"
        )
        self.vanna.train(documentation=db_doc)
        
        logger.info("Schema training completed")
    
    def _generate_ddl_from_schema(self, table_name: str, table_info: Dict) -> str:
        """Generate DDL statement from schema definition"""
        columns = []
        for col_name, col_info in table_info['columns'].items():
            col_def = f"  {col_name} {col_info['type']}"
            if not col_info.get('nullable', True):
                col_def += " NOT NULL"
            if col_info.get('description'):
                col_def += f" -- {col_info['description']}"
            columns.append(col_def)
        
        ddl = f"CREATE TABLE {table_name} (\n"
        ddl += ",\n".join(columns)
        ddl += "\n);"
        
        if table_info.get('description'):
            ddl += f"\n-- {table_info['description']}"
        
        return ddl
    
    def _train_on_examples(self, examples: List[Dict]) -> None:
        """Train Vanna on example queries"""
        logger.info(f"Training Vanna on {len(examples)} query examples...")
        
        trained_count = 0
        for example in examples:
            question = example.get('question')
            sql = example.get('sql')
            
            if question and sql:
                try:
                    self.vanna.train(question=question, sql=sql)
                    trained_count += 1
                except Exception as e:
                    logger.warning(f"Failed to train on example: {question[:50]}... - {e}")
        
        logger.info(f"Successfully trained on {trained_count} examples")
    
    def initialize(self, force_retrain: bool = False) -> None:
        """
        Initialize and train the LLM service.
        
        Args:
            force_retrain: If True, retrain even if already initialized
        """
        if self._initialized and not force_retrain:
            logger.info("LLM Service already initialized")
            return
        
        try:
            # ALWAYS initialize Vanna (connects to DB)
            self.vanna = self._initialize_vanna()
            
            # Simple training approach: Always train on basic DDL
            # This is fast (< 1 second) and ensures correct schema understanding
            self._train_basic_schema()
            
            # Optionally load examples
            examples = self._load_training_examples()
            if examples:
                self._train_on_examples(examples)
                logger.info(f"Loaded {len(examples)} query examples")
            
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize LLM Service: {e}")
            raise
    
    def generate_sql(self, question: str) -> Tuple[str, Optional[str]]:
        """
        Generate SQL query from natural language question.
        
        Args:
            question: Natural language question
        
        Returns:
            Tuple of (sql_query, explanation)
        
        Raises:
            ValueError: If service not initialized or invalid question
        """
        if not self._initialized:
            raise ValueError("LLM Service not initialized. Call initialize() first.")
        
        if not question or not question.strip():
            raise ValueError("Question cannot be empty")
        
        try:
            logger.info(f"Generating SQL for question: {question}")
            
            # Generate SQL using Vanna
            sql = self.vanna.generate_sql(question)
            
            # Clean up the SQL (Vanna sometimes wraps it)
            if isinstance(sql, str):
                # Remove markdown code blocks if present
                sql = sql.replace("```sql", "").replace("```", "").strip()
            
            # Get explanation (optional)
            explanation = None
            try:
                # Vanna can generate explanations in some cases
                explanation = f"This query answers: {question}"
            except Exception as e:
                logger.warning(f"Could not generate explanation: {e}")
            
            logger.info(f"Generated SQL: {sql[:100]}...")
            return sql, explanation
            
        except Exception as e:
            logger.error(f"Failed to generate SQL: {e}")
            raise
    
    def generate_followup_questions(self, question: str, sql: str) -> List[str]:
        """
        Generate followup questions based on the current question and SQL.
        
        Args:
            question: Original question
            sql: Generated SQL query
        
        Returns:
            List of suggested followup questions
        """
        if not self._initialized:
            raise ValueError("LLM Service not initialized. Call initialize() first.")
        
        try:
            # Vanna has a method for this, but let's provide a simple fallback
            followups = [
                "What is the average value for this data?",
                "Can you show me the top 10 results?",
                "How does this compare to last year?",
                "What is the breakdown by state?",
            ]
            return followups[:3]  # Return top 3
        except Exception as e:
            logger.warning(f"Could not generate followup questions: {e}")
            return []
    
    def generate_text(self, prompt: str, max_tokens: int = 150) -> str:
        """
        Generate text using the SUMMARY MODEL (separate from SQL model).
        
        Args:
            prompt: Text prompt for the LLM
            max_tokens: Maximum tokens to generate
        
        Returns:
            Generated text response
        """
        if not self._initialized:
            self.initialize()
        
        try:
            logger.info(f"Generating text with {self.summary_model} (max_tokens={max_tokens})")
            
            # Use OpenAI directly for summaries to use the summary model
            if self.provider == "openai":
                from openai import OpenAI
                client = OpenAI(api_key=settings.openai_api_key)
                
                response = client.chat.completions.create(
                    model=self.summary_model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=0.3
                )
                
                if response.choices and response.choices[0].message.content:
                    return response.choices[0].message.content.strip()
                else:
                    logger.warning("Empty response from OpenAI")
                    return "Unable to generate summary."
                    
            else:
                # For other providers, use Vanna (will use SQL model)
                response = self.vanna.submit_prompt(prompt, kwargs={"max_tokens": max_tokens})
                
                if response:
                    return response.strip()
                else:
                    return "Unable to generate summary."
                
        except Exception as e:
            logger.error(f"Error generating text: {e}", exc_info=True)
            return "Unable to generate summary."
    
    def get_provider_info(self) -> Dict:
        """Get information about the current LLM provider and configuration"""
        # Check if we can generate text (lazy initialization)
        status_text = "Ready (lazy init)" if not self._initialized else "Initialized"
        
        return {
            "provider": self.provider,
            "sql_model": self.sql_model,
            "summary_model": self.summary_model,
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
            "initialized": self._initialized,
            "status": status_text,
            "training_enabled": settings.vanna_training_enabled,
        }


# Global LLM service instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """
    Get the global LLM service instance (singleton pattern).
    
    Returns:
        LLMService instance
    """
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


def initialize_llm_service(force_retrain: bool = False) -> None:
    """
    Initialize the global LLM service.
    
    Args:
        force_retrain: If True, retrain even if already initialized
    """
    service = get_llm_service()
    service.initialize(force_retrain=force_retrain)
