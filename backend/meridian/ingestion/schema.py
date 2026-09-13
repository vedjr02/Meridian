"""Column names of the event-log tables that every analytical module shares.

Why constants instead of string literals in each module: 01-REQUIREMENTS.md requires all modules
to read one normalized schema and never invent their own column names. Importing the names from
here turns a typo into an import error instead of a silently empty column.
"""

CASE_ID = "case_id"
EVENT_INDEX = "event_index"
ACTIVITY = "activity"
LIFECYCLE = "lifecycle"
TIMESTAMP = "timestamp"
RESOURCE = "resource"
COST = "cost"
OUTCOME = "outcome"

# Every event exactly as parsed from the source file, all lifecycle transitions included, values
# still raw strings. Validation and typing happen in normalization.
RAW_COLUMNS = (CASE_ID, EVENT_INDEX, ACTIVITY, LIFECYCLE, TIMESTAMP, RESOURCE)

# The normalized schema from 01-REQUIREMENTS.md plus `event_index`, the event's position within
# its trace in the source file. Why the extra column: a database table has no inherent row order
# and timestamps alone cannot order two events that share one, so without an explicit tiebreak
# two runs could order such events differently and yield different directly-follows counts.
# Logged as a scope decision in 07-PROGRESS-STATE.md.
NORMALIZED_COLUMNS = (CASE_ID, EVENT_INDEX, ACTIVITY, TIMESTAMP, RESOURCE, COST, OUTCOME)
