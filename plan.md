Good choice. I’d scope it tightly enough that you can actually ship it, but design it so it still looks like a serious AI/SWE project.

I’d call the MVP something like AidPath: an AI-powered financial-aid and benefits navigator for college students.

The core problem is simple: students often qualify for scholarships, emergency grants, food assistance, work-study-related benefits, housing support, and campus programs, but the information is scattered across university pages, government sites, and PDFs. Your app turns that into a personalized, evidence-backed checklist.

MVP

A student enters information like:

School: UMass Amherst
Year: Sophomore
State: Massachusetts
Employment: 12 hours/week
Work study: Yes
Living situation: Off campus
Main issue: Struggling to afford groceries

Then your system returns:

3 programs you may qualify for

1. Campus Emergency Grant
   Confidence: High

Why:

- You are currently enrolled
- You reported financial hardship
- Sophomores are eligible

Maximum assistance:
Up to $1,500

Documents needed:

- Student ID
- Proof of unexpected expense
- Financial aid information

Source:
UMass official financial aid page

The important part: every recommendation should have a real source and explanation.

I would explicitly avoid letting the LLM invent programs.

Architecture
┌───────────────┐
│ Next.js UI │
└───────┬───────┘
│
▼
┌───────────────┐
│ FastAPI API │
└───────┬───────┘
│
┌──────────────┴──────────────┐
│ │
▼ ▼
┌──────────────┐ ┌──────────────┐
│ PostgreSQL │ │ AI Service │
│ │ │ │
│ users │ │ extraction │
│ programs │ │ retrieval │
│ requirements │ │ explanation │
│ applications │ └──────┬───────┘
└──────────────┘ │
▼
┌────────────────┐
│ Vector Search │
│ pgvector │
└────────────────┘

But there should actually be two different decision systems.

LLM
↓
Understand messy eligibility requirements
↓
Convert to structured rules

"Students must be enrolled at least half time"
↓
{
"field": "enrollment_status",
"operator": "in",
"value": ["half_time", "full_time"]
}

Normal Python code
↓
Evaluates student against rules
↓
eligible / ineligible / unknown

That separation is one of the most important parts of the project.

You don't want:

response = llm("Does this student qualify?")

You want something closer to:

requirements = extract_requirements(program)

result = eligibility_engine.evaluate(
student_profile,
requirements
)

Then use the LLM to explain the result, not make every decision.

Your database could look like this
users

---

id
school
state
year
employment_hours
work_study
housing_status

## programs

id
name
provider
description
maximum_award
deadline
source_url
last_verified

## requirements

id
program_id
field
operator
value
source_text

## applications

id
user_id
program_id
status
deadline
notes

For example:

program:
Massachusetts Student Emergency Assistance

requirements:

state = Massachusetts
enrollment_status = enrolled
financial_need = true
Where AI actually comes in

This is where the project becomes much stronger than an ordinary CRUD app.

1. Requirement extraction

Feed a government/university page like:

Applicants must currently be enrolled at least half time and demonstrate unexpected financial hardship.

Have the model output:

{
"requirements": [
{
"field": "enrollment_status",
"operator": "in",
"value": ["half_time", "full_time"]
},
{
"field": "financial_hardship",
"operator": "equals",
"value": true
}
]
}

Use structured outputs / JSON schema so the response has to follow your format.

2. RAG

Students can ask:

"Why don't I qualify for this?"

Retrieve the relevant sections of the original aid documentation and have the model answer only from those passages.

3. Conversational intake

Instead of forcing users through a 40-field form:

"I'm a sophomore at UMass. I work around 15 hours per week and live off campus."

The LLM extracts:

{
"year": "sophomore",
"school": "UMass Amherst",
"employment_hours": 15,
"housing": "off_campus"
}

Then your app asks only for missing information.

4. Document understanding

Later, allow uploads like:

financial aid award letter
tuition bill
lease
employment documentation

The model extracts relevant information and helps fill the profile.

That's probably a V2 feature rather than MVP.

One feature I really want you to build

Have the system distinguish between:

LIKELY ELIGIBLE
LIKELY INELIGIBLE
NEED MORE INFORMATION

