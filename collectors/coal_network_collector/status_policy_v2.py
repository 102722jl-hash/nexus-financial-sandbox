"""Central status policy: AI approval is accepted into the candidate set."""
CANDIDATE_STATUSES = ('CANDIDATE','AI_CANDIDATE','AI_APPROVED')
FORMAL_STATUSES = ('CONFIRMED','ACTIVE','APPROVED')
USABLE_STATUSES = CANDIDATE_STATUSES + FORMAL_STATUSES

def placeholders(values):
    return ','.join('?' for _ in values)
