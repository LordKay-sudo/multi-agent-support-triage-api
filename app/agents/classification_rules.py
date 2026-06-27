from app.models.agent_outputs import ClassificationResult, EscalationDecision
from app.models.tickets import TicketCategory, TicketPriority


def classify_ticket(subject: str, description: str) -> ClassificationResult:
    """Deterministic keyword classifier used by the mock provider and as a Bedrock fallback."""

    text = f"{subject} {description}".lower()
    category = _classify_category(text)
    priority = _classify_priority(text, category)
    confidence = _classification_confidence(text, category, priority)
    return ClassificationResult(category=category, priority=priority, confidence=confidence)


def decide_escalation(
    category: TicketCategory,
    priority: TicketPriority,
) -> EscalationDecision:
    escalate = priority in {TicketPriority.HIGH, TicketPriority.CRITICAL}
    rationale = (
        f"Escalation is {'required' if escalate else 'not required'} because the ticket is "
        f"{priority.value} priority in the {category.value} queue."
    )
    if category == TicketCategory.SECURITY and escalate:
        rationale += " Security-sensitive tickets require senior review."
    return EscalationDecision(escalate=escalate, rationale=rationale)


def _classify_category(text: str) -> TicketCategory:
    if any(term in text for term in ["breach", "compromise", "phishing", "suspicious"]):
        return TicketCategory.SECURITY
    if any(term in text for term in ["error", "bug", "down", "latency", "api", "crash"]):
        return TicketCategory.TECHNICAL
    if any(term in text for term in ["invoice", "payment", "refund", "charge", "billing"]):
        return TicketCategory.BILLING
    if any(term in text for term in ["mfa", "password", "login", "locked", "account"]):
        return TicketCategory.ACCOUNT
    return TicketCategory.GENERAL


def _classify_priority(text: str, category: TicketCategory) -> TicketPriority:
    if any(term in text for term in ["breach", "compromise", "data leak", "production down"]):
        return TicketPriority.CRITICAL
    if category == TicketCategory.SECURITY:
        return TicketPriority.HIGH
    if any(term in text for term in ["urgent", "blocked", "payroll", "angry", "cannot access"]):
        return TicketPriority.HIGH
    if any(term in text for term in ["question", "how do i", "request"]):
        return TicketPriority.LOW
    return TicketPriority.MEDIUM


def _classification_confidence(
    text: str,
    category: TicketCategory,
    priority: TicketPriority,
) -> float:
    category_terms = {
        TicketCategory.BILLING: ["invoice", "payment", "refund", "charge", "billing"],
        TicketCategory.TECHNICAL: ["error", "bug", "down", "latency", "api", "crash"],
        TicketCategory.ACCOUNT: ["mfa", "password", "login", "locked", "account"],
        TicketCategory.SECURITY: ["breach", "compromise", "phishing", "suspicious"],
        TicketCategory.GENERAL: [],
    }
    category_hits = sum(term in text for term in category_terms[category])
    priority_bonus = 0.08 if priority in {TicketPriority.HIGH, TicketPriority.CRITICAL} else 0
    confidence = 0.62 + min(category_hits * 0.08, 0.24) + priority_bonus
    return round(min(confidence, 0.94), 2)