That third option matters.

Suppose SNAP eligibility requires certain employment conditions.

Instead of hallucinating:

"Yes, you qualify."

The system says:

Eligibility: NEED MORE INFORMATION

I still need to know:

1. Do you participate in federal work study?
2. Do you have a meal plan?
3. Approximately how many hours do you work each week?

Then after the user responds, the eligibility engine runs again.

That's a real agentic workflow, rather than just chatbot behavior.

Build it in phases

I'd keep the initial dataset intentionally small.

Phase 1 — 10–20 programs

Start with:

UMass-specific aid
Massachusetts state programs
Federal student programs
SNAP/student food assistance
Local food resources
Emergency grants

Manually collect these initially.

Build:

PostgreSQL schema
program CRUD
student profile
eligibility engine
basic React UI

No AI yet.

Phase 2 — AI ingestion

Create:

URL
↓
scraper
↓
page text
↓
LLM
↓
structured program
↓
human approval
↓
database

Your admin dashboard could literally show:

AI detected:

Program: Emergency Assistance Fund

Requirement 1:
"Must be a currently enrolled undergraduate student"

Converted rule:
student_status = undergraduate
enrollment = active

[Approve] [Edit] [Reject]

That is a very legitimate application of AI.

Phase 3 — conversational matching

User asks:

"I'm struggling with groceries."

Your agent should understand that this maps primarily to:

food assistance
emergency assistance
SNAP
campus pantry

Then run eligibility rules.

Phase 4 — evaluations

This is what could make the project stand out.

Create test cases:

## Student A

Massachusetts resident
Full-time
Work study
10 hr/week job

Expected:
Program A → eligible
Program B → eligible
Program C → insufficient information

Run 100 synthetic profiles.

Measure:

Eligibility accuracy
Requirement extraction accuracy
Retrieval precision
Hallucination rate
Citation accuracy

Now you have an actual AI system you can evaluate.

Tech stack I'd use

Because you're targeting SWE, I wouldn't overcomplicate it.

Frontend
Next.js
TypeScript
Tailwind

Backend
FastAPI
Python

Database
PostgreSQL
pgvector

AI
OpenAI / Anthropic API
Structured outputs
Embeddings
Tool calling

Infrastructure
Docker
GitHub Actions
AWS / Render / Railway / Vercel

And eventually:

Redis
Celery / Dramatiq

for program ingestion jobs.

One powerful AI agent design

Your agent could have these tools:

search_programs(query)

get_program(program_id)

evaluate_eligibility(program_id, student_id)

retrieve_requirements(program_id)

update_student_profile(field, value)

find_missing_requirements(program_id, student_id)

Then a conversation could be:

USER
I'm having trouble paying for groceries.

AGENT
→ search_programs("food assistance college students")

Found:
SNAP
UMass Meal Assistance
Student Care Supply Closet

→ evaluate_eligibility(...)

SNAP:
missing work-study status

AGENT
Are you currently participating in a federal work-study
program?

User:

Yes.

Agent:

→ update_student_profile(work_study=True)

→ evaluate_eligibility(SNAP)

Likely eligible.

That is a much more convincing demonstration of modern AI tooling than:

ChatGPT wrapper
→ answer
And this could eventually become a strong resume project

Something like:

AidPath — AI Financial Assistance Navigator | Next.js, FastAPI, PostgreSQL, pgvector, OpenAI
• Engineered an AI-powered financial-assistance platform that matches college students with government, university, and nonprofit aid programs using structured eligibility rules extracted from unstructured web documents.
• Built an agentic workflow combining tool calling, retrieval-augmented generation, and deterministic eligibility evaluation to identify missing information, personalize recommendations, and provide source-backed explanations.
• Developed an automated ingestion pipeline that converts aid documentation into validated structured program data using schema-constrained LLM outputs and human-in-the-loop review.

If you execute this well, I think it fits your resume much better than another pure ML project because it shows backend engineering + databases + AI systems + product thinking + reliability all in the same project.

The very first thing I would build is not the chatbot. Build the program + requirements schema and a Python eligibility engine first. Once that works, the AI becomes the layer that populates and interacts with the system rather than being the entire system.
