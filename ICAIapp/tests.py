from django.test import TestCase

# Test plan:
# - Create session as guest and verify public_token returned + questions seeded.
# - Create session as authenticated user and verify list/detail access works.
# - PATCH answer, then evaluate to store per-question feedback and overall results.
# - Verify guest token required for detail/generate/evaluate.
# - Delete a question keeps order holes and subsequent generates append after max order.
