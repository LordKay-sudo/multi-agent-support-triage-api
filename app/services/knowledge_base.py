from app.models.tickets import TicketCategory


class SupportKnowledgeBase:
    """Small local knowledge base used by the retrieval agent."""

    _guidance: dict[TicketCategory, list[str]] = {
        TicketCategory.BILLING: [
            "Confirm the invoice, payment method, and renewal date before changing account state.",
            "Escalate disputed charges above the refund threshold to finance operations.",
        ],
        TicketCategory.TECHNICAL: [
            "Capture reproduction steps, affected environment, and recent changes.",
            "Check service status and known incidents before drafting customer guidance.",
        ],
        TicketCategory.ACCOUNT: [
            "Verify identity before changing authentication settings or account ownership.",
            "Offer a secure recovery path and avoid requesting secrets in support channels.",
        ],
        TicketCategory.SECURITY: [
            "Treat suspected account compromise as high priority until disproven.",
            "Preserve audit context and route confirmed incidents to the security queue.",
        ],
        TicketCategory.GENERAL: [
            "Clarify the customer goal and collect missing context before closing the ticket.",
            "Provide a concise next step and expected response window.",
        ],
    }

    def lookup(self, category: TicketCategory) -> list[str]:
        return self._guidance.get(category, self._guidance[TicketCategory.GENERAL])
