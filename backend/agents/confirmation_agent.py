# backend/agents/confirmation_agent.py
from config import settings


class ConfirmationAgent:
    """
    Manages the iterative product confirmation loop.
    Tracks how many batches have been shown to the user.
    To change max attempts, update MAX_CONFIRMATION_ITERATIONS in .env.
    """

    def __init__(self):
        self.iteration = 0
        self.all_fetched: list[dict] = []

    def next_batch(self, new_products: list[dict]) -> dict:
        """
        Record a new batch and increment iteration counter.
        Returns state dict to emit via SSE.
        """
        self.iteration += 1
        self.all_fetched.extend(new_products)
        return {
            "iteration": self.iteration,
            "batch": new_products,
            "max_iterations": settings.max_confirmation_iterations,
            "needs_more_detail": self.iteration >= settings.max_confirmation_iterations,
        }

    def should_ask_for_more_detail(self) -> bool:
        return self.iteration >= settings.max_confirmation_iterations
